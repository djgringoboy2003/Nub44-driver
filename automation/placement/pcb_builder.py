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
from pathlib import Path

import pcbnew

MM = pcbnew.FromMM


def P(job, x, y):
    ox, oy = job["origin"]
    return pcbnew.VECTOR2I(MM(ox + x), MM(oy + y))


def layer_id(board, name):
    layer = board.GetLayerID(name)
    if layer == pcbnew.UNDEFINED_LAYER:
        raise ValueError(f"Unknown KiCad layer name: {name}")
    return layer


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
    # The source angle is applied in the library frame, before a left/right flip.
    # auto_place reuses the same footprint across candidates: its current layer
    # therefore cannot tell us its original library side after the first call.
    native_back = item.setdefault("_native_back", fp.GetLayer() == pcbnew.B_Cu)
    target_back = side == "B"
    if (fp.GetLayer() == pcbnew.B_Cu) != target_back:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetPosition(P(job, x, y))
    fp.SetOrientationDegrees(180 - rot if target_back != native_back else rot)


def copper_pad(pad):
    """Paste/mask-only pads are not copper obstacles or electrical terminals."""
    return any(pcbnew.IsCopperLayer(layer) for layer in pad.GetLayerSet().Seq())


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
    """True when the box lies inside the placement area: a disc of r_max, or job['placement_box']
    (x0, y0, x1, y1 relative to the board centre) for rectangular boards."""
    ox, oy = job["origin"]
    if job.get("placement_box"):
        x0, y0, x1, y1 = job["placement_box"]
        return box[0] >= ox + x0 and box[1] >= oy + y0 and box[2] <= ox + x1 and box[3] <= oy + y1
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
            if not copper_pad(pad):
                continue
            (own_pads if pad.GetNetname() == net_name else foreign_pads).append(pad)
    tracks = list(board.GetTracks())
    done = failed = 0
    r = via_d / 2
    # source pours of other nets: a through via there would cut a hole into power copper
    pours = [[(px + ox, py + oy) for px, py in z["polygon"]] for z in job.get("zones_pre", [])
             if "polygon" in z and z["net"] != net_name]

    def in_pour(x, y):
        for poly in pours:
            inside = False
            for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
            if inside or min(_seg_dist(x, y, *a, *b) for a, b in zip(poly, poly[1:] + poly[:1])) < r + clr:
                return True
        return False

    def free(px, py, x, y, layer):
        pt = pcbnew.VECTOR2I(MM(x), MM(y))
        if in_pour(x, y):
            return False
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
                if pad.IsOnLayer(layer) and pad.HitTest(spt, MM(width / 2 + clr)):
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
                via_r = pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
                if math.hypot(x - tx, y - ty) < r + via_r + clr:
                    return False
                if _seg_dist(tx, ty, px, py, x, y) < width / 2 + via_r + clr:
                    return False
            else:
                x0, y0 = pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y)
                x1, y1 = pcbnew.ToMM(t.GetEnd().x), pcbnew.ToMM(t.GetEnd().y)
                tw = pcbnew.ToMM(t.GetWidth()) / 2
                if _seg_dist(x, y, x0, y0, x1, y1) < r + tw + clr:
                    return False
                if t.GetLayer() == layer:
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
                if not inside_disc(job, (x - r, y - r, x + r, y + r), job["placement_radius"]):
                    continue
                if free(px, py, x, y, layer):
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
def _track_key(track):
    endpoints = tuple(sorted(((track.GetStart().x, track.GetStart().y),
                              (track.GetEnd().x, track.GetEnd().y))))
    return track.GetNetname(), track.GetLayer(), track.GetWidth(), endpoints


def _via_key(via):
    diameters = tuple((layer, via.GetWidth(layer)) for layer in via.GetLayerSet().Seq()
                      if pcbnew.IsCopperLayer(layer))
    position = via.GetPosition()
    return (via.GetNetname(), position.x, position.y, via.GetViaType(), via.TopLayer(),
            via.BottomLayer(), via.GetDrillValue(), diameters)


def add_track(board, job, t):
    """Add source segments once; preserve distinct widths, layers, nets and arcs."""
    pts = t["pts"]
    net = get_net(board, t["net"])
    existing = {_track_key(track) for track in board.GetTracks() if type(track) is pcbnew.PCB_TRACK}
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(P(job, x0, y0))
        tr.SetEnd(P(job, x1, y1))
        tr.SetWidth(MM(t["width"]))
        tr.SetLayer(layer_id(board, t["layer"]))
        tr.SetNet(net)
        key = _track_key(tr)
        if key not in existing:
            board.Add(tr)
            existing.add(key)


