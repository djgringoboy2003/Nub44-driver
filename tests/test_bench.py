"""Bench recording framework. Every record here is SYNTHETIC test data in a temporary folder, used only to prove
that the framework accepts, rejects and judges records correctly; nothing is written to the project results."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bench(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("bench_under_test", ROOT / "automation/bench/bench.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(module, "REPORTS", tmp_path / "reports")
    return module


def record(bench, folder: Path, test_id, values, status="PASS", serial="EVB-001", variant="evaluation-board",
           conditions=None, origin="MEASURED", name=None):
    board = folder / serial
    (board / "raw").mkdir(parents=True, exist_ok=True)
    raw = board / "raw" / f"{test_id}.csv"
    raw.write_text("synthetic test data\n", encoding="utf-8")
    rec = {"schema": bench.SCHEMA, "test_id": test_id, "data_origin": origin,
           "board": {"serial": serial, "variant": variant, "hardware_revision": "A"},
           "firmware": {"revision": "abc123", "hex_sha256": "0" * 64}, "date": "2026-11-20", "operator": "tester",
           "instruments": [{"type": "DMM", "model": "model"}], "conditions": conditions or {},
           "measurements": values, "attachments": [{"path": f"raw/{test_id}.csv",
                                                    "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}],
           "status": status, "notes": "synthetic"}
    path = board / (name or f"{test_id}_2026-11-20_1.json")
    path.write_text(json.dumps(rec), encoding="utf-8")
    return path


def passing_values(test):
    out = []
    for q in test["quantities"]:
        if "equals" in q:
            v = q["equals"]
        elif "range" in q:
            v = sum(q["range"]) / 2
        elif "min" in q:
            v = q["min"] + 1
        elif "max" in q:
            v = q["max"] * 0.5
        else:
            v = 1.0
        out.append({"quantity": q["name"], "value": v, "unit": q["unit"], "conditions": q.get("when") or {}})
    return out


def test_catalogue_ids_exist_in_the_test_plan(bench):
    plan = (ROOT / "documentation/testing/test-plan.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"^\| (T\d+\.\d+) \|", plan, re.M))
    catalogue = bench.load_catalogue()
    assert set(catalogue) <= ids, set(catalogue) - ids
    for t in catalogue.values():
        assert t["quantities"] and set(t.get("gate_g") or []) <= set(bench.VARIANTS)


def test_valid_record_passes_and_contradiction_is_invalid(bench, tmp_path):
    cat = bench.load_catalogue()
    p = record(bench, tmp_path / "results", "T1.4", [{"quantity": "i_out_a", "value": 4.51, "unit": "A"}])
    assert bench.evaluate(p, cat)["status"] == "PASS"
    p = record(bench, tmp_path / "results", "T1.4", [{"quantity": "i_out_a", "value": 4.9, "unit": "A"}], name="b.json")
    r = bench.evaluate(p, cat)
    assert r["status"] == "INVALID" and "contradicts" in r["problems"][0]
    p = record(bench, tmp_path / "results", "T1.4", [{"quantity": "i_out_a", "value": 4.9, "unit": "A"}],
               status="FAIL", name="c.json")
    assert bench.evaluate(p, cat)["status"] == "FAIL"


@pytest.mark.parametrize("origin", ["SIMULATED", "PREDICTED", "UNSET", "measured"])
def test_only_measured_data_is_accepted(bench, tmp_path, origin):
    p = record(bench, tmp_path / "results", "T1.4", [{"quantity": "i_out_a", "value": 4.0, "unit": "A"}], origin=origin)
    assert bench.evaluate(p, bench.load_catalogue())["status"] == "INVALID"


def test_changed_raw_data_and_wrong_folder_are_invalid(bench, tmp_path):
    cat = bench.load_catalogue()
    p = record(bench, tmp_path / "results", "T1.4", [{"quantity": "i_out_a", "value": 4.0, "unit": "A"}])
    (p.parent / "raw/T1.4.csv").write_text("edited\n", encoding="utf-8")
    assert any("raw data changed" in x for x in bench.evaluate(p, cat)["problems"])
    other = tmp_path / "results/EVB-002"
    other.mkdir()
    moved = other / p.name
    moved.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    assert bench.evaluate(moved, cat)["status"] == "INVALID"


def test_missing_quantity_and_conditional_limits(bench, tmp_path):
    cat = bench.load_catalogue()
    p = record(bench, tmp_path / "results", "T1.7",
               [{"quantity": "efficiency_pct", "value": 93.9, "unit": "%", "conditions": {"vin_v": 4.0}},
                {"quantity": "efficiency_pct", "value": 90.0, "unit": "%", "conditions": {"vin_v": 3.0}}], status="FAIL")
    r = bench.evaluate(p, cat)
    assert r["status"] == "FAIL" and [m["result"] for m in r["measurements"]] == ["FAIL", "PASS"]
    p = record(bench, tmp_path / "results", "T1.7",
               [{"quantity": "efficiency_pct", "value": 94.5, "unit": "%", "conditions": {"vin_v": 4.0}}],
               status="NOT TESTED", name="partial.json")
    assert bench.evaluate(p, cat)["status"] == "NOT TESTED"
    p = record(bench, tmp_path / "results", "T1.7",
               [{"quantity": "efficiency_pct", "value": 94.5, "unit": "W", "conditions": {"vin_v": 4.0}},
                {"quantity": "efficiency_pct", "value": 90.0, "unit": "%", "conditions": {"vin_v": 3.0}}],
               status="FAIL", name="unit.json")
    assert bench.evaluate(p, cat)["status"] == "FAIL", "a wrong unit can never pass"


def test_gate_g_needs_every_required_test_to_pass(bench, tmp_path):
    cat = bench.load_catalogue()
    results = tmp_path / "results"
    s = bench.summarise(results, cat)
    assert s["variants"]["evaluation-board"]["gate_g"] == "NO DATA"
    required = [t for t, d in cat.items() if "evaluation-board" in d["gate_g"]]
    for t in required[:-1]:
        record(bench, results, t, passing_values(cat[t]))
    s = bench.summarise(results, cat)
    assert s["variants"]["evaluation-board"]["gate_g"] == "OPEN"
    assert s["variants"]["evaluation-board"]["not_passed"] == [required[-1]]
    record(bench, results, required[-1], passing_values(cat[required[-1]]))
    s = bench.summarise(results, cat)
    assert s["variants"]["evaluation-board"]["gate_g"] == "PASS"
    assert s["variants"]["compact-22mm"]["gate_g"] == "NO DATA", "evaluation data never closes the compact board"
    bench.write_report(s, cat, tmp_path / "reports")
    assert "PASS" in (tmp_path / "reports/bench-report.md").read_text(encoding="utf-8")


def test_import_requires_affirmation_and_preserves_raw_data(bench, tmp_path):
    cat = bench.load_catalogue()
    csv_file = tmp_path / "t14.csv"
    csv_file.write_text("quantity,value,unit,vin_v\ni_out_a,4.51,A,3.7\ni_out_a,4.49,A,4.2\n", encoding="utf-8")
    args = SimpleNamespace(test="T1.4", serial="EVB-001", variant="evaluation-board", hardware_revision="A",
                           firmware_revision="abc", firmware_hex_sha256="0" * 64, operator="tester", date="2026-11-21",
                           csv=str(csv_file), instrument=["DMM:model:sn"], attach=None, condition=["ambient_c=23"],
                           status="PASS", notes=None, measured=False)
    with pytest.raises(SystemExit):
        bench.import_csv(args, cat, tmp_path / "results")
    args.measured = True
    out = bench.import_csv(args, cat, tmp_path / "results")
    r = bench.evaluate(out, cat)
    assert r["status"] == "PASS" and len(r["measurements"]) == 2
    assert (out.parent / "raw/t14.csv").read_bytes() == csv_file.read_bytes()
    csv_file.write_text("quantity,value,unit\ni_out_a,4.5,A\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        bench.import_csv(args, cat, tmp_path / "results")   # never overwrites raw data


def test_predictions_are_read_from_evidence(bench):
    assert bench.prediction({"source": "calculation", "path": ["uvlo", "v_off"]})["value"] == pytest.approx(2.829, abs=0.01)
    p = bench.prediction({"source": "simulation", "id": "SIM-07", "metric": "time_to_50mA_s", "scale": 1000})
    assert p is None or p["class"].startswith("PREDICTION")
