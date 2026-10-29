"""Budget qualification must expose uncertainty and remain separate from A/B."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import evidence, spec  # noqa: E402
from nubm44.variants import ALL_VARIANTS, LEGACY_VARIANTS, sources_for  # noqa: E402

module_spec = importlib.util.spec_from_file_location("budget_qualify", ROOT / "automation/budget/qualify.py")
qualify = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(qualify)


@pytest.fixture
def params():
    return yaml.safe_load(qualify.PARAMETERS.read_text(encoding="utf-8"))


def test_variant_paths_cannot_inherit_1s_sources():
    a = sources_for("compact-22mm")
    b = sources_for("evaluation-board")
    c = sources_for("budget-2s")
    assert a.parameters == b.parameters
    assert a.connectivity == b.connectivity
    assert c.parameters != a.parameters
    assert c.connectivity != a.connectivity
    assert "budget-2s" in c.parameters.parts
    assert c.placement.parent.name == "budget-2s"
    assert set(ALL_VARIANTS) == {*LEGACY_VARIANTS, "budget-2s"}
    # The old full validator still covers only A/B; it must not award budget gates.
    assert spec.VARIANTS == LEGACY_VARIANTS
    with pytest.raises(ValueError, match="unknown variant"):
        sources_for("budget-2s-typo")
    with pytest.raises(ValueError, match="unknown variant"):
        spec.parts_for("budget-2s")


def test_candidate_current_envelope_is_conditional(params):
    r = qualify.calculate(params)
    assert r["current"]["nominal_a"] == pytest.approx(3.984)
    assert 3.8 <= r["current"]["min_a"] < r["current"]["max_a"] <= 4.2
    assert r["current"]["conditional_accuracy_ok"]
    assert not r["manufacturing_ready"]
    assert r["readiness"][0]["status"] == "CONDITIONAL"
    assert "current_sense.fb_resistor_mpns" in r["unknown_inputs"]
    assert not any(x["status"] == "PASS" for x in r["readiness"])


def test_wrong_divider_or_shunt_does_not_pass_current_screen(params):
    for section, key, factor in [("current_sense", "shunt_ohm", 0.5),
                                  ("current_sense", "fb_top_ohm", 2)]:
        p = copy.deepcopy(params)
        p[section][key] *= factor
        r = qualify.calculate(p)
        assert not r["current"]["conditional_accuracy_ok"]
        assert r["readiness"][0]["status"] == "FAIL"


def test_all_error_terms_widen_envelope(params):
    base = qualify.current_bounds(params)
    p = copy.deepcopy(params)
    p["current_sense"]["shunt_delta_c_from_25"] *= 4
    hot = qualify.current_bounds(p)
    assert hot["min_a"] < base["min_a"]
    assert hot["max_a"] > base["max_a"]
    p["buck"]["reference_v_min"] *= 0.98
    p["buck"]["reference_v_max"] *= 1.02
    wide = qualify.current_bounds(p)
    assert wide["min_a"] < hot["min_a"]
    assert wide["max_a"] > hot["max_a"]


def test_backup_fast_mode_includes_naf_and_cannot_be_disabled_by_mcu(params):
    r = qualify.calculate(params)["backup"]
    assert r["nominal_a"] == pytest.approx(4.99)
    assert 4.8 <= r["min_a"] < r["max_a"] <= 5.2
    assert r["total_shutdown_s_max"] == "UNKNOWN"
    for key, bad in [("noise_adjustment_v", 0), ("enable", "MCU_ENABLE"),
                      ("latch", "LOW"), ("delay", "GND")]:
        p = copy.deepcopy(params)
        p["backup"][key] = bad
        with pytest.raises(ValueError):
            qualify.calculate(p)


def test_uvlo_incompatibility_and_efficiency_risk_remain_visible(params):
    r = qualify.calculate(params)
    assert r["voltage_monitor"]["uv"]["max_v"] > params["targets"]["input_v_min"]
    screens = r["loss_screens"]
    assert len(screens) == 6
    assert any(x["remaining_for_switching_core_copper_w_typ_buck"] < 0 for x in screens)
    assert "efficiency" not in r  # No invented complete efficiency percentage.
    for vf in (3.8, 4.5, 5.2):
        rows = [x for x in screens if x["vf_v"] == vf]
        assert rows[1]["external_screen_w"] < rows[0]["external_screen_w"]


def test_ripple_uses_guaranteed_frequency_minimum_not_nominal(params):
    r = qualify.ripple(params)
    assert r["ripple_a_pp_global_bound"] == pytest.approx(8.4 / (4 * 4.7e-6 * 0.8 * 400000))
    p = copy.deepcopy(params)
    p["buck"]["frequency_hz_min"] /= 2
    assert qualify.ripple(p)["ripple_a_pp_global_bound"] == pytest.approx(2 * r["ripple_a_pp_global_bound"])
    assert r["catalogue_isat_above_switch_limit"]
    assert params["inductor"]["minimum_l_h_hot_biased"] == "UNKNOWN"


def test_cap_energy_and_bleed_time_scale_with_capacitance(params):
    r = qualify.calculate(params)
    p = copy.deepcopy(params)
    p["output_energy"]["bulk_cap_f_max_analysis"] *= 2
    bigger = qualify.calculate(p)
    for key in ("upstream_j_at_ov_max", "upstream_j_at_switch_short_8p4v", "bleed_s_to_target_from_ov_max"):
        assert bigger["energy"][key] == pytest.approx(2 * r["energy"][key])
    assert r["energy"]["laser_side_j_cap_only_at_ov_max"] < r["energy"]["upstream_j_at_ov_max"]


@pytest.mark.parametrize("bad", ["UNKNOWN", True, float("nan"), float("inf"), 0, -1])
def test_invalid_numeric_inputs_do_not_produce_evidence(params, bad):
    params["current_sense"]["shunt_ohm"] = bad
    with pytest.raises(ValueError):
        qualify.calculate(params)


def test_invalid_candidate_invalidates_previous_manifest(tmp_path, monkeypatch):
    p = tmp_path / "parameters.yaml"
    p.write_text("schema: wrong\n", encoding="utf-8")
    out = tmp_path / "reports"
    out.mkdir()
    old = out / "qualification-evidence.json"
    old.write_text('{"schema":"old-pass"}', encoding="utf-8")
    monkeypatch.setattr(qualify, "PARAMETERS", p)
    monkeypatch.setattr(qualify, "OUT", out)
    assert qualify.main([]) == 2
    assert not old.exists()


def test_unknowns_survive_json_and_no_bench_values_are_created(params):
    r = qualify.calculate(params)
    restored = json.loads(json.dumps(r, allow_nan=False))
    assert restored["backup"]["total_shutdown_s_max"] == "UNKNOWN"
    assert "MEASURED" not in json.dumps(restored)
    g = next(x for x in restored["readiness"] if x["id"] == "BUD-G-01")
    assert g["status"] == "OPEN"


def test_hash_evidence_detects_changed_budget_source(tmp_path):
    source = tmp_path / "parameters.yaml"
    output = tmp_path / "qualification.json"
    source.write_text("shunt: 0.010\n", encoding="utf-8")
    output.write_text('{}\n', encoding="utf-8")
    manifest = evidence.build("budget-qualification", [source], [output], {"test": "1"}, root=tmp_path)
    assert not evidence.problems(manifest, root=tmp_path, expected_kind="budget-qualification")
    source.write_text("shunt: 0.005\n", encoding="utf-8")
    assert any("stale evidence" in x for x in evidence.problems(manifest, root=tmp_path))