def add_via(board, job, v):
    """Add an exact through via once, accounting for span and per-layer diameters."""
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(P(job, v["x"], v["y"]))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetDrill(MM(v.get("drill", 0.3)))
    via.SetWidth(MM(v.get("size", 0.6)))
    via.SetNet(get_net(board, v["net"]))
    key = _via_key(via)
    if not any(_via_key(existing) == key for existing in board.GetTracks()
               if isinstance(existing, pcbnew.PCB_VIA)):
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
    pads = [(pad.GetNetname(), pad) for fp in board.GetFootprints() for pad in fp.Pads() if copper_pad(pad)]
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


def reserve_source_vias(job, occupied):
    """Source vias are added after placement but pass through both sides: reserve each one (via radius
    plus clearance) on both sides so automatically placed courtyards cannot land on it."""
    ox, oy = job["origin"]
    for v in job.get("vias", []):
        r = v.get("size", 0.6) / 2 + job["rules"]["min_clearance"]
        box = (ox + v["x"] - r, oy + v["y"] - r, ox + v["x"] + r, oy + v["y"] + r)
        occupied["F"].append(box)
        occupied["B"].append(box)


def add_router_keepout(board, job, k):
    """Specctra exports pours as conduction planes that the router may cross with other nets. A router
    keep-out (tracks and vias barred, pours allowed) protects power copper during routing only: the
    finish stage deletes every zone, these rule areas included, before rebuilding the source pours.

    With ``net`` given (the pour the keep-out protects), the area is cut back around every via already on
    the board that belongs to another routed net: a through via inside a keep-out on any layer is an
    unfixable violation for the router, which then leaves that via's connection unrouted. Vias of the
    pour's own net and of plane nets (``fanout_nets``) need no router access and keep the area intact."""
    area = pcbnew.ZONE(board)
    area.SetIsRuleArea(True)
    area.SetLayer(layer_id(board, k["layer"]))
    area.SetDoNotAllowTracks(True)
    area.SetDoNotAllowVias(True)
    area.SetDoNotAllowZoneFills(False)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    outline = area.Outline()
    outline.NewOutline()
    for x, y in k["polygon"]:
        p = P(job, x, y)
        outline.Append(p.x, p.y)
    if k.get("net"):
        keep = {k["net"].lstrip("/")} | {n.lstrip("/") for n in job.get("fanout_nets", [])}
        clr = job["rules"]["min_clearance"] + 0.05
        cut = pcbnew.SHAPE_POLY_SET()
        for t in board.GetTracks():
            if t.GetClass() != "PCB_VIA" or t.GetNetname().lstrip("/") in keep:
                continue
            c, r = t.GetPosition(), t.GetWidth(pcbnew.F_Cu) / 2 + MM(clr)
            cut.NewOutline()
            for i in range(24):
                a = 2 * math.pi * i / 24
                cut.Append(int(c.x + r * math.cos(a)), int(c.y + r * math.sin(a)))
        if cut.OutlineCount():
            outline.BooleanSubtract(cut)
    board.Add(area)
    return area


def replace_source_zones(board, job):
    """Replace prior/imported pours so repeated finish uses current source polygons."""
    for zone in list(board.Zones()):
        # Delete natively: Remove transfers loaded zone ownership to Python and
        # KiCad 10's SWIG destructor can then corrupt subsequent zone wrappers.
        board.Delete(zone)
    for zone in job.get("zones_pre", []) + job.get("zones_post", []):
        add_zone(board, job, zone)


def normalize_track_widths(board, minimum_width_mm):
    """Restore minimum widths after import; clearance and connectivity still require DRC."""
    minimum_width = MM(minimum_width_mm)
    widened = 0
    for track in board.GetTracks():
        if not isinstance(track, pcbnew.PCB_VIA) and track.GetWidth() < minimum_width:
            track.SetWidth(minimum_width)
            widened += 1
    return widened


