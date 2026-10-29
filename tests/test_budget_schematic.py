"""Budget-2s connectivity and schematic evidence stay consistent and separate from A/B."""
from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import evidence, paths, spec  # noqa: E402
from nubm44.variants import sources_for  # noqa: E402

CONNECTIVITY = sources_for("budget-2s").connectivity


def kicad_available() -> bool:
    try:
        return paths.kicad_symbols_dir().is_dir()
    except Exception:  # KiCad absent (e.g. Linux CI)
        return False


@pytest.fixture(scope="module")
def parts():
    return yaml.safe_load(CONNECTIVITY.read_text(encoding="utf-8"))["parts"]


def test_budget_connectivity_is_separate_from_ab():
    assert CONNECTIVITY != spec.SPEC and "budget-2s" in CONNECTIVITY.parts
    assert spec.VARIANTS == ("compact-22mm", "evaluation-board")


def test_refs_unique_and_every_net_connects_two_pins(parts):
    refs = [p["ref"] for p in parts]
    assert len(refs) == len(set(refs))
    nets = collections.Counter(net for p in parts for net in p["pins"].values() if net != "NC")
    lonely = sorted(n for n, k in nets.items() if k < 2)
    assert not lonely, f"single-pin nets: {lonely}"


def test_safety_critical_nets_match_the_design_decisions(parts):
    by_ref = {p["ref"]: p for p in parts}
    # DD-32: both outputs need ARM_Q and nFAULT through series pairs.
    assert by_ref["Q4"]["pins"][1] == "nFAULT" and by_ref["Q6"]["pins"][1] == "nFAULT"
    assert by_ref["R18"]["pins"][1] == by_ref["R20"]["pins"][1] == "ARM_Q"
    assert by_ref["U6"]["pins"][1] == "nFAULT"  # latch CLR
    assert by_ref["R24"]["pins"] == {1: "EN", 2: "GND"}  # EN default-off pulldown
    # DD-33/34 values follow the parameter source.
    params = yaml.safe_load(sources_for("budget-2s").parameters.read_text(encoding="utf-8"))
    assert by_ref["R5"]["value"] == f"{params['current_sense']['fb_top_ohm'] / 1000:g}k"
    assert by_ref["R7"]["value"] == f"{params['backup']['limit_resistor_ohm'] / 1000:g}k"
    assert by_ref["Q2"]["mpn"] == params["disconnect"]["selected_output_mpn"]
    assert by_ref["RS1"]["mpn"] == params["current_sense"]["shunt_mpn"]
    assert by_ref["D3"]["mpn"] == params["disconnect"]["gate_clamp_mpn"]


@pytest.mark.skipif(not kicad_available(), reason="KiCad libraries not installed")
def test_every_pin_exists_on_its_symbol_and_stock_footprints_exist(parts):
    from nubm44 import kicad_lib
    for p in parts:
        sym_pins = set(kicad_lib.symbol_pins(kicad_lib.get_symbol(p["lib"])))
        assert {str(n) for n in p["pins"]} == sym_pins, p["ref"]
        if not p["footprint"].startswith(kicad_lib.BUDGET_LIB + ":"):
            assert kicad_lib.footprint_path(p["footprint"]).exists(), p["footprint"]


def test_schematic_evidence_when_present_is_current_and_passing():
    summary = ROOT / "reports/budget-2s/schematic.json"
    manifest = ROOT / "reports/budget-2s/schematic-evidence.json"
    if not summary.exists():
        pytest.skip("budget schematic not generated")
    assert not evidence.problems(evidence.load(manifest), expected_kind="budget-schematic")
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["status"] == "PASS" and data["erc_errors"] == 0 and not data["connectivity_differences"]
    # Only missing project footprints may warn.
    assert all(v["type"] == "footprint_link_issues" for v in data["erc_violations"])


def test_budget_layout_wraps_wide_blocks():
    module_spec = importlib.util.spec_from_file_location("budget_sch", ROOT / "automation/budget/build_schematic.py")
    if not kicad_available():
        pytest.skip("KiCad libraries not installed")
    budget = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(budget)
    enable = [p for p in budget.load_spec()["parts"] if p["block"] == "enable"]
    assert budget.layout_block("enable", enable)["w"] < budget.ab.layout_block("enable", enable)["w"] / 2
