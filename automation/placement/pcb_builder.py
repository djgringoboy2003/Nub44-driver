"""KiCad-side PCB builder. Runs inside KiCad's bundled Python (needs the SWIG pcbnew module).

Invoked by automation/placement/build_pcb.py with a JSON job file:

  mode "place":  create the board (outline, footprints, nets, manual + automatic placement,
                 pre-routed tracks/vias, plane zones), save it and export Specctra DSN.
  mode "finish": load the placed board, import the FreeRouting session, add copper pours,
                 fill all zones and save.

All coordinates in the job are millimetres relative to the board centre (Y down).
"""
from __future__ import annotations

import json
import math
import sys

import pcbnew

MM = pcbnew.FromMM


def P(job, x, y):
    ox, oy = job["origin"]
    return pcbnew.VECTOR2I(MM(ox + x), MM(oy + y))


def layer_id(board, name):
    return board.GetLayerID(name)


# ---------------------------------------------------------------------------------- nets
def get_net(board, name, cache={}):
    if name in cache and cache[name].GetNetCode() > 0 and board.FindNet(name):
        return cache[name]
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    cache[name] = net
    return net


# ---------------------------------------------------------------------------------- footprints
def load_fp(item):
    fp = pcbnew.FootprintLoad(item["lib_dir"], item["fp_name"])
    if fp is None:
        raise RuntimeError(f"footprint {item['fp_name']} not found in {item['lib_dir']}")
    return fp


def place_fp(board, job, fp, item, x, y, rot, side):
    native_back = fp.GetLayer() == pcbnew.B_Cu
    fp.SetPosition(P(job, x, y))
    fp.SetOrientationDegrees(rot)
    if side == "B" and not native_back:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def courtyard_box(fp, side):
    """Courtyard bounding box (mm, board frame) on the given side, or the footprint body box."""
    layer = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
    try:
        poly = fp.GetCourtyard(layer)
        if poly.OutlineCount():
            bb = poly.BBox()
            return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                    pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    except Exception:
        pass
    bb = fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
            pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def overlap(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def inside_disc(job, box, r_max):
    ox, oy = job["origin"]
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        if math.hypot(x - ox, y - oy) > r_max:
            return False
    return True


def pad_points(fp):
    out = {}
    for pad in fp.Pads():
        pos = pad.GetPosition()
        out.setdefault(pad.GetNetname(), []).append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)))
    return out


def auto_place(board, job, fp, item, occupied, net_points):
    """Greedy nearest-free-spot placement around the anchor, scored by distance to same-net pads."""
    side = item["side"]
    ax, ay = item["anchor"]
    r_max = job["placement_radius"]
    best = None
    step = 0.25
    candidates = []
    for ring in range(0, 64):
        if ring == 0:
            pts = [(0.0, 0.0)]
        else:
            pts = []
            n = 8 * ring
            for k in range(n):
                a = 2 * math.pi * k / n
                pts.append((ring * step * math.cos(a), ring * step * math.sin(a)))
        for dx, dy in pts:
            for rot in item.get("rots", [0, 90, 180, 270]):
                place_fp(board, job, fp, item, ax + dx, ay + dy, rot, side)
                box = courtyard_box(fp, side)
                if not inside_disc(job, box, r_max):
                    continue
                if any(overlap(box, o, job["courtyard_gap"]) for o in occupied[side]):
                    continue
                if any(overlap(box, k, 0.0) for k in job["keepouts"].get(side, [])):
                    continue
                score = 0.0
                for net, pts_ in pad_points(fp).items():
                    if not net or net not in net_points:
                        continue
                    for (px, py) in pts_:
                        score += min(math.hypot(px - qx, py - qy) for qx, qy in net_points[net])
                candidates.append((score + 1.0 * math.hypot(dx, dy), ax + dx, ay + dy, rot, box))
        if len(candidates) >= 16:
            break
    if not candidates:
        raise RuntimeError(f"no free spot for {item['ref']} near {item['anchor']} on {side}")
    best = min(candidates, key=lambda c: c[0])
    place_fp(board, job, fp, item, best[1], best[2], best[3], side)
    return courtyard_box(fp, side), (best[1], best[2], best[3])