def remove_source_copper(board, job):
    """Remove exact source-listed imported items; absence is safe on repeat finish.

    All requests are checked before mutation. Multiple matches are ambiguous and
    fail closed. Coordinates use a 0.0001 mm geometric tolerance; track width is
    deliberately unrestricted so a router neckdown does not hide the requested spur.
    """
    tolerance = MM(0.0001)

    def near(a, b):
        return math.hypot(a.x - b.x, a.y - b.y) <= tolerance

    copper = list(board.GetTracks())
    targets, report = {}, []
    for kind, entries in (("via", job.get("remove_vias_post", [])),
                          ("track", job.get("remove_tracks_post", []))):
        for entry in entries:
            if kind == "via":
                position = P(job, entry["x"], entry["y"])
                matches = [item for item in copper if isinstance(item, pcbnew.PCB_VIA)
                           and item.GetNetname() == entry["net"] and near(item.GetPosition(), position)]
            else:
                if len(entry["pts"]) != 2:
                    raise ValueError("remove_tracks_post requires exactly two segment endpoints")
                start, end = (P(job, *point) for point in entry["pts"])
                layer = layer_id(board, entry["layer"])
                matches = [item for item in copper if type(item) is pcbnew.PCB_TRACK
                           and item.GetNetname() == entry["net"] and item.GetLayer() == layer
                           and ((near(item.GetStart(), start) and near(item.GetEnd(), end))
                                or (near(item.GetStart(), end) and near(item.GetEnd(), start)))]
            if len(matches) > 1:
                raise RuntimeError(f"ambiguous source {kind} removal: {entry}; {len(matches)} matches")
            report.append({"kind": kind, **entry, "matches": len(matches)})
            for item in matches:
                targets[id(item)] = item
    for item in targets.values():
        board.Delete(item)
    return report


def apply_project_rules(job):
    """pcbnew.SaveBoard() rewrites the .kicad_pro with the board's in-memory (default) settings, so the
    project design rules and net classes are re-applied after every save."""
    pro = job["board"][:-len(".kicad_pcb")] + ".kicad_pro"
    # Capture before native SaveBoard: it can rewrite or truncate the project.
    # New jobs always carry that snapshot; fallback supports old scratch jobs.
    d = job.get("project_data")
    if d is None:
        with open(pro, encoding="utf-8") as f:
            d = json.load(f)
    d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(job["rules"])
    ds = d["board"]["design_settings"]
    ds["track_widths"] = job["track_widths"]
    ds["via_dimensions"] = job["via_dimensions"]
    sev = ds.setdefault("rule_severities", {})
    sev.update(job.get("rule_severities", {}))
    d["net_settings"] = job["net_settings"]
    temporary = Path(pro).with_suffix(".kicad_pro.tmp")
    temporary.write_text(json.dumps(d, indent=2), encoding="utf-8")
    temporary.replace(pro)


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
    """Delete only dangling track/via UUIDs from DRC; shared endpoints are not identities."""
    try:
        with open(job["drc_report"], encoding="utf-8") as f:
            drc = json.load(f)
    except (OSError, KeyError, ValueError):
        return 0
    targets = {}
    for v in drc.get("violations", []):
        if v["type"] in ("via_dangling", "track_dangling"):
            for it in v["items"]:
                if it.get("uuid"):
                    targets.setdefault(it["uuid"], set()).add(v["type"])
    removed = 0
    for t in list(board.GetTracks()):
        is_via = isinstance(t, pcbnew.PCB_VIA)
        kind = "via_dangling" if is_via else "track_dangling"
        if kind in targets.get(t.m_Uuid.AsString(), set()):
            board.Delete(t)
            removed += 1
    return removed


# ---------------------------------------------------------------------------------- modes
def add_texts(board, job):
    """Replace the board-level labels with the placement source's; repeatable across finish runs.

    Every board-level text comes from placement.yaml (footprint texts are separate), so the old ones are
    removed first: a changed size, stroke or position then takes effect instead of being skipped.
    """
    for t in [t for t in board.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT)]:
        board.Remove(t)
    for item in job.get("texts", []):
        position = P(job, *item["at"])
        layer = layer_id(board, item.get("layer", "F.Silkscreen"))
        text = pcbnew.PCB_TEXT(board)
        text.SetText(item["text"])
        text.SetPosition(position)
        text.SetLayer(layer)
        text.SetTextSize(pcbnew.VECTOR2I(MM(item.get("size", 1.0)), MM(item.get("size", 1.0))))
        text.SetTextThickness(MM(item.get("thickness", 0.15)))
        text.SetMirrored(layer == pcbnew.B_SilkS)
        board.Add(text)


