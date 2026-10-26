"""Bench-test records: import, validate, judge, compare with predictions, report (audit AUD-VAL-10).

Only MEASURED data recorded by a person with named instruments can count. A record is one test run on one board,
stored as JSON in documentation/testing/results/<serial>/ next to its raw data (raw/), whose SHA-256 hashes the record
keeps so the raw measurements cannot change unnoticed. Software never writes measurement values: the importer copies
values from an operator's CSV and requires an explicit --measured affirmation.

Statuses: PASS, FAIL, NOT TESTED (no or incomplete measurements), INVALID (schema, metadata, raw-data hash or origin
problem, or an operator PASS that the recorded values contradict). Pass criteria come from
documentation/testing/bench-tests.yaml; design predictions are shown beside the measurements and never decide a result.

    python automation/bench/bench.py template --test T1.4 --serial EVB-001 --variant evaluation-board
    python automation/bench/bench.py import-csv --test T1.4 --serial EVB-001 --variant evaluation-board \\
        --hardware-revision A --firmware-revision <git sha> --firmware-hex-sha256 <sha> --operator "Name" \\
        --instrument "DMM:Keysight 34465A:MY123" --date 2026-11-20 --csv t14.csv --attach scope.png --measured
    python automation/bench/bench.py check        # writes reports/bench-summary.json and reports/bench-report.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "documentation" / "testing" / "results"
CATALOGUE = ROOT / "documentation" / "testing" / "bench-tests.yaml"
REPORTS = ROOT / "reports"
SCHEMA = "nubm44-bench-result.v1"
VARIANTS = ("compact-22mm", "evaluation-board")
STATUSES = ("PASS", "FAIL", "NOT TESTED", "INVALID")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_catalogue(path: Path = CATALOGUE) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {t["id"]: t for t in data["tests"]}


# ------------------------------------------------------------------ record validation
def record_problems(rec, path: Path, catalogue: dict) -> list[str]:
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA:
        return ["not a bench record (schema)"]
    out = []
    if rec.get("data_origin") != "MEASURED":
        out.append("data_origin is not MEASURED: only bench measurements can be recorded")
    if rec.get("test_id") not in catalogue:
        out.append(f"unknown test id {rec.get('test_id')!r}")
    board = rec.get("board") if isinstance(rec.get("board"), dict) else {}
    if not board.get("serial") or board.get("serial") != path.parent.name:
        out.append("board serial missing or not equal to the folder name")
    if board.get("variant") not in VARIANTS:
        out.append("board variant missing or unknown")
    if not board.get("hardware_revision"):
        out.append("hardware revision missing")
    fw = rec.get("firmware") if isinstance(rec.get("firmware"), dict) else {}
    if not fw.get("revision") or not (SHA_RE.match(str(fw.get("hex_sha256", ""))) or fw.get("hex_sha256") == "NOT PROGRAMMED"):
        out.append("firmware revision and HEX SHA-256 (or NOT PROGRAMMED) required")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(rec.get("date", ""))):
        out.append("test date (YYYY-MM-DD) missing")
    if not str(rec.get("operator", "")).strip():
        out.append("operator missing")
    instruments = rec.get("instruments")
    if not isinstance(instruments, list) or not instruments or any(
            not isinstance(i, dict) or not i.get("type") or not i.get("model") for i in instruments):
        out.append("at least one instrument with type and model required")
    if not isinstance(rec.get("conditions"), dict):
        out.append("conditions must be an object")
    if rec.get("status") not in STATUSES:
        out.append(f"status must be one of {STATUSES}")
    meas = rec.get("measurements")
    if not isinstance(meas, list):
        out.append("measurements must be a list")
    else:
        for i, m in enumerate(meas):
            if not isinstance(m, dict) or not isinstance(m.get("quantity"), str) or "value" not in m or not m.get("unit"):
                out.append(f"measurement {i}: quantity, value and unit required")
    atts = rec.get("attachments", [])
    if not isinstance(atts, list):
        out.append("attachments must be a list")
    else:
        for a in atts:
            rel = a.get("path") if isinstance(a, dict) else None
            target = (path.parent / rel).resolve() if isinstance(rel, str) else None
            if target is None or not target.is_relative_to(path.parent.resolve()):
                out.append(f"attachment path outside the board folder: {rel}")
            elif not target.is_file():
                out.append(f"raw data missing: {rel}")
            elif a.get("sha256") != sha256(target):
                out.append(f"raw data changed since recording: {rel}")
    return out


# ------------------------------------------------------------------ judging
def _num(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and re.fullmatch(r"0x[0-9a-fA-F]+", v.strip()):
        return int(v, 16)
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _matches(conditions: dict, when: dict | None) -> bool:
    return all(_num(conditions.get(k)) == _num(v) for k, v in (when or {}).items())


def judge_value(q: dict, value) -> bool | None:
    """True/False against the limit, None for record-only quantities."""
    if q.get("record"):
        return None
    v = _num(value)
    if "equals" in q:
        return v == _num(q["equals"])
    if isinstance(v, (bool, str)):
        return False
    if q.get("abs"):
        v = abs(v)
    if "range" in q:
        return q["range"][0] <= v <= q["range"][1]
    if "min" in q and v < q["min"]:
        return False
    if "max" in q and v > q["max"]:
        return False
    return True


def judge(rec: dict, test: dict) -> tuple[str, list[dict]]:
    rows, failed, missing = [], False, False
    for q in test["quantities"]:
        ms = [m for m in rec.get("measurements", []) if m.get("quantity") == q["name"]
              and _matches({**rec.get("conditions", {}), **(m.get("conditions") or {})}, q.get("when"))]
        if not ms:
            missing = True
            rows.append({"quantity": q["name"], "when": q.get("when"), "result": "MISSING"})
            continue
        for m in ms:
            if str(m.get("unit")) != str(q["unit"]):
                ok, result = False, f"UNIT {m.get('unit')} != {q['unit']}"
            else:
                ok = judge_value(q, m["value"])
                result = "RECORDED" if ok is None else ("PASS" if ok else "FAIL")
            failed |= ok is False
            rows.append({"quantity": q["name"], "when": q.get("when"), "value": m["value"], "unit": m.get("unit"),
                         "conditions": m.get("conditions") or {}, "result": result})
    return ("FAIL" if failed else "NOT TESTED" if missing else "PASS"), rows


def evaluate(path: Path, catalogue: dict) -> dict:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"path": path.as_posix(), "status": "INVALID", "problems": [f"unreadable: {exc}"]}
    problems = record_problems(rec, path, catalogue)
    base = {"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix(),
            "test_id": rec.get("test_id") if isinstance(rec, dict) else None,
            "serial": (rec.get("board") or {}).get("serial") if isinstance(rec, dict) else None,
            "variant": (rec.get("board") or {}).get("variant") if isinstance(rec, dict) else None,
            "date": rec.get("date") if isinstance(rec, dict) else None}
    if problems:
        return dict(base, status="INVALID", problems=problems)
    computed, rows = judge(rec, catalogue[rec["test_id"]])
    operator = rec["status"]
    notes = []
    if operator == "INVALID":
        status = "INVALID"
    elif operator == "NOT TESTED":
        status = "NOT TESTED"
    elif operator == "PASS" and computed != "PASS":
        status, notes = "INVALID", [f"operator PASS contradicts the recorded values ({computed})"]
    elif operator == "FAIL" and computed == "PASS":
        status, notes = "FAIL", ["operator recorded FAIL although the values meet the limits; FAIL kept"]
    else:
        status = computed
    fw = rec["firmware"].get("hex_sha256")
    current = (_load_json(REPORTS / "firmware-evidence.json") or {}).get("target", {}).get("hex_sha256")
    return dict(base, status=status, computed=computed, operator_status=operator, measurements=rows, problems=notes,
                firmware_matches_current_build=(fw == current) if current else None)


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ predictions
def prediction(spec_: dict | None):
    if not spec_:
        return None
    scale = spec_.get("scale", 1)
    if spec_["source"] == "calculation":
        node = _load_json(ROOT / "engineering/calculations/power-stage-results.json")
        for k in spec_["path"]:
            node = node.get(k) if isinstance(node, dict) else None
        if isinstance(node, list):
            node = node[0]
        return None if node is None else {"value": round(node * scale, 4), "class": "PREDICTION (calculation)"}
    if spec_["source"] == "calculation-check":
        calc = _load_json(ROOT / "engineering/calculations/power-stage-results.json") or {}
        c = next((c for c in calc.get("checks", []) if c["check"].startswith(spec_["check"])), None)
        return None if c is None else {"value": round(c["value"] * scale, 4), "class": "PREDICTION (calculation)"}
    if spec_["source"] == "simulation":
        sims = _load_json(ROOT / "simulation/results/results.json") or []
        r = next((r for r in sims if r.get("id") == spec_["id"]), None)
        v = (r or {}).get("metrics", {}).get(spec_["metric"])
        return None if v is None else {"value": round(v * scale, 6), "class": "PREDICTION (averaged simulation)"}
    return None


# ------------------------------------------------------------------ summary and report
def summarise(results_dir: Path = RESULTS, catalogue: dict | None = None) -> dict:
    catalogue = catalogue or load_catalogue()
    records = [evaluate(p, catalogue) for p in sorted(results_dir.glob("*/*.json"))] if results_dir.is_dir() else []
    variants = {}
    for v in VARIANTS:
        required = [t for t, d in catalogue.items() if v in (d.get("gate_g") or [])]
        latest = {}
        for r in records:
            if r.get("variant") == v and r["status"] != "INVALID" and r.get("test_id") in catalogue:
                if r["test_id"] not in latest or (r["date"], r["path"]) > (latest[r["test_id"]]["date"], latest[r["test_id"]]["path"]):
                    latest[r["test_id"]] = r
        not_passed = [t for t in required if latest.get(t, {}).get("status") != "PASS"]
        has_data = any(r.get("variant") == v for r in records)
        variants[v] = {"gate_g": "PASS" if required and not not_passed else ("OPEN" if has_data else "NO DATA"),
                       "required": required, "not_passed": not_passed,
                       "latest": {t: {"status": r["status"], "date": r["date"], "serial": r["serial"], "path": r["path"]}
                                  for t, r in latest.items()}}
    return {"schema": "nubm44-bench-summary.v1", "generated": str(date.today()),
            "evidence_class": "MEASURED (bench records only; predictions are shown for comparison)",
            "variants": variants, "records": records,
            "invalid_records": [r["path"] for r in records if r["status"] == "INVALID"]}


def write_report(summary: dict, catalogue: dict, reports: Path = REPORTS) -> None:
    reports.mkdir(exist_ok=True)
    (reports / "bench-summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    lines = ["# Bench evidence (Gate G)", "", f"Generated by `automation/bench/bench.py check` on {summary['generated']}. "
             "Only MEASURED records from `documentation/testing/results/` count; predictions are listed for "
             "comparison and never pass a test.", "", "| Variant | Gate G | Required tests | Not yet PASS |", "|---|---|---|---|"]
    for v, s in summary["variants"].items():
        lines.append(f"| {v} | **{s['gate_g']}** | {len(s['required'])} | {len(s['not_passed'])} |")
    if summary["invalid_records"]:
        lines += ["", "**Invalid records:** " + ", ".join(summary["invalid_records"])]
    for v, s in summary["variants"].items():
        lines += ["", f"## {v}", "", "| Test | Title | Status | Date | Board | Limit | Prediction |", "|---|---|---|---|---|---|---|"]
        for t in s["required"]:
            d = catalogue[t]
            latest = s["latest"].get(t)
            limits, preds = [], []
            for q in d["quantities"]:
                lim = ("record" if q.get("record") else f"= {q['equals']}" if "equals" in q else
                       f"{q['range'][0]}..{q['range'][1]}" if "range" in q else
                       f">= {q['min']}" if "min" in q else f"<= {q['max']}")
                limits.append(f"{q['name']} {lim} {q['unit']}" + (f" @ {q['when']}" if q.get("when") else ""))
                p = prediction(q.get("prediction"))
                if p:
                    preds.append(f"{q['name']} {p['value']} {q['unit']}")
            lines.append(f"| {t} | {d['title']} | {latest['status'] if latest else 'NOT TESTED'} | "
                         f"{latest['date'] if latest else '-'} | {latest['serial'] if latest else '-'} | "
                         f"{'; '.join(limits)} | {'; '.join(preds) or '-'} |")
    (reports / "bench-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ record creation
def template(test_id: str, serial: str, variant: str, catalogue: dict) -> dict:
    t = catalogue[test_id]
    return {"schema": SCHEMA, "test_id": test_id, "data_origin": "UNSET (set to MEASURED only for real bench data)",
            "board": {"serial": serial, "variant": variant, "hardware_revision": "", "assembly": ""},
            "firmware": {"revision": "", "hex_sha256": ""}, "date": "", "operator": "",
            "instruments": [{"type": "", "model": "", "serial": "", "calibration_due": ""}],
            "conditions": {"ambient_c": None, "supply": "", "load": ""},
            "measurements": [{"quantity": q["name"], "value": None, "unit": q["unit"], "conditions": q.get("when") or {}}
                             for q in t["quantities"]],
            "attachments": [], "status": "NOT TESTED", "notes": ""}


def import_csv(args, catalogue: dict, results_dir: Path = RESULTS) -> Path:
    if not args.measured:
        raise SystemExit("refusing to import: confirm with --measured that every value was measured on the bench")
    if args.test not in catalogue:
        raise SystemExit(f"unknown test {args.test}")
    board_dir = results_dir / args.serial
    raw = board_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    measurements = []
    with open(args.csv, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            cond = {k: _num(v) for k, v in row.items() if k not in ("quantity", "value", "unit") and v not in ("", None)}
            measurements.append({"quantity": row["quantity"].strip(), "value": _num(row["value"]),
                                 "unit": row["unit"].strip(), "conditions": cond})
    attachments = []
    for src in [args.csv] + list(args.attach or []):
        src = Path(src)
        dst = raw / src.name
        if dst.exists() and sha256(dst) != sha256(src):
            raise SystemExit(f"{dst} exists with different content; raw data is never overwritten")
        shutil.copyfile(src, dst)
        attachments.append({"path": f"raw/{src.name}", "sha256": sha256(dst), "description": "imported by bench.py"})
    instruments = []
    for spec_ in args.instrument:
        parts = (spec_.split(":") + ["", "", "", ""])[:4]
        instruments.append(dict(zip(("type", "model", "serial", "calibration_due"), parts)))
    rec = {"schema": SCHEMA, "test_id": args.test, "data_origin": "MEASURED",
           "board": {"serial": args.serial, "variant": args.variant, "hardware_revision": args.hardware_revision},
           "firmware": {"revision": args.firmware_revision, "hex_sha256": args.firmware_hex_sha256},
           "date": args.date, "operator": args.operator, "instruments": instruments,
           "conditions": {k: _num(v) for k, v in (c.split("=", 1) for c in args.condition or [])},
           "measurements": measurements, "attachments": attachments, "status": args.status, "notes": args.notes or ""}
    n = 1
    while (out := board_dir / f"{args.test}_{args.date}_{n}.json").exists():
        n += 1
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template")
    t.add_argument("--test", required=True); t.add_argument("--serial", required=True)
    t.add_argument("--variant", required=True, choices=VARIANTS)
    i = sub.add_parser("import-csv")
    for name in ("test", "serial", "hardware-revision", "firmware-revision", "firmware-hex-sha256", "operator", "date", "csv"):
        i.add_argument(f"--{name}", required=True)
    i.add_argument("--variant", required=True, choices=VARIANTS)
    i.add_argument("--instrument", action="append", required=True, help="type:model:serial:calibration_due")
    i.add_argument("--attach", action="append"); i.add_argument("--condition", action="append", help="name=value")
    i.add_argument("--status", default="PASS", choices=STATUSES); i.add_argument("--notes")
    i.add_argument("--measured", action="store_true", help="affirm that every value was measured on the bench")
    sub.add_parser("check")
    args = ap.parse_args(argv)
    catalogue = load_catalogue()
    if args.cmd == "template":
        print(json.dumps(template(args.test, args.serial, args.variant, catalogue), indent=1))
        return 0
    if args.cmd == "import-csv":
        out = import_csv(args, catalogue)
        print(f"recorded {out.relative_to(ROOT)}: {evaluate(out, catalogue)['status']}")
        return 0
    summary = summarise(RESULTS, catalogue)
    write_report(summary, catalogue)
    for v, s in summary["variants"].items():
        print(f"{v}: Gate G {s['gate_g']} ({len(s['required']) - len(s['not_passed'])}/{len(s['required'])} required tests PASS)")
    for p in summary["invalid_records"]:
        print(f"INVALID record: {p}")
    return 1 if summary["invalid_records"] else 0


if __name__ == "__main__":
    sys.exit(main())