def strip_silkscreen(fp):
    """Remove footprint silkscreen graphics/text. On this density they cannot meet silk clearance
    rules; references and polarity marks are carried by the Fab (assembly) layers instead."""
    for item in list(fp.GraphicalItems()):
        if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            fp.Remove(item)


# ---------------------------------------------------------------------------------- GND fanout
def fanout(board, job, net_name, report, max_dist=1.6, width=0.25, clr=0.15, via_d=0.6, via_drill=0.3):
    """Give every SMD pad of ``net_name`` a short track to its own via (plane connection).

    Candidates are searched outward from the pad; a candidate is accepted when the via and the straight
    track keep ``clr`` from every foreign pad, track and via and the via does not land on any pad."""
    ox, oy = job["origin"]
    net = get_net(board, net_name)
    foreign_pads = []
    own_pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            (own_pads if pad.GetNetname() == net_name else foreign_pads).append(pad)
    tracks = list(board.GetTracks())
    done = failed = 0
    r = via_d / 2

    def free(px, py, x, y):
        pt = pcbnew.VECTOR2I(MM(x), MM(y))
        for pad in foreign_pads:
            if pad.HitTest(pt, MM(r + clr)):
                return False
        for pad in own_pads:                     # never put the via on a pad (solder wicking)
            if pad.HitTest(pt, MM(r + 0.05)):
                return False
        n = max(2, int(math.hypot(x - px, y - py) / 0.05))
        for i in range(1, n):
            sx, sy = px + (x - px) * i / n, py + (y - py) * i / n
            spt = pcbnew.VECTOR2I(MM(sx), MM(sy))
            for pad in foreign_pads:
                if pad.HitTest(spt, MM(width / 2 + clr)):
                    return False
        for t in tracks:
            if isinstance(t, pcbnew.PCB_VIA):           # hole-to-hole applies to every net
                tx, ty = pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)
                if math.hypot(x - tx, y - ty) < via_drill + 0.3:
                    return False
            if t.GetNetname() == net_name:
                continue
            if isinstance(t, pcbnew.PCB_VIA):
                tx, ty = pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)
                if math.hypot(x - tx, y - ty) < r + pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 + clr:
                    return False
            else:
                x0, y0 = pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y)
                x1, y1 = pcbnew.ToMM(t.GetEnd().x), pcbnew.ToMM(t.GetEnd().y)
                tw = pcbnew.ToMM(t.GetWidth()) / 2
                if _seg_dist(x, y, x0, y0, x1, y1) < r + tw + clr:
                    return False
                for i in range(0, n + 1):
                    sx, sy = px + (x - px) * i / n, py + (y - py) * i / n
                    if _seg_dist(sx, sy, x0, y0, x1, y1) < width / 2 + tw + clr:
                        return False
        return True

    for pad in own_pads:
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        if pad.GetParentFootprint().GetReference() in job.get("fanout_skip", []):
            continue
        layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        px, py = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
        best = None
        for ring in range(4, int(max_dist / 0.1) + 1):
            d = ring * 0.1
            for k in range(16):
                a = 2 * math.pi * k / 16
                x, y = px + d * math.cos(a), py + d * math.sin(a)
                if math.hypot(x - ox, y - oy) > job["placement_radius"] - r:
                    continue
                if free(px, py, x, y):
                    best = (x, y)
                    break
            if best:
                break
        if not best:
            failed += 1
            continue
        x, y = best
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(pad.GetPosition()); tr.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
        tr.SetWidth(MM(width)); tr.SetLayer(layer); tr.SetNet(net)
        board.Add(tr); tracks.append(tr)
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetDrill(MM(via_drill)); via.SetWidth(MM(via_d)); via.SetNet(net)
        board.Add(via); tracks.append(via)
        done += 1
    report.append({"fanout": net_name, "connected": done, "failed": failed})


# ---------------------------------------------------------------------------------- copper
def add_track(board, job, t):
    pts = t["pts"]
    net = get_net(board, t["net"])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(P(job, x0, y0))
        tr.SetEnd(P(job, x1, y1))
        tr.SetWidth(MM(t["width"]))
        tr.SetLayer(layer_id(board, t["layer"]))
        tr.SetNet(net)
        board.Add(tr)