def mode_place(job):
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(job["copper_layers"])
    bds = board.GetDesignSettings()
    bds.SetBoardThickness(MM(job["thickness"]))
    bds.SetAuxOrigin(P(job, 0, 0))          # drill/place origin = board centre (centroid file reference)

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
        item["_native_back"] = fp.GetLayer() == pcbnew.B_Cu
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
    reserve_source_vias(job, occupied)
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
    # grid_route.py copper comes after the via fields it was routed around and before the fanout,
    # which then keeps clear of it
    for t in job.get("grid_tracks", []):
        add_track(board, job, t)
    for v in job.get("grid_vias", []):
        add_via(board, job, v)
    for net_name in job.get("fanout_nets", []):
        fanout(board, job, net_name, via_report)
    for z in job.get("zones_pre", []):
        add_zone(board, job, z)
    if job.get("zones_pre"):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for k in job.get("router_keepouts", []):
        add_router_keepout(board, job, k)

    add_texts(board, job)
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
        if not ok:
            raise RuntimeError("Specctra session import failed; board was not saved")
    removals = remove_source_copper(board, job)
    if removals:
        print("source copper removals: " + json.dumps(removals))
    widened = normalize_track_widths(board, job["rules"]["min_track_width"])
    print(f"restored {widened} imported track widths to the {job['rules']['min_track_width']} mm minimum; DRC required")
    for track in job.get("tracks_post", []):
        add_track(board, job, track)
    for v in job.get("vias_post", []):
        add_via(board, job, v)
    # Rebuild the source-defined zones on every finish. SES import/repeated finish
    # can otherwise retain duplicate pours or outdated source polygons.
    replace_source_zones(board, job)
    # Preserve BOM/DNP flags while matching mount type to the actual copper pads.
    for footprint in board.GetFootprints():
        pads = [p for p in footprint.Pads() if copper_pad(p)]
        mount = pcbnew.FP_THROUGH_HOLE if any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in pads) else pcbnew.FP_SMD
        footprint.SetAttributes((footprint.GetAttributes() & ~(pcbnew.FP_THROUGH_HOLE | pcbnew.FP_SMD)) | mount)
    add_texts(board, job)
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


def mode_geometry(job):
    """Write footprint geometry (unplaced: origin, orientation 0) for the fast floorplan checker:
    pad outlines, pad nets, courtyard box and whether the footprint is native to the back side."""
    out = {}
    sources = {Path(__file__).resolve(), Path(job["board"]).with_suffix(".net")}
    for item in job["footprints"]:
        sources.add(Path(item["lib_dir"]) / (item["fp_name"] + ".kicad_mod"))
        fp = load_fp(item)
        native_back = fp.GetLayer() == pcbnew.B_Cu
        pads = []
        for pad in fp.Pads():
            if not copper_pad(pad):
                continue
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                kind, layer = "THT", pcbnew.F_Cu
            else:
                kind = "B" if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else "F"
                layer = pcbnew.B_Cu if kind == "B" else pcbnew.F_Cu
            poly = pad.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
            outline = []
            if poly.OutlineCount():
                o = poly.Outline(0)
                outline = [(round(pcbnew.ToMM(o.CPoint(k).x), 4), round(pcbnew.ToMM(o.CPoint(k).y), 4))
                           for k in range(o.PointCount())]
            pos = pad.GetPosition()
            pads.append({"num": pad.GetNumber(), "x": pcbnew.ToMM(pos.x), "y": pcbnew.ToMM(pos.y), "kind": kind,
                         "net": item["pad_nets"].get(pad.GetNumber(), ""), "outline": outline,
                         "drill": pcbnew.ToMM(pad.GetDrillSize().x) if kind == "THT" else 0.0})
        out[item["ref"]] = {"native_back": native_back, "pads": pads,
                            "courtyard": courtyard_box(fp, "B" if native_back else "F")}
    out["__meta__"] = {"format_version": 2, "sources": [
        {"path": str(p), "mtime_ns": p.stat().st_mtime_ns, "size": p.stat().st_size}
        for p in sorted(sources) if p.exists()]}
    with open(job["geometry"], "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"geometry for {len(job['footprints'])} footprints")


if __name__ == "__main__":
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    {"place": mode_place, "finish": mode_finish, "cleanup": mode_cleanup,
     "geometry": mode_geometry}[job["mode"]](job)
