"""KiCad-side copper extractor for the layout review. Runs inside KiCad's bundled Python.

Writes every copper item of a routed board as polygons per net and layer, plus the raw
track segments, vias and pads that the geometric checks need:

  usage: <kicad python> layout_extract.py <board.kicad_pcb> <out.json>

Coordinates are millimetres relative to the board centre (+y down), the same frame as
hardware/<variant>/placement.yaml. Zone polygons are the filled areas KiCad computed, so
the board must have been filled (the build's DRC stage refills and saves it).
"""
from __future__ import annotations

import hashlib
import json
import sys

import pcbnew

MAX_ERR = pcbnew.FromMM(0.005)


def mm(v):
    return round(pcbnew.ToMM(v), 4)


def outlines(poly, ox, oy):
    """SHAPE_POLY_SET -> [{"outline": [[x, y], ...], "holes": [[[x, y], ...], ...]}]."""
    def chain(c):
        return [[mm(c.CPoint(k).x) - ox, mm(c.CPoint(k).y) - oy] for k in range(c.PointCount())]
    out = []
    for i in range(poly.OutlineCount()):
        out.append({"outline": chain(poly.Outline(i)),
                    "holes": [chain(poly.Hole(i, h)) for h in range(poly.HoleCount(i))]})
    return out


def item_poly(item, layer):
    poly = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(poly, layer, 0, MAX_ERR, pcbnew.ERROR_INSIDE)
    return poly


def main(board_path, out_path):
    board = pcbnew.LoadBoard(board_path)
    box = board.GetBoardEdgesBoundingBox()
    ox, oy = mm(box.Centre().x), mm(box.Centre().y)
    copper = [board.GetLayerName(l) for l in board.GetEnabledLayers().CuStack()]
    ids = {board.GetLayerName(l): l for l in board.GetEnabledLayers().CuStack()}
    copper_um = {}
    try:
        for it in board.GetDesignSettings().GetStackupDescriptor().GetList():
            if it.GetType() == pcbnew.BS_ITEM_TYPE_COPPER:
                copper_um[board.GetLayerName(it.GetBrdLayerId())] = round(pcbnew.ToMM(it.GetThickness()) * 1000, 2)
    except Exception as exc:  # stack-up API differs between KiCad builds; report, never guess
        copper_um = {"error": str(exc)}

    polys = []        # {"net", "layer", "kind", "ref", "polys"}
    footprints = []
    for fp in board.GetFootprints():
        pads = []
        for pad in fp.Pads():
            on = [n for n in copper if pad.IsOnLayer(ids[n])]
            if not on:
                continue
            pos = pad.GetPosition()
            drill = mm(pad.GetDrillSize().x) if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else 0.0
            shapes = {}
            for name in on:
                shapes[name] = outlines(pad.GetEffectivePolygon(ids[name], pcbnew.ERROR_INSIDE), ox, oy)
                polys.append({"net": pad.GetNetname(), "layer": name, "kind": "pad",
                              "ref": f"{fp.GetReference()}.{pad.GetNumber()}", "polys": shapes[name]})
            pads.append({"num": pad.GetNumber(), "net": pad.GetNetname(), "x": mm(pos.x) - ox,
                         "y": mm(pos.y) - oy, "layers": on, "drill": drill, "shapes": shapes})
        pos = fp.GetPosition()
        footprints.append({"ref": fp.GetReference(), "value": fp.GetValue(), "x": mm(pos.x) - ox,
                           "y": mm(pos.y) - oy, "rot": round(fp.GetOrientationDegrees(), 3),
                           "side": "B" if fp.GetLayer() == pcbnew.B_Cu else "F", "pads": pads})

    tracks, vias = [], []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            top, bot = board.GetLayerName(t.TopLayer()), board.GetLayerName(t.BottomLayer())
            span = copper[copper.index(top):copper.index(bot) + 1]
            pos = t.GetPosition()
            vias.append({"net": t.GetNetname(), "x": mm(pos.x) - ox, "y": mm(pos.y) - oy,
                         "d": mm(t.GetWidth(ids[top])), "drill": mm(t.GetDrillValue()), "layers": span})
            for name in span:
                polys.append({"net": t.GetNetname(), "layer": name, "kind": "via", "ref": "",
                              "polys": outlines(item_poly(t, ids[name]), ox, oy)})
            continue
        layer = board.GetLayerName(t.GetLayer())
        rec = {"net": t.GetNetname(), "layer": layer, "w": mm(t.GetWidth()),
               "a": [mm(t.GetStart().x) - ox, mm(t.GetStart().y) - oy],
               "b": [mm(t.GetEnd().x) - ox, mm(t.GetEnd().y) - oy]}
        if t.GetClass() == "PCB_ARC":
            rec["mid"] = [mm(t.GetMid().x) - ox, mm(t.GetMid().y) - oy]
        tracks.append(rec)
        polys.append({"net": t.GetNetname(), "layer": layer, "kind": "track", "ref": "",
                      "polys": outlines(item_poly(t, t.GetLayer()), ox, oy)})

    zones = []
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        for name in copper:
            if not z.IsOnLayer(ids[name]):
                continue
            filled = z.GetFilledPolysList(ids[name])
            shapes = outlines(filled, ox, oy) if filled is not None else []
            zones.append({"net": z.GetNetname(), "layer": name, "priority": z.GetAssignedPriority(),
                          "filled_area_mm2": round(sum(_area(s) for s in shapes), 3)})
            polys.append({"net": z.GetNetname(), "layer": name, "kind": "zone", "ref": "", "polys": shapes})

    with open(board_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    out = {"board": board_path, "board_sha256": digest, "origin": [ox, oy],
           "bbox": [mm(box.GetLeft()) - ox, mm(box.GetTop()) - oy, mm(box.GetRight()) - ox, mm(box.GetBottom()) - oy],
           "copper_layers": copper, "copper_um": copper_um,
           "thickness_mm": mm(board.GetDesignSettings().GetBoardThickness()),
           "footprints": footprints, "tracks": tracks, "vias": vias, "zones": zones, "polys": polys}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"extracted {len(footprints)} footprints, {len(tracks)} tracks, {len(vias)} vias, "
          f"{len(zones)} zone layers")


def _area(shape):
    def a(pts):
        return 0.5 * sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))
    return abs(a(shape["outline"])) - sum(abs(a(h)) for h in shape["holes"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
