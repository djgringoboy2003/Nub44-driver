"""Evidence binding, known-limitation classification, incomplete-board marking and release readiness."""
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import evidence  # noqa: E402
from export import release_check  # noqa: E402


@pytest.fixture
def validation(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("validation_evidence_test", ROOT / "automation/validation/validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "REP", tmp_path / "reports")
    monkeypatch.setattr(module.paths, "HARDWARE", tmp_path / "hardware")
    monkeypatch.setattr(module.paths, "MANUFACTURING", tmp_path / "manufacturing")
    module.REP.mkdir()
    module.entries.clear()
    return module


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


CHECKS = [{"check": "Setpoint tolerance", "value": 3.58, "limit": 5.0, "kind": "max", "unit": "%", "status": "PASS"},
          {"check": "Efficiency", "value": 94.6, "limit": 94.0, "kind": "min", "unit": "%", "status": "PASS"}]


def calc_fixture(root: Path, checks=CHECKS):
    params = write(root / "engineering/design/parameters.yaml", "current: {i_set_a: 4.0}\n")
    script = write(root / "engineering/calculations/power_stage.py", "# calc\n")
    results = write(root / "engineering/calculations/power-stage-results.json", json.dumps({"checks": checks}))
    manifest = evidence.build("calculation", [params, script], [results], {"python": "3.11"}, root=root,
                              check_names=[c["check"] for c in checks])
    evidence.write(manifest, root / "engineering/calculations/power-stage-evidence.json")
    return params, results


def sim_fixture(root: Path, results=None):
    params = root / "engineering/design/parameters.yaml"
    if not params.exists():
        write(params, "current: {i_set_a: 4.0}\n")
    script = write(root / "simulation/run_sims.py", "# sims\n")
    results = results if results is not None else [
        {"id": f"SIM-{i:02d}", "name": f"sim {i}", "metrics": {"x": 1.0}, "limit": "", "pass": True, "status": "PASS"}
        for i in range(1, 12)]
    out = write(root / "simulation/results/results.json", json.dumps(results))
    evidence.write(evidence.build("simulation", [params, script], [out], {"ngspice": "ngspice-47"}, root=root,
                                  simulation_ids=[f"SIM-{i:02d}" for i in range(1, 12)]),
                   root / "simulation/results/evidence.json")
    return out


def status(v, eid):
    return next(e["status"] for e in v.entries if e["id"] == eid)


# ------------------------------------------------------------------ calculation evidence
def test_current_calculation_evidence_passes_and_rejudges_each_check(validation):
    calc_fixture(validation.ROOT)
    validation.calculations()
    assert status(validation, "VAL-CALC-EVID") == "PASS"
    assert status(validation, "VAL-CALC-01") == "PASS" and status(validation, "VAL-CALC-02") == "PASS"


def test_parameter_change_makes_calculations_stale(validation):
    params, _ = calc_fixture(validation.ROOT)
    params.write_text("current: {i_set_a: 3.5}\n", encoding="utf-8")
    validation.calculations()
    assert status(validation, "VAL-CALC-EVID") == "FAIL"
    assert not any(e["id"] == "VAL-CALC-01" for e in validation.entries), "stale values must not be reported as checks"


def test_contradictory_saved_status_fails(validation):
    bad = [dict(CHECKS[0], value=7.0)]               # 7 % > 5 % limit but saved as PASS
    calc_fixture(validation.ROOT, bad)
    validation.calculations()
    assert status(validation, "VAL-CALC-01") == "FAIL"


def test_edited_results_without_manifest_update_fail(validation):
    _, results = calc_fixture(validation.ROOT)
    results.write_text(json.dumps({"checks": [dict(CHECKS[0], status="PASS", value=1.0)]}), encoding="utf-8")
    validation.calculations()
    assert status(validation, "VAL-CALC-EVID") == "FAIL"


@pytest.mark.parametrize("content", ["not json", json.dumps({"checks": "none"}), json.dumps([1, 2])])
def test_malformed_calculation_results_fail_without_crashing(validation, content):
    calc_fixture(validation.ROOT)
    (validation.ROOT / "engineering/calculations/power-stage-results.json").write_text(content, encoding="utf-8")
    validation.calculations()
    assert status(validation, "VAL-CALC-EVID") == "FAIL"


def test_missing_calculation_evidence_is_not_run(validation):
    validation.calculations()
    assert status(validation, "VAL-CALC-EVID") == "NOT RUN"


# ------------------------------------------------------------------ simulation evidence
def test_current_simulation_evidence_passes(validation):
    sim_fixture(validation.ROOT)
    validation.simulation()
    assert status(validation, "VAL-SIM-EVID") == "PASS"
    assert all(status(validation, f"VAL-SIM-{i:02d}") == "PASS" for i in range(1, 12))


def test_simulation_script_change_makes_results_stale(validation):
    sim_fixture(validation.ROOT)
    (validation.ROOT / "simulation/run_sims.py").write_text("# changed model\n", encoding="utf-8")
    validation.simulation()
    assert status(validation, "VAL-SIM-EVID") == "FAIL"
    assert validation.gates([])["C"] == "OPEN"


def test_missing_and_contradictory_simulation_results(validation):
    results = [{"id": f"SIM-{i:02d}", "name": "s", "metrics": {}, "limit": "", "pass": i != 3, "status": "PASS"}
               for i in range(1, 11)]                # SIM-11 missing, SIM-03 claims PASS with pass False
    sim_fixture(validation.ROOT, results)
    validation.simulation()
    assert status(validation, "VAL-SIM-11") == "NOT RUN"
    assert status(validation, "VAL-SIM-03") == "FAIL"
    assert validation.gates([])["C"] == "OPEN"


# ------------------------------------------------------------------ known limitations and exit code
def known_file(root: Path, accepted=(), pending=()):
    write(root / "engineering/known-limitations.yaml",
          yaml.safe_dump({"accepted": list(accepted), "pending_disposition": list(pending)}))


def test_unchanged_known_limitation_is_classified_known(validation):
    known_file(validation.ROOT, accepted=[{"id": "VAL-ROUTE-compact-22mm", "status": "FAIL",
                                           "detail": "20 unconnected items", "reason": "parked", "decision": "DD-27"}])
    validation.add("VAL-ROUTE-compact-22mm", "routed", "CAD", "FAIL", "", "20 unconnected items")
    cls = validation.classify(validation.load_known())
    assert [e["id"] for e in cls["known"]] == ["VAL-ROUTE-compact-22mm"] and not cls["new"] and not cls["changed"]


@pytest.mark.parametrize("detail", ["21 unconnected items", "19 unconnected items"])
def test_known_limitation_that_changes_is_reported(validation, detail):
    known_file(validation.ROOT, accepted=[{"id": "VAL-ROUTE-compact-22mm", "status": "FAIL",
                                           "detail": "20 unconnected items"}])
    validation.add("VAL-ROUTE-compact-22mm", "routed", "CAD", "FAIL", "", detail)
    assert [e["id"] for e in validation.classify(validation.load_known())["changed"]] == ["VAL-ROUTE-compact-22mm"]


def test_new_failure_is_never_hidden_by_the_baseline(validation):
    known_file(validation.ROOT)
    validation.add("VAL-DRC-evaluation-board", "drc", "CAD", "FAIL", "", "1 errors")
    assert [e["id"] for e in validation.classify(validation.load_known())["new"]] == ["VAL-DRC-evaluation-board"]


def test_resolved_known_limitation_is_flagged(validation):
    known_file(validation.ROOT, accepted=[{"id": "VAL-ROUTE-compact-22mm", "status": "FAIL", "detail": "x"}])
    validation.add("VAL-ROUTE-compact-22mm", "routed", "CAD", "PASS", "", "0 unconnected items")
    assert [k["id"] for k in validation.classify(validation.load_known())["resolved"]] == ["VAL-ROUTE-compact-22mm"]


def test_repository_baseline_is_well_formed():
    data = yaml.safe_load((ROOT / "engineering/known-limitations.yaml").read_text(encoding="utf-8"))
    for item in data["accepted"]:
        assert item["id"].startswith("VAL-") and item["status"] in ("FAIL", "NOT RUN") and item.get("decision")
        assert ("detail" in item) != ("detail_contains" in item)
    for item in data["pending_disposition"]:
        assert item["id"].startswith("VAL-") and item.get("finding") and item.get("reason")


# ------------------------------------------------------------------ Gate G and readiness
def test_gate_g_needs_bench_evidence(validation):
    assert validation.gate_g().startswith("OPEN")
    write(validation.REP / "bench-summary.json", json.dumps({"variants": {"evaluation-board": {"gate_g": "PASS"}}}))
    assert validation.gate_g().startswith("OPEN"), "one board's bench data does not close Gate G for both"


def passing(variant):
    ids = [f"VAL-{c}-{variant}" for c in release_check.CAD_CHECKS] + list(release_check.COMMON_CHECKS)
    ids += list(release_check.SIM_GATE_IDS) + ["VAL-CALC-01"]
    return [{"id": i, "status": "PASS", "detail": ""} for i in ids]


def reviews(root: Path, done: bool):
    data = yaml.safe_load((ROOT / "engineering/release/design-reviews.yaml").read_text(encoding="utf-8"))
    for r in data["reviews"]:
        # Test states must not depend on which real reviews the owner has completed.
        r.update(status="OPEN", reviewer=None, date=None, evidence=None)
        if done and r["level"] == "PROTOTYPE_CANDIDATE":
            r.update(status="DONE", reviewer="reviewer", date="2026-10-27", evidence="compared drawing rev X")
    write(root / "engineering/release/design-reviews.yaml", yaml.safe_dump(data))


def test_readiness_levels_follow_the_evidence(tmp_path):
    v = "evaluation-board"
    reviews(tmp_path, done=False)
    r = release_check.readiness(v, passing(v), tmp_path, [])
    assert r["level"] == "DRAFT_REVIEW" and any("FP-U1" in b for b in r["blockers"]["PROTOTYPE_CANDIDATE"])
    reviews(tmp_path, done=True)
    r = release_check.readiness(v, passing(v), tmp_path, ["VAL-SIM-12"])
    assert r["level"] == "PROTOTYPE_CANDIDATE" and r["manufacturing_release"] is False
    blockers = " ".join(r["blockers"]["MANUFACTURING_RELEASE"])
    assert "bench" in blockers and "VAL-SIM-12" in blockers and "approval" in blockers
    entries = [e for e in passing(v) if e["id"] != "VAL-ROUTE-" + v] + [{"id": "VAL-ROUTE-" + v, "status": "FAIL",
                                                                         "detail": "3 unconnected items"}]
    assert release_check.readiness(v, entries, tmp_path, [])["level"] == "DRAFT_REVIEW"
    entries = [e for e in passing(v) if e["id"] != "VAL-EXPORT-" + v]
    assert release_check.readiness(v, entries, tmp_path, [])["level"] == "NONE"


def test_manufacturing_release_needs_matching_approval_and_bench(tmp_path):
    v = "evaluation-board"
    reviews(tmp_path, done=True)
    data = yaml.safe_load((tmp_path / "engineering/release/design-reviews.yaml").read_text(encoding="utf-8"))
    for r in data["reviews"]:
        r.update(status="DONE", reviewer="r", date="2026-10-27", evidence="e")
    write(tmp_path / "engineering/release/design-reviews.yaml", yaml.safe_dump(data))
    pkg = tmp_path / "manufacturing/pcbway" / v
    zipped = write(pkg / f"{v}-gerbers.zip", "zip")
    bom, cpl = write(pkg / "assembly/BOM_PCBWay_template.csv", "bom"), write(pkg / "assembly/CPL_PCBWay.csv", "cpl")
    write(tmp_path / "reports/bench-summary.json", json.dumps({"variants": {v: {"gate_g": "PASS"}}}))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    approval = {"approver": "owner", "date": "2026-11-01", "level": "MANUFACTURING_RELEASE", "git_commit": "abc",
                "gerber_zip_sha256": sha(zipped), "bom_sha256": sha(bom), "cpl_sha256": sha(cpl)}
    write(tmp_path / f"manufacturing/approvals/{v}.yaml", yaml.safe_dump(approval))
    assert release_check.readiness(v, passing(v), tmp_path, [])["level"] == "MANUFACTURING_RELEASE"
    zipped.write_text("regenerated zip", encoding="utf-8")
    r = release_check.readiness(v, passing(v), tmp_path, [])
    assert r["level"] == "PROTOTYPE_CANDIDATE" and any("gerber_zip_sha256" in b for b in r["blockers"]["MANUFACTURING_RELEASE"])


# ------------------------------------------------------------------ incomplete-board marker
def test_incomplete_board_export_must_carry_the_marker(validation):
    variant = "compact-22mm"
    write(validation.REP / f"drc-{variant}.json", json.dumps({"violations": [], "unconnected_items": [{"x": 1}],
                                                               "schematic_parity": []}))
    pkg = validation.paths.MANUFACTURING / "pcbway" / variant
    pkg.mkdir(parents=True)
    with zipfile.ZipFile(pkg / f"{variant}-gerbers.zip", "w") as z:
        z.writestr("gerbers/a.gtl", "g")
    problems = validation.incomplete_marker_problems(variant, pkg, {"package_class": "DRAFT_REVIEW"})
    assert len(problems) == 2
    with zipfile.ZipFile(pkg / f"{variant}-gerbers.zip", "w") as z:
        z.writestr("DO_NOT_FABRICATE.txt", "no")
    assert not validation.incomplete_marker_problems(variant, pkg, {"package_class": "DRAFT_REVIEW_INCOMPLETE_BOARD"})


# ------------------------------------------------------------------ schematic evidence (AUD-VAL-08)
def schematic_fixture(v, variant="evaluation-board"):
    root = v.ROOT
    conn = write(root / "engineering/design/connectivity.yaml", "parts: []\n")
    params = write(root / "engineering/design/parameters.yaml", "current: {i_set_a: 4.0}\n")
    sch = write(v.paths.HARDWARE / variant / "nubm44_driver.kicad_sch", "(kicad_sch)")
    net = write(sch.with_suffix(".net"), "(export)")
    erc = write(v.REP / f"erc-{variant}.json", json.dumps({
        "$schema": "https://schemas.kicad.org/erc.v1.json", "source": "nubm44_driver.kicad_sch",
        "included_severities": ["error", "warning", "exclusion"], "sheets": [{"violations": []}]}))
    summary = write(v.REP / f"schematic-{variant}.json", json.dumps({
        "variant": variant, "schematic": f"hardware/{variant}/nubm44_driver.kicad_sch", "upgrade_rc": 0,
        "erc_errors": 0, "erc_warnings": 0, "netlist_parts": 5, "netlist_nets": 4, "connectivity_differences": []}))
    evidence.write(evidence.build("schematic", [conn, params], [sch, net, erc, summary], {"kicad-cli": "10.0.6"},
                                  root=root), v.REP / f"schematic-{variant}-evidence.json")
    return conn


def test_schematic_evidence_is_hash_bound(validation):
    conn = schematic_fixture(validation)
    validation.schematic("evaluation-board")
    assert status(validation, "VAL-ERC-evaluation-board") == "PASS"
    validation.entries.clear()
    conn.write_text("parts: [changed]\n", encoding="utf-8")
    import os
    os.utime(conn, (1, 1))                       # an old mtime must not hide the change
    validation.schematic("evaluation-board")
    assert status(validation, "VAL-ERC-evaluation-board") == "FAIL"
