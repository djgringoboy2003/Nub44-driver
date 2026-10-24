"""Release gates must reject incomplete, stale or misleading CAD evidence."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def validation(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "automation/validation/validate.py"
    spec = importlib.util.spec_from_file_location("validation_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "REP", tmp_path / "reports")
    monkeypatch.setattr(module.paths, "HARDWARE", tmp_path / "hardware")
    monkeypatch.setattr(module.paths, "MANUFACTURING", tmp_path / "manufacturing")
    module.REP.mkdir()
    return module


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def source_evidence(v, variant="compact-22mm"):
    inputs = {}
    for p in (v.paths.HARDWARE / variant / "placement.yaml", v.ROOT / "engineering/design/connectivity.yaml",
              v.ROOT / "engineering/design/parameters.yaml"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"original {p.name}", encoding="utf-8")
        inputs[p.relative_to(v.ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return inputs


def cad_evidence(v, variant="compact-22mm"):
    inputs = source_evidence(v, variant)
    for suffix in ("kicad_pcb", "kicad_sch", "kicad_pro"):
        p = v.paths.HARDWARE / variant / f"nubm44_driver.{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"original {suffix}", encoding="utf-8")
        inputs[p.relative_to(v.ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    report = v.REP / f"drc-{variant}.json"
    data = {"$schema": "https://schemas.kicad.org/drc.v1.json", "source": "nubm44_driver.kicad_pcb",
            "included_severities": ["error", "warning", "exclusion"],
            "ignored_checks": [], "violations": [], "unconnected_items": [], "schematic_parity": []}
    write_json(report, data)
    manifest = {"inputs": inputs, "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                "schematic_parity": True, "severity_all": True}
    write_json(v.REP / f"drc-{variant}-evidence.json", manifest)
    return report, data, manifest


def replace_drc(v, report, data, manifest):
    write_json(report, data)
    manifest["report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
    write_json(report.with_name(report.stem + "-evidence.json"), manifest)


def statuses(v):
    return {e["id"]: e["status"] for e in v.entries}


def passing_entries(v):
    ids = list(v.SIMULATION_IDS)
    ids += [f"VAL-{check}-{variant}" for variant in v.spec.VARIANTS
            for check in ("ERC", "NET", "ROUTE", "PARITY", "DRC", "EXPORT")]
    v.entries[:] = [{"id": key, "status": "PASS"} for key in ids]


@pytest.mark.parametrize("key", ["VAL-ROUTE-compact-22mm", "VAL-ERC-compact-22mm",
                                 "VAL-PARITY-compact-22mm", "VAL-DRC-compact-22mm"])
def test_unresolved_cad_checks_cannot_release_manufacturing(validation, key):
    v = validation
    passing_entries(v)
    next(e for e in v.entries if e["id"] == key)["status"] = "FAIL"
    gates = v.gates([])
    assert gates["E (compact-22mm)"] == "OPEN"
    assert gates["F (compact-22mm)"] == "OPEN"


@pytest.mark.parametrize("missing", ["VAL-NET-evaluation-board", "VAL-SIM-11"])
def test_missing_required_evidence_cannot_release_manufacturing(validation, missing):
    v = validation
    passing_entries(v)
    v.entries[:] = [e for e in v.entries if e["id"] != missing]
    assert v.gates([])["F (compact-22mm)"] == "OPEN"


def test_duplicate_simulation_result_cannot_hide_failure(validation):
    v = validation
    passing_entries(v)
    v.entries.insert(0, {"id": "VAL-SIM-01", "status": "FAIL"})
    assert v.gates([])["C"] == "OPEN"
    assert v.gates([])["F (compact-22mm)"] == "OPEN"


def test_owner_block_holds_otherwise_passing_release_and_bench_gate_stays_open(validation):
    v = validation
    passing_entries(v)
    assert v.gates([])["F (compact-22mm)"] == "PASS"
    assert v.gates(["REQ-BAT-04"])["F (compact-22mm)"].startswith("HELD")
    assert v.gates([])["G"].startswith("OPEN")


@pytest.mark.parametrize("data", [{}, {"violations": [], "unconnected_items": [], "schematic_parity": []}])
def test_incomplete_drc_objects_never_count_as_clean(validation, data):
    v = validation
    report, _, manifest = cad_evidence(v)
    replace_drc(v, report, data, manifest)
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


@pytest.mark.parametrize("field", ["violations", "unconnected_items", "schematic_parity"])
def test_omitting_a_drc_check_fails_closed(validation, field):
    v = validation
    report, data, manifest = cad_evidence(v)
    del data[field]
    replace_drc(v, report, data, manifest)
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


def test_warnings_remain_unresolved_drc_findings(validation):
    v = validation
    report, data, manifest = cad_evidence(v)
    data["violations"] = [{"type": "connection_width", "severity": "warning",
                           "description": "Copper connection is too narrow", "items": []}]
    replace_drc(v, report, data, manifest)
    v.drc("compact-22mm")
    assert statuses(v)["VAL-DRC-compact-22mm"] == "FAIL"


@pytest.mark.parametrize("ignored", ["clearance", "lib_footprint_mismatch"])
def test_disabled_drc_rules_require_explicit_allowed_documentation(validation, ignored):
    v = validation
    report, data, manifest = cad_evidence(v)
    data["ignored_checks"] = [{"key": ignored, "description": "disabled"}]
    replace_drc(v, report, data, manifest)
    v.drc("compact-22mm")
    assert statuses(v)["VAL-DRC-compact-22mm"] == "FAIL"


def test_documented_cosmetic_and_unused_feature_exceptions_are_reported(validation):
    v = validation
    report, data, manifest = cad_evidence(v)
    decisions = v.ROOT / "engineering/design-decisions.md"
    decisions.parent.mkdir(parents=True, exist_ok=True)
    decisions.write_text("## DD-20 DRC exceptions\nlib_footprint_mismatch: silkscreen removal.\n"
                         "tuning_profile_track_geometries: tuning not used.\n", encoding="utf-8")
    data["ignored_checks"] = [{"key": key, "description": "disabled"} for key in v.DRC_IGNORED_REASONS]
    replace_drc(v, report, data, manifest)
    v.drc("compact-22mm")
    assert statuses(v)["VAL-DRC-compact-22mm"] == "PASS"
    detail = next(e["detail"] for e in v.entries if e["id"] == "VAL-DRC-compact-22mm")
    assert "DD-20" in detail and "silkscreen" in detail


@pytest.mark.parametrize("suffix", ["kicad_pcb", "kicad_sch", "kicad_pro"])
def test_cad_edits_invalidate_prior_drc_even_with_old_mtime(validation, suffix):
    v = validation
    cad_evidence(v)
    p = v.paths.HARDWARE / "compact-22mm" / f"nubm44_driver.{suffix}"
    old = p.stat()
    p.write_text("changed after check", encoding="utf-8")
    os.utime(p, ns=(old.st_atime_ns, old.st_mtime_ns))
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


@pytest.mark.parametrize("source", ["hardware/compact-22mm/placement.yaml",
                                    "engineering/design/connectivity.yaml", "engineering/design/parameters.yaml"])
def test_source_edits_invalidate_drc_even_when_cad_and_mtime_do_not_change(validation, source):
    v = validation
    cad_evidence(v)
    path = v.ROOT / source
    original = path.stat()
    path.write_text("edited authoritative source", encoding="utf-8")
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


def test_drc_manifest_missing_placement_hash_fails_closed(validation):
    v = validation
    _, _, manifest = cad_evidence(v)
    del manifest["inputs"]["hardware/compact-22mm/placement.yaml"]
    write_json(v.REP / "drc-compact-22mm-evidence.json", manifest)
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


def test_drc_report_edit_invalidates_manifest(validation):
    v = validation
    report, _, _ = cad_evidence(v)
    report.write_text(report.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


def test_drc_requires_manifest_and_confirmation_of_parity_check(validation):
    v = validation
    _, _, manifest = cad_evidence(v)
    del manifest["schematic_parity"]
    evidence = v.REP / "drc-compact-22mm-evidence.json"
    write_json(evidence, manifest)
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}
    v.entries.clear()
    evidence.unlink()
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"FAIL"}


def test_complete_clean_drc_with_matching_inputs_passes(validation):
    v = validation
    cad_evidence(v)
    v.drc("compact-22mm")
    assert set(statuses(v).values()) == {"PASS"}


def test_newer_input_invalidates_legacy_report(validation):
    v = validation
    report = v.REP / "schematic.json"
    report.write_text("{}", encoding="utf-8")
    schematic = v.ROOT / "board.kicad_sch"
    schematic.write_text("changed", encoding="utf-8")
    newer = report.stat().st_mtime_ns + 1_000_000_000
    os.utime(schematic, ns=(newer, newer))
    assert v.freshness_problems(report, [schematic])


def test_malformed_schematic_summary_cannot_pass_electrical_gate(validation):
    v = validation
    write_json(v.REP / "schematic-compact-22mm.json", {})
    write_json(v.REP / "erc-compact-22mm.json", {})
    v.schematic("compact-22mm")
    assert statuses(v)["VAL-ERC-compact-22mm"] == "FAIL"
    assert statuses(v)["VAL-NET-compact-22mm"] == "FAIL"


def export_evidence(v):
    package = v.paths.MANUFACTURING / "pcbway/compact-22mm"
    data = {"variant": "compact-22mm", "status": "PASS", "problems": [], "inputs": source_evidence(v),
            "files": {}, "file_sha256": {}, "required_files": v.required_export_files("compact-22mm")}
    for suffix in ("kicad_pcb", "kicad_sch", "kicad_pro"):
        p = v.paths.HARDWARE / "compact-22mm" / f"nubm44_driver.{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("input", encoding="utf-8")
        data["inputs"][p.relative_to(v.ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    note = v.ROOT / "documentation/stack-up.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("stack-up note", encoding="utf-8")
    data["inputs"][note.relative_to(v.ROOT).as_posix()] = hashlib.sha256(note.read_bytes()).hexdigest()
    for rel in data["required_files"]:
        p = package / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("artifact", encoding="utf-8")
        data["files"][rel] = p.stat().st_size
        data["file_sha256"][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    report = package / "reports/export-check.json"
    write_json(report, data)
    return package, report, data


def test_export_gate_accepts_complete_hash_matched_package(validation):
    v = validation
    export_evidence(v)
    v.exports("compact-22mm")
    assert statuses(v)["VAL-EXPORT-compact-22mm"] == "PASS"


@pytest.mark.parametrize("source", ["hardware/compact-22mm/placement.yaml",
                                    "engineering/design/connectivity.yaml", "engineering/design/parameters.yaml"])
def test_source_edits_invalidate_export_even_when_cad_and_mtime_do_not_change(validation, source):
    v = validation
    export_evidence(v)
    path = v.ROOT / source
    original = path.stat()
    path.write_text("edited authoritative source", encoding="utf-8")
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    v.exports("compact-22mm")
    assert statuses(v)["VAL-EXPORT-compact-22mm"] == "FAIL"


def test_export_manifest_missing_placement_hash_fails_closed(validation):
    v = validation
    _, report, data = export_evidence(v)
    del data["inputs"]["hardware/compact-22mm/placement.yaml"]
    write_json(report, data)
    v.exports("compact-22mm")
    assert statuses(v)["VAL-EXPORT-compact-22mm"] == "FAIL"


@pytest.mark.parametrize("fault", ["modified_input", "modified_note", "modified_output", "missing_output", "omitted_layer", "path_escape"])
def test_export_gate_rejects_stale_or_incomplete_manifest(validation, fault):
    v = validation
    package, report, data = export_evidence(v)
    if fault == "modified_input":
        p = v.paths.HARDWARE / "compact-22mm/nubm44_driver.kicad_pcb"
        p.write_text("edited board", encoding="utf-8")
    elif fault == "modified_note":
        (v.ROOT / "documentation/stack-up.md").write_text("edited stack-up", encoding="utf-8")
    elif fault == "modified_output":
        (package / "assembly/CPL_PCBWay.csv").write_text("changed centroid", encoding="utf-8")
    elif fault == "missing_output":
        (package / "drawings/assembly_bottom.pdf").unlink()
    elif fault == "omitted_layer":
        data["required_files"].remove("gerbers/nubm44_driver-In1_Cu.g1")
    else:
        data["files"]["../../outside.txt"] = 1
    write_json(report, data)
    v.exports("compact-22mm")
    assert statuses(v)["VAL-EXPORT-compact-22mm"] == "FAIL"