def add_via(board, job, v):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(P(job, v["x"], v["y"]))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetDrill(MM(v.get("drill", 0.3)))
    via.SetWidth(MM(v.get("size", 0.6)))
    via.SetNet(get_net(board, v["net"]))
    board.Add(via)


def _point_in_poly(x, y, poly):
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def _seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    if dx == dy == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def add_via_field(board, job, vf, report):
    """Place up to vf['count'] through vias of vf['net'] on a grid inside vf['polygon'].

    A candidate is rejected if it is closer than (via radius + clearance) to any foreign-net pad,
    track or via, or overlaps ANY pad (same net included: no via-in-pad, so no solder wicking)."""
    ox, oy = job["origin"]
    net_name = vf["net"]
    r = vf.get("size", 0.6) / 2
    clr = vf.get("clearance", 0.2)
    pitch = vf.get("pitch", 0.9)
    poly = [(x + ox, y + oy) for x, y in vf["polygon"]]
    # real pad shapes (a bounding box would be wrong for the ring contact, whose box spans the board)
    pads = [(pad.GetNetname(), pad) for fp in board.GetFootprints() for pad in fp.Pads()]
    segs, vias = [], []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            vias.append((t.GetNetname(), pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y),
                         pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            segs.append((t.GetNetname(), pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y),
                         pcbnew.ToMM(t.GetEnd().x), pcbnew.ToMM(t.GetEnd().y), pcbnew.ToMM(t.GetWidth()) / 2))
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    placed = 0
    step = 0.1                      # fine candidate scan; spacing between new vias enforced via `vias`
    gy = min(ys) + r
    while gy < max(ys) and placed < vf["count"]:
        gx = min(xs) + r
        while gx < max(xs) and placed < vf["count"]:
            ok = _point_in_poly(gx, gy, poly)
            if ok:
                pt = pcbnew.VECTOR2I(MM(gx), MM(gy))
                for net, pad in pads:
                    m = r + (0.05 if net == net_name else clr)
                    if pad.HitTest(pt, MM(m)):
                        ok = False
                        break
            if ok:
                for net, x, y, vr in vias:
                    need = r + vr + (pitch - 2 * r if net == net_name else clr)
                    if math.hypot(gx - x, gy - y) < need:
                        ok = False
                        break
            if ok:
                for net, x0, y0, x1, y1, w in segs:
                    if net != net_name and _seg_dist(gx, gy, x0, y0, x1, y1) < r + w + clr:
                        ok = False
                        break
            if ok:
                add_via(board, job, {"x": gx - ox, "y": gy - oy, "net": net_name,
                                     "drill": vf.get("drill", 0.3), "size": 2 * r})
                vias.append((net_name, gx, gy, r))
                placed += 1
            gx += step
        gy += step
    report.append({"net": net_name, "requested": vf["count"], "placed": placed})
    return placed


def add_zone(board, job, z):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer_id(board, z["layer"]))
    zone.SetNet(get_net(board, z["net"]))
    outline = zone.Outline()
    outline.NewOutline()
    if z.get("circle"):
        cx, cy, r = z["circle"]
        pts = [(cx + r * math.cos(2 * math.pi * k / 96), cy + r * math.sin(2 * math.pi * k / 96)) for k in range(96)]
    else:
        pts = z["polygon"]
    for x, y in pts:
        p = P(job, x, y)
        outline.Append(p.x, p.y)
    zone.SetAssignedPriority(z.get("priority", 0))
    zone.SetLocalClearance(MM(z.get("clearance", 0.2)))
    zone.SetMinThickness(MM(z.get("min_width", 0.2)))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if z.get("solid", False) else pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(MM(z.get("thermal_gap", 0.25)))
    zone.SetThermalReliefSpokeWidth(MM(z.get("spoke", 0.3)))
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(zone)


