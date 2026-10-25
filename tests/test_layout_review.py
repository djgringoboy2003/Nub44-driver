"""Analytic checks of the layout-review copper model and DC current-flow solver."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))

from review import dcflow  # noqa: E402
from review.raster import CopperModel  # noqa: E402

OZ1 = 0.03479


def rect(x0, y0, x1, y1):
    return {"outline": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "holes": []}


def strip_geo(layers=("F.Cu",), length=10.0, width=1.0, vias=()):
    polys = [{"net": "/N", "layer": l, "kind": "zone", "ref": "", "polys": [rect(0, 0, length, width)]}
             for l in layers]
    pads = []
    for num, x0 in (("1", 0.0), ("2", length - 1.0)):
        shape = rect(x0, 0, x0 + 1.0, width)
        pads.append({"num": num, "net": "/N", "x": x0 + 0.5, "y": width / 2, "layers": ["F.Cu"],
                     "drill": 0.0, "shapes": {"F.Cu": [shape]}})
    via_recs = [{"net": "/N", "x": x, "y": width / 2, "d": 0.6, "drill": 0.3, "layers": list(layers)}
                for x in vias]
    return {"bbox": [0.0, 0.0, length, width], "copper_layers": list(layers), "polys": polys,
            "footprints": [{"ref": "R1", "x": 0, "y": 0, "rot": 0, "side": "F", "pads": pads}],
            "vias": via_recs}


def stack(layers):
    return dcflow.Stack(copper_mm={l: OZ1 for l in layers}, gaps_mm=[1.5] * (len(layers) - 1))


def test_strip_resistance_matches_sheet_squares():
    geo = strip_geo()
    model = CopperModel(geo, 0.05)
    st = stack(["F.Cu"])
    flow = dcflow.solve(model, "N", {"a": (["R1.1"], 1.0), "b": (["R1.2"], 0.0)}, "b", st)
    expected = st.r_sheet("F.Cu") * 8.0           # 8 squares between the pad edges
    assert flow.resistance("a") == pytest.approx(expected, rel=0.03)
    assert flow.loss_w == pytest.approx(1.0 * flow.v_terminal["a"], rel=0.02)
    hot = dcflow.hot_area_k(flow, model.grid.h, area_mm2=0.25)
    assert hot["k_a_per_mm"] == pytest.approx(1.0, rel=0.05)    # 1 A across 1 mm


def test_second_layer_joined_by_vias_halves_resistance():
    one = dcflow.solve(CopperModel(strip_geo(), 0.05), "N",
                       {"a": (["R1.1"], 1.0), "b": (["R1.2"], 0.0)}, "b", stack(["F.Cu"]))
    layers = ("F.Cu", "B.Cu")
    geo = strip_geo(layers, vias=(0.5, 9.5))
    two = dcflow.solve(CopperModel(geo, 0.05), "N",
                       {"a": (["R1.1"], 1.0), "b": (["R1.2"], 0.0)}, "b", stack(list(layers)))
    r1, r2 = one.resistance("a"), two.resistance("a")
    st = stack(list(layers))
    barrel = st.barrel_r(0.3, 1.5)
    # parallel: (B.Cu strip + two barrels) || F.Cu strip, within raster/spreading tolerance
    b_path = st.r_sheet("B.Cu") * 9.0 + 2 * barrel
    expected = 1 / (1 / r1 + 1 / b_path)
    assert r2 < 0.75 * r1
    assert r2 == pytest.approx(expected, rel=0.08)
    assert max(v["max_segment_current_a"] for v in two.via_currents) > 0.2


def test_barrel_resistance_formula_matches_copper_module():
    from nubm44.calc import copper
    st = dcflow.Stack(copper_mm={"F.Cu": OZ1}, gaps_mm=[], plating_mm=0.020, temp_c=25.0)
    assert st.barrel_r(0.3, 1.6) * 1000 == pytest.approx(copper.via_resistance_mohm(0.3, 20.0, 1.6, 25.0), rel=1e-9)
    assert st.r_sheet("F.Cu") * 1000 == pytest.approx(copper.sheet_resistance_mohm(1.0, 25.0), rel=1e-3)


def test_disconnected_terminal_is_reported():
    geo = strip_geo()
    geo["polys"][0]["polys"] = [rect(0, 0, 4, 1), rect(6, 0, 10, 1)]
    with pytest.raises(ValueError, match="not connected"):
        dcflow.solve(CopperModel(geo, 0.05), "N", {"a": (["R1.1"], 1.0), "b": (["R1.2"], 0.0)}, "b",
                     stack(["F.Cu"]))


def test_neck_raises_current_density_and_resistance():
    geo = strip_geo(width=2.0)
    wide = dcflow.solve(CopperModel(geo, 0.05), "N", {"a": (["R1.1"], 1.0), "b": (["R1.2"], 0.0)}, "b",
                        stack(["F.Cu"]))
    # a 0.5 mm wide, 2 mm long neck in the middle of the strip
    geo["polys"][0]["polys"] = [rect(0, 0, 4, 2), rect(4, 0.75, 6, 1.25), rect(6, 0, 10, 2)]
    neck = dcflow.solve(CopperModel(geo, 0.05), "N", {"a": (["R1.1"], 1.0), "b": (["R1.2"], 0.0)}, "b",
                        stack(["F.Cu"]))
    st = stack(["F.Cu"])
    assert neck.resistance("a") - wide.resistance("a") > st.r_sheet("F.Cu") * (4.0 - 1.0)
    hot = dcflow.hot_area_k(neck, 0.05, area_mm2=0.25)
    assert hot["k_a_per_mm"] == pytest.approx(2.0, rel=0.1)     # 1 A through 0.5 mm
    assert math.isfinite(hot["k_max_a_per_mm"])
    assert np.nanmax(neck.k_map["F.Cu"]) >= hot["k_a_per_mm"]


# ------------------------------------------------------------------ review helpers
from review import power_layout  # noqa: E402


def two_track_geo(sep=0.3, other_layer=False):
    geo = strip_geo(layers=("F.Cu", "In1.Cu"))
    geo["tracks"] = [
        {"net": "/A", "layer": "F.Cu", "w": 0.15, "a": [1.0, 0.2], "b": [9.0, 0.2]},
        {"net": "/B", "layer": "In1.Cu" if other_layer else "F.Cu", "w": 0.15, "a": [1.0, 0.2 + sep], "b": [9.0, 0.2 + sep]},
    ]
    return geo


def test_pair_separation_measures_parallel_kelvin_routes():
    st = stack(["F.Cu", "In1.Cu"])
    close = power_layout.pair_separation(CopperModel(two_track_geo(0.3), 0.05), "A", "B", st)
    assert close["A"]["max_separation_mm"] == pytest.approx(0.3, abs=0.01)
    assert close["A"]["enclosed_area_mm2"] == pytest.approx(8 * 0.3, rel=0.02)
    assert close["A"]["length_separated_over_1mm"] == 0
    apart = power_layout.pair_separation(CopperModel(two_track_geo(0.0, other_layer=True), 0.05), "A", "B", st)
    assert apart["A"]["max_separation_mm"] == pytest.approx(1.5, abs=0.01)   # layer spacing only


def test_loop_area_uses_three_dimensional_distance_to_the_return():
    st = stack(["F.Cu", "In1.Cu"])
    geo = two_track_geo()
    geo["tracks"] = geo["tracks"][:1]
    geo["polys"] = [{"net": "/R", "layer": "In1.Cu", "kind": "zone", "ref": "", "polys": [rect(0, 0, 10, 1)]}]
    res = power_layout.loop_area(CopperModel(geo, 0.05), "A", "R", st)
    assert res["loop_area_mm2"] == pytest.approx(8 * 1.5, rel=0.02)       # return plane directly below
    geo["polys"] = []
    assert power_layout.loop_area(CopperModel(geo, 0.05), "A", "R", st)["loop_area_mm2"] is None


def test_geodesic_follows_copper_and_reports_open_paths():
    model = CopperModel(strip_geo(), 0.05)
    d = power_layout.geodesic_mm(model, "N", ["F.Cu"], ["R1.1"], ["R1.2"], stack(["F.Cu"]))
    assert d == pytest.approx(8.0, abs=0.1)
    geo = strip_geo()
    geo["polys"][0]["polys"] = [rect(0, 0, 4, 1), rect(6, 0, 10, 1)]
    assert power_layout.geodesic_mm(CopperModel(geo, 0.05), "N", ["F.Cu"], ["R1.1"], ["R1.2"],
                                    stack(["F.Cu"])) == float("inf")


def test_ground_offset_setpoint_error_sign_and_size():
    params = {"components": {"fb_divider": {"r_top_ohm": 6650, "r_bot_ohm": 10000},
                             "shunt": {"r_ohm": 0.010}, "csa": {"gain": 50}},
              "current": {"i_set_a": 4.0}}
    k = 10000 / 16650
    # quiet grounds 1 mV below AGND: FB reads low, the loop raises the current by 1 mV / (k * 0.5 V/A)
    res = power_layout.setpoint_error(params, {"U2.1": -1000.0, "R9.2": -1000.0})
    assert res["delta_i_ma"] == pytest.approx(1.0 / (k * 0.5), rel=1e-3)
    assert res["delta_pct"] > 0
    assert power_layout.setpoint_error(params, {}) == {}


def test_unconnected_power_path_is_reported_not_invented():
    paths_ = [{"net": "VOUT", "what": "x", "terminals": {}, "error": "terminal src is not connected"}]
    gnd = {"net": "GND", "error": "not solved"}
    f, comp = power_layout.findings(paths_, gnd, {"nominal": {}}, {}, {}, [], [], {"pairing": {}})
    ids = {x["id"] for x in f}
    assert {"CONNECT-VOUT", "CONNECT-GND"} <= ids
    assert "incomplete" in comp
