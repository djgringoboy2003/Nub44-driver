"""Budget-2s placement source stays consistent with its connectivity and design decisions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import evidence  # noqa: E402
from nubm44.variants import sources_for  # noqa: E402

SRC = sources_for("budget-2s")
PLACE = yaml.safe_load(SRC.placement.read_text(encoding="utf-8"))
PARTS = {p["ref"]: p for p in yaml.safe_load(SRC.connectivity.read_text(encoding="utf-8"))["parts"]}


def test_every_part_has_exactly_one_placement_entry():
    assert set(PLACE["parts"]) == set(PARTS)


def test_manual_positions_and_pours_lie_inside_the_board():
    w, h = PLACE["board"]["outline"]["w"] / 2, PLACE["board"]["outline"]["h"] / 2
    for ref, cfg in PLACE["parts"].items():
        x, y = (cfg["pos"][:2] if "pos" in cfg else cfg["auto"]["anchor"])
        assert abs(x) < w and abs(y) < h, ref
    for z in PLACE["zones_pre"] + PLACE["zones_post"]:
        assert all(abs(x) <= w + 0.6 and abs(y) <= h + 0.6 for x, y in z["polygon"]), z["net"]


def test_kelvin_traces_start_on_the_shunt_pads_and_carry_the_right_nets():
    rs1 = PLACE["parts"]["RS1"]["pos"]
    pad1, pad2 = (rs1[0] - 2.96, rs1[1]), (rs1[0] + 2.96, rs1[1])  # R_2512_6332Metric pads, 1.23 x 3.35 mm
    first = {}
    for t in PLACE["tracks"]:
        if "kelvin" in t:
            first.setdefault((t["kelvin"], t["net"]), t)  # a chain starts with its first listed segment
    # separate pairs for INA186 (U2) and INA300 (U3)
    assert set(first) == {(u, n) for u in ("U2", "U3") for n in ("VBUCK", "VSH")}
    for (_, net), t in first.items():
        cx, cy = pad1 if net == "VBUCK" else pad2
        sx, sy = t["pts"][0]
        assert abs(sx - cx) <= 0.615 and abs(sy - cy) <= 1.675, t
    assert {PARTS["U2"]["pins"][4], PARTS["U2"]["pins"][5]} == {"VBUCK", "VSH"}
    assert {PARTS["U3"]["pins"][1], PARTS["U3"]["pins"][2]} == {"VBUCK", "VSH"}


def test_battery_polarity_text_is_beside_the_matching_xt30_pad():
    x, y, rot = PLACE["parts"]["J1"]["pos"]
    assert rot == 90 and PARTS["J1"]["pins"] == {1: "GND", 2: "VBAT_IN"}
    pad2_y = y + 5.0  # footprint pad 2 at (-5, 0) rotated 90 degrees counter-clockwise
    texts = {t["text"]: t["at"] for t in PLACE["texts"]}
    assert abs(texts["B+"][1] - pad2_y) < abs(texts["B-"][1] - pad2_y)


def test_u1_paste_apertures_keep_clear_of_the_thermal_via_drills():
    import importlib.util  # by path: automation/setup/build_library.py (A/B) shares the module name
    spec = importlib.util.spec_from_file_location("budget_build_library", ROOT / "automation/budget/build_library.py")
    build_library = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_library)
    fp = build_library.tps54821_rhl0014a()
    pads = [n for n in fp if isinstance(n, list) and n and str(n[0]) == "pad"]
    drills = [next(float(c[1]) for c in p if isinstance(c, list) and str(c[0]) == "drill") for p in pads
              if str(p[2]) == "thru_hole"]
    vias = [next((float(c[1]), float(c[2])) for c in p if isinstance(c, list) and str(c[0]) == "at") for p in pads
            if str(p[2]) == "thru_hole"]
    paste = []
    for p in pads:
        layers = next(c for c in p if isinstance(c, list) and str(c[0]) == "layers")
        if [str(x) for x in layers[1:]] == ["F.Paste"]:
            at = next(c for c in p if isinstance(c, list) and str(c[0]) == "at")
            size = next(c for c in p if isinstance(c, list) and str(c[0]) == "size")
            paste.append((float(at[1]), float(at[2]), float(size[1]), float(size[2])))
    assert len(vias) == 5 and len(paste) == 8
    for (vx, vy), d in zip(vias, drills):
        for x, y, w, h in paste:  # distance from the drill centre to the nearest point of the aperture
            dx, dy = max(abs(vx - x) - w / 2, 0.0), max(abs(vy - y) - h / 2, 0.0)
            assert (dx * dx + dy * dy) ** 0.5 >= d / 2 + 0.05 - 1e-9, ((vx, vy), (x, y))


def test_layout_review_when_present_is_current_and_within_allocation():
    ev = ROOT / "reports/budget-2s/layout-review-evidence.json"
    if not ev.exists():
        pytest.skip("budget layout review not run")
    assert not evidence.problems(evidence.load(ev), expected_kind="budget-layout-review")
    s = json.loads((ROOT / "reports/budget-2s/layout-review.json").read_text(encoding="utf-8"))["summary"]
    assert s["output_ok"] and s["input_ok"]


def test_bom_never_merges_different_tolerances_or_part_types():
    bom = ROOT / "manufacturing/budget-2s/assembly/BOM.csv"
    if not bom.exists():
        pytest.skip("budget export not run")
    import csv
    rows = list(csv.DictReader(bom.read_text(encoding="utf-8-sig").splitlines()))
    for r in rows:
        notes = r["Requirement / notes"]
        assert not ("0.1%" in notes and " 1% " in notes), r["Designators"]
        refs = r["Designators"].split(",")
        assert not ({"TH1"} & set(refs) and len(refs) > 1), r["Designators"]
    placed = {ref for r in rows for ref in r["Designators"].split(",")}
    assert placed == {ref for ref, p in PARTS.items() if p.get("in_bom", True)}


def test_every_bom_part_has_an_mpn_and_exactly_one_sourcing_entry():
    import re
    sourcing = yaml.safe_load((ROOT / "engineering/design/budget-2s/sourcing.yaml").read_text(encoding="utf-8"))
    bom = {p["ref"]: p for p in PARTS.values() if p.get("in_bom", True)}
    assert not [r for r, p in bom.items() if str(p.get("mpn", "UNKNOWN")) in ("", "UNKNOWN")]
    entries = {str(m): c for m, c in sourcing["parts"].items()}
    assert set(entries) == {str(p["mpn"]) for p in bom.values()}
    for mpn, c in entries.items():
        assert c.get("evidence"), mpn
        assert c["lcsc"] == "UNKNOWN" or re.fullmatch(r"C\d+", c["lcsc"]), mpn
        assert c.get("jlc", "Basic") in ("Basic", "Extended"), mpn
        eq = c.get("lcsc_equivalent")
        if eq:  # only for a part LCSC does not list, and always with its own MPN, maker, code and evidence
            assert c["lcsc"] == "UNKNOWN" and eq["mpn"] != mpn and eq.get("mfr") and eq.get("evidence"), mpn
            assert re.fullmatch(r"C\d+", eq["lcsc"]), mpn
    # the 0.1 % / 25 ppm lines are never satisfied by Yageo RT/AT...BRE (+-50 ppm/C) parts, nor by their equivalents
    precision = [p for p in bom.values() if "0.1%" in p.get("desc", "")]
    chosen = [(p["ref"], m) for p in precision
              for m in (str(p["mpn"]), entries[str(p["mpn"])].get("lcsc_equivalent", {}).get("mpn", ""))]
    assert precision and not [c for c in chosen if re.match(r"(RT|AT)\d{4}BRE", c[1])]


def test_jlcpcb_bom_names_and_codes_the_lcsc_equivalent_never_the_unlisted_part():
    bom = ROOT / "manufacturing/budget-2s/assembly/BOM_JLCPCB.csv"
    if not bom.exists():
        pytest.skip("budget export not run")
    import csv
    sourcing = yaml.safe_load((ROOT / "engineering/design/budget-2s/sourcing.yaml").read_text(encoding="utf-8"))
    rows = {r["Designator"]: r for r in csv.DictReader(bom.read_text(encoding="utf-8-sig").splitlines())}
    checked = 0
    for mpn, c in sourcing["parts"].items():
        eq = c.get("lcsc_equivalent")
        refs = {r for r, p in PARTS.items() if str(p.get("mpn")) == str(mpn) and p.get("in_bom", True)}
        mine = [v for k, v in rows.items() if set(k.split(",")) <= refs]  # one MPN may span several BOM lines
        assert mine and {r for v in mine for r in v["Designator"].split(",")} == refs, mpn
        for row in mine:
            if eq:
                assert row["LCSC Part #"] == eq["lcsc"] and eq["mpn"] in row["Comment"], mpn
                assert str(mpn) not in row["Comment"], mpn
            else:
                assert row["LCSC Part #"] == ("" if c["lcsc"] == "UNKNOWN" else c["lcsc"]), mpn
        checked += bool(eq)
    assert checked == sum(1 for c in sourcing["parts"].values() if c.get("lcsc_equivalent"))


def test_drc_evidence_when_present_is_current():
    rep = ROOT / "reports/budget-2s/drc.json"
    ev = ROOT / "reports/budget-2s/drc-evidence.json"
    if not rep.exists():
        pytest.skip("budget board not routed")
    e = json.loads(ev.read_text(encoding="utf-8"))
    assert e["report_sha256"] == evidence.sha256_file(rep)
    for rel, digest in e["inputs"].items():
        assert evidence.sha256_file(ROOT / rel) == digest, rel