def apply_project_rules(job):
    """pcbnew.SaveBoard() rewrites the .kicad_pro with the board's in-memory (default) settings, so the
    project design rules and net classes are re-applied after every save."""
    pro = job["board"][:-len(".kicad_pcb")] + ".kicad_pro"
    with open(pro, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(job["rules"])
    ds = d["board"]["design_settings"]
    ds["track_widths"] = job["track_widths"]
    ds["via_dimensions"] = job["via_dimensions"]
    sev = ds.setdefault("rule_severities", {})
    sev.update(job.get("rule_severities", {}))
    d["net_settings"] = job["net_settings"]
    with open(pro, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def apply_netclasses(board, job):
    """Set net classes on the in-memory board. LoadBoard() reads the project rules but does not resolve
    net-class pattern assignments, so the DSN would otherwise carry only the default class."""
    ns = board.GetDesignSettings().m_NetSettings
    classes = job["net_settings"]["classes"]

    def fill(nc, c):
        nc.SetClearance(MM(c["clearance"]))
        nc.SetTrackWidth(MM(c["track_width"]))
        nc.SetViaDiameter(MM(c["via_diameter"]))
        nc.SetViaDrill(MM(c["via_drill"]))

    for c in classes:
        if c["name"] == "Default":
            fill(ns.GetDefaultNetclass(), c)
        else:
            nc = pcbnew.NETCLASS(c["name"])
            fill(nc, c)
            nc.SetPriority(c["priority"])
            ns.SetNetclass(c["name"], nc)
    ns.ClearNetclassPatternAssignments()
    for pat in job["net_settings"]["netclass_patterns"]:
        ns.SetNetclassPatternAssignment(pat["pattern"], pat["netclass"])
    ns.ClearAllCaches()
    ns.RecomputeEffectiveNetclasses()
    board.SynchronizeNetsAndNetClasses(True)


def remove_dangling(board, job):
    """Remove vias/tracks reported dangling by the previous DRC run (positions from the JSON report)."""
    try:
        with open(job["drc_report"], encoding="utf-8") as f:
            drc = json.load(f)
    except (OSError, KeyError, ValueError):
        return 0
    targets = []
    for v in drc.get("violations", []):
        if v["type"] in ("via_dangling", "track_dangling"):
            for it in v["items"]:
                pos = it.get("pos")
                if pos:
                    targets.append((v["type"], pos["x"], pos["y"]))
    removed = 0
    for t in list(board.GetTracks()):
        is_via = isinstance(t, pcbnew.PCB_VIA)
        x, y = pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)
        for kind, tx, ty in targets:
            if (kind == "via_dangling") == is_via and abs(x - tx) < 0.01 and abs(y - ty) < 0.01:
                board.Remove(t)
                removed += 1
                break
    return removed


# ---------------------------------------------------------------------------------- modes
def mode_place(job):
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(job["copper_layers"])
    bds = board.GetDesignSettings()
    bds.SetBoardThickness(MM(job["thickness"]))

    # outline
    if job["outline"]["type"] == "circle":
        c = pcbnew.PCB_SHAPE(board)
        c.SetShape(pcbnew.SHAPE_T_CIRCLE)
        c.SetLayer(pcbnew.Edge_Cuts)
        c.SetCenter(P(job, 0, 0))
        c.SetEnd(P(job, job["outline"]["radius"], 0))
        c.SetWidth(MM(0.05))
        board.Add(c)
    else:
        w, h, r = job["outline"]["w"], job["outline"]["h"], job["outline"].get("corner", 0)
        x0, y0, x1, y1 = -w / 2, -h / 2, w / 2, h / 2
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetStart(P(job, *a))
            s.SetEnd(P(job, *b))
            s.SetWidth(MM(0.05))
            board.Add(s)

    occupied = {"F": [], "B": []}
    net_points = {}
    placements = {}
    fps = {}
    # manual parts first, then automatic ones in job order
    for item in job["footprints"]:
        fp = load_fp(item)
        fp.SetFPID(pcbnew.LIB_ID(item["lib_nick"], item["fp_name"]))
        fp.SetReference(item["ref"])
        fp.SetValue(item["value"])
        for k, v in item.get("fields", {}).items():
            fp.SetField(k, v)
            field = fp.GetField(k)
            if field is not None:
                field.SetVisible(False)
        strip_silkscreen(fp)
        fp.SetDNP(bool(item.get("dnp")))
        fp.SetExcludedFromBOM(not item.get("in_bom", True))
        fp.SetExcludedFromPosFiles(not item.get("in_pos", True))
        # dense board: no reference/value on silkscreen; references stay on the Fab (assembly) layer
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        board.Add(fp)
        for pad in fp.Pads():
            net = item["pad_nets"].get(pad.GetNumber())
            if net:
                pad.SetNet(get_net(board, net))
        fps[item["ref"]] = fp

    def area(it):
        """Courtyard area of the not-yet-placed footprint (all footprints load on the front side)."""
        x0, y0, x1, y1 = courtyard_box(fps[it["ref"]], "F")
        return (x1 - x0) * (y1 - y0)

    manual = [it for it in job["footprints"] if "pos" in it]
    auto = sorted((it for it in job["footprints"] if "pos" not in it), key=area, reverse=True)
    for item in manual + auto:
        fp = fps[item["ref"]]
        if "pos" in item:
            x, y, rot = item["pos"]
            place_fp(board, job, fp, item, x, y, rot, item["side"])
            box = courtyard_box(fp, item["side"])
            placements[item["ref"]] = (x, y, rot)
        else:
            a = item["anchor"]
            if isinstance(a, dict):      # anchor on a pad of an already placed footprint
                pad = fps[a["ref"]].FindPadByNumber(str(a["pad"]))
                pos = pad.GetPosition()
                ox, oy = job["origin"]
                dx, dy = a.get("offset", (0.0, 0.0))
                item = dict(item, anchor=(pcbnew.ToMM(pos.x) - ox + dx, pcbnew.ToMM(pos.y) - oy + dy))
            try:
                box, placements[item["ref"]] = auto_place(board, job, fp, item, occupied, net_points)
            except RuntimeError:
                pcbnew.SaveBoard(job["board"], board)       # keep the partial board for inspection
                raise
        if not item.get("no_courtyard"):
            occupied[item["side"]].append(box)
            if item.get("both_sides"):
                occupied["B" if item["side"] == "F" else "F"].append(box)
        for net, pts in pad_points(fp).items():
            net_points.setdefault(net, []).extend(pts)
        fp.SetLocked(True)

    for t in job.get("tracks", []):
        add_track(board, job, t)
    for v in job.get("vias", []):
        add_via(board, job, v)
    via_report = []
    for vf in job.get("via_fields", []):
        add_via_field(board, job, vf, via_report)
    for net_name in job.get("fanout_nets", []):
        fanout(board, job, net_name, via_report)
    for z in job.get("zones_pre", []):
        add_zone(board, job, z)
    if job.get("zones_pre"):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    pcbnew.SaveBoard(job["board"], board)
    apply_project_rules(job)
    # reload so the .kicad_pro design rules / net classes are attached before DSN export
    board = pcbnew.LoadBoard(job["board"])
    apply_netclasses(board, job)
    ok = pcbnew.ExportSpecctraDSN(board, job["dsn"])
    json.dump({"placements": placements, "via_fields": via_report, "dsn_ok": bool(ok)},
              open(job["report"], "w"), indent=1)
    print(f"placed {len(placements)} footprints; via fields {via_report}; DSN export {'ok' if ok else 'FAILED'}")


def mode_finish(job):
    board = pcbnew.LoadBoard(job["board"])
    if job.get("ses"):
        ok = pcbnew.ImportSpecctraSES(board, job["ses"])
        print(f"SES import {'ok' if ok else 'FAILED'}")
    for v in job.get("vias_post", []):
        add_via(board, job, v)
    existing = {(z.GetLayerName(), z.GetNetname(), z.GetAssignedPriority()) for z in board.Zones()}
    for z in job.get("zones_post", []):
        if (z["layer"], z["net"], z.get("priority", 0)) not in existing:
            add_zone(board, job, z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(job["board"], board)
    apply_project_rules(job)
    print(f"tracks {len(board.GetTracks())}, zones {len(board.Zones())}")


def mode_cleanup(job):
    board = pcbnew.LoadBoard(job["board"])
    n = remove_dangling(board, job)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(job["board"], board)
    apply_project_rules(job)
    print(f"cleanup: removed {n} dangling vias/tracks")


if __name__ == "__main__":
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    {"place": mode_place, "finish": mode_finish, "cleanup": mode_cleanup}[job["mode"]](job)
