"""Grid router: obstacle clearance, layer changes, negotiation between nets and the written source."""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "automation/placement"))
import grid_route as gr  # noqa: E402

LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
PLACE = {"board": {"outline": {"type": "circle", "radius": 2.9}}}


def rect(x0, y0, x1, y1):
    return [{"outline": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "holes": []}]


def geometry(pads):
    """pads: (ref, num, net, layer, x0, y0, x1, y1) rectangles -> a layout_extract-style geometry dict."""
    polys, fps = [], {}
    for ref, num, net, layer, x0, y0, x1, y1 in pads:
        shape = rect(x0, y0, x1, y1)
        polys.append({"net": net, "layer": layer, "kind": "pad", "ref": f"{ref}.{num}", "polys": shape})
        fps.setdefault(ref, []).append({"num": num, "net": net, "x": (x0 + x1) / 2, "y": (y0 + y1) / 2,
                                        "layers": [layer], "drill": 0.0, "shapes": {layer: shape}})
    return {"bbox": [-3, -3, 3, 3], "copper_layers": LAYERS, "polys": polys, "vias": [], "tracks": [],
            "footprints": [{"ref": r, "pads": p} for r, p in fps.items()]}


def route(geo, nets, **cfg):
    c = dict(gr.SETTINGS, **cfg)
    board = gr.Board(geo, PLACE, c)
    router = gr.Router(board, nets, c, log=lambda m: None)
    converged = router.run()
    tracks, vias = router.results()
    opens = [n for n in router.nets if router.state[n]["open"]]
    return converged, opens, tracks, vias


def min_gap_to_rect(tracks, box):
    """Smallest copper gap between the new tracks and an axis-aligned rectangle."""
    x0, y0, x1, y1 = box
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(gr.seg_dist(a, b, c, d) - t["width"] / 2
               for t in tracks for a, b in zip(t["pts"], t["pts"][1:]) for c, d in edges)


def test_track_detours_around_a_foreign_pad_with_rule_clearance():
    wall = (-0.2, -1.5, 0.2, 1.5)
    geo = geometry([("A", "1", "A", "F.Cu", -2.2, -0.2, -1.8, 0.2), ("A", "2", "A", "F.Cu", 1.8, -0.2, 2.2, 0.2),
                    ("W", "1", "W", "F.Cu", *wall)])
    converged, opens, tracks, vias = route(geo, ["A"], layers=["F.Cu"])
    assert converged and not opens and not vias
    assert min_gap_to_rect(tracks, wall) >= 0.15


def test_a_full_width_wall_is_crossed_through_vias_or_reported_open():
    wall = (-0.2, -3.0, 0.2, 3.0)
    pads = [("A", "1", "A", "F.Cu", -2.2, -0.2, -1.8, 0.2), ("A", "2", "A", "F.Cu", 1.8, -0.2, 2.2, 0.2),
            ("W", "1", "W", "F.Cu", *wall)]
    _, opens, _, _ = route(geometry(pads), ["A"], layers=["F.Cu"])
    assert opens == ["A"]                                   # unreachable on one layer: reported, not forced
    converged, opens, tracks, vias = route(geometry(pads), ["A"], layers=["F.Cu", "B.Cu"])
    assert converged and not opens and len(vias) >= 2
    assert {t["layer"] for t in tracks} == {"F.Cu", "B.Cu"}
    for v in vias:                                          # vias stay clear of the wall on F.Cu
        assert abs(v["x"]) - 0.3 - 0.2 >= 0.15


def test_crossing_nets_negotiate_layers_and_keep_clearance():
    pads = [("A", "1", "A", "F.Cu", -2.3, -0.2, -1.9, 0.2), ("A", "2", "A", "F.Cu", 1.9, -0.2, 2.3, 0.2),
            ("C", "1", "C", "F.Cu", -0.2, -2.3, 0.2, -1.9), ("C", "2", "C", "F.Cu", -0.2, 1.9, 0.2, 2.3)]
    converged, opens, tracks, vias = route(geometry(pads), ["A", "C"], layers=["F.Cu", "B.Cu"])
    assert converged and not opens
    assert gr.exact_check(tracks, vias, 0.6) == []
    assert vias                                             # one of them changes layer to cross


def test_exact_check_flags_close_tracks_of_different_nets():
    tracks = [{"net": "A", "layer": "F.Cu", "width": 0.15, "pts": [[0, 0], [2, 0]]},
              {"net": "B", "layer": "F.Cu", "width": 0.15, "pts": [[0, 0.25], [2, 0.25]]}]
    assert gr.exact_check(tracks, [], 0.6)                  # 0.25 - 0.15 = 0.10 mm < 0.15 mm
    tracks[1]["pts"] = [[0, 0.3], [2, 0.3]]
    assert gr.exact_check(tracks, [], 0.6) == []


def test_written_routes_round_trip_and_replace_the_previous_section(tmp_path, monkeypatch):
    vdir = tmp_path / "v"
    vdir.mkdir()
    (vdir / "placement.yaml").write_bytes(b"board: {outline: {type: circle, radius: 3}}\r\n")
    monkeypatch.setattr(gr.paths, "HARDWARE", tmp_path)
    tracks = [{"net": "A", "layer": "F.Cu", "width": 0.15, "pts": [[-1.175, 0.025], [1.025, 0.025]]}]
    vias = [{"net": "A", "x": 0.525, "y": -0.075}]
    gr.write_routes("v", tracks, vias)
    gr.write_routes("v", tracks, vias)                      # idempotent: the section is replaced
    raw = (vdir / "placement.yaml").read_bytes()
    assert raw.count(b"grid_routes:") == 1 and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    data = yaml.safe_load(raw.decode("utf-8"))
    assert data["grid_routes"] == {"tracks": tracks, "vias": vias}
