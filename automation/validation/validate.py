"""Validation register and release-gate computation.

Collects the machine-readable evidence produced by the other tools and derives every status from it.
Nothing here is hard-coded to pass: a missing report is NOT RUN, a check without bench data is
NOT VERIFIABLE.

Writes reports/validation-register.md and reports/validation-register.json.
Exit code 0 only when every collected automated check passes (gate F may still be HELD by owner
decisions; gate G always needs hardware).
"""
from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths, spec  # noqa: E402
from export.export_pcbway import required_files as required_export_files  # noqa: E402

REP = ROOT / "reports"
entries: list[dict] = []
SIMULATION_IDS = tuple(f"VAL-SIM-{i:02d}" for i in range(1, 12))
DRC_IGNORED_REASONS = {
    "lib_footprint_mismatch": "density silkscreen removal; DD-20",
    "tuning_profile_track_geometries": "no track length tuning used; DD-20",
}


def add(eid, item, method, status, evidence, detail=""):
    entries.append({"id": eid, "item": item, "method": method, "status": status, "evidence": evidence,
                    "detail": detail})
    return status


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def freshness_problems(report: Path, inputs: list[Path]) -> list[str]:
    """Legacy evidence has no hashes: require it to postdate every input it claims to check."""
    problems = []
    for p in inputs:
        if not p.is_file():
            problems.append(f"missing input: {p.name}")
        elif p.stat().st_mtime_ns > report.stat().st_mtime_ns:
            problems.append(f"stale evidence: {p.name} is newer than {report.name}")
    return problems


def issue_list_ok(value) -> bool:
    return isinstance(value, list) and all(
        isinstance(v, dict) and v.get("severity") in ("error", "warning", "exclusion")
        and isinstance(v.get("type"), str) and isinstance(v.get("description"), str)
        and isinstance(v.get("items"), list) for v in value)


def kicad_report_problems(data, kind: str, source: Path) -> list[str]:
    """A missing report field must never mean that its check found no problems."""
    if not isinstance(data, dict):
        return [f"malformed {kind.upper()} report: expected an object"]
    problems = []
    if data.get("$schema") != f"https://schemas.kicad.org/{kind}.v1.json":
        problems.append(f"unrecognised {kind.upper()} schema")
    if data.get("source") != source.name:
        problems.append(f"{kind.upper()} report source differs from {source.name}")
    severities = data.get("included_severities")
    if not isinstance(severities, list) or not all(s in severities for s in ("error", "warning", "exclusion")):
        problems.append(f"{kind.upper()} report must include errors, warnings and exclusions")
    if kind == "drc":
        for name in ("violations", "unconnected_items", "schematic_parity"):
            if not issue_list_ok(data.get(name)):
                problems.append(f"missing or malformed {name}")
        ignored = data.get("ignored_checks")
        if not isinstance(ignored, list) or any(
                not isinstance(rule, dict) or not isinstance(rule.get("key"), str) for rule in ignored):
            problems.append("missing or malformed ignored_checks")
        else:
            decisions = ROOT / "engineering/design-decisions.md"
            text = decisions.read_text(encoding="utf-8") if decisions.is_file() else ""
            dd20 = re.search(r"^## DD-20\b[\s\S]*?(?=^## |\Z)", text, re.M)
            for rule in ignored:
                key = rule["key"]
                if key not in DRC_IGNORED_REASONS:
                    problems.append(f"undocumented disabled DRC rule: {key}")
                elif dd20 is None or key not in dd20.group():
                    problems.append(f"disabled DRC rule {key} requires documented DD-20 exception")
    else:
        sheets = data.get("sheets")
        if not isinstance(sheets, list) or not sheets or any(
                not isinstance(s, dict) or not issue_list_ok(s.get("violations")) for s in sheets):
            problems.append("missing or malformed ERC sheets/violations")
    return problems


def design_source_paths(variant: str) -> list[Path]:
    return [paths.HARDWARE / variant / "placement.yaml", ROOT / "engineering/design/connectivity.yaml",
            ROOT / "engineering/design/parameters.yaml"]


def drc_evidence_problems(variant: str, report: Path) -> list[str]:
    """Hash the final saved PCB because KiCad can save it after writing the DRC report."""
    manifest = load_json(REP / f"drc-{variant}-evidence.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("inputs"), dict):
        return ["missing or malformed DRC evidence manifest; rerun PCB DRC"]
    problems = []
    if manifest.get("report_sha256") != hashlib.sha256(report.read_bytes()).hexdigest():
        problems.append("DRC report hash differs from evidence manifest")
    if manifest.get("schematic_parity") is not True or manifest.get("severity_all") is not True:
        problems.append("DRC evidence does not confirm schematic parity and all severities")
    inputs = [paths.HARDWARE / variant / f"nubm44_driver.{suffix}"
              for suffix in ("kicad_pcb", "kicad_sch", "kicad_pro")]
    for p in inputs + design_source_paths(variant):
        key = p.relative_to(ROOT).as_posix()
        if not p.is_file():
            problems.append(f"missing DRC input: {key}")
        elif manifest["inputs"].get(key) != hashlib.sha256(p.read_bytes()).hexdigest():
            problems.append(f"stale DRC evidence: {key} hash differs")
    return problems


def research():
    files = ["research/nubm44-research.md", "research/converter-ic-research.md", "research/component-research.md",
             "research/battery-and-mechanics.md", "research/pcbway-requirements.md",
             "research/architecture-comparison.md", "engineering/requirements.md", "engineering/design-decisions.md"]
    missing = [f for f in files if not (ROOT / f).exists()]
    return add("VAL-A1", "Research and requirement documents present", "INSPECT",
               "PASS" if not missing else "FAIL", ", ".join(files[:3]) + ", ...",
               f"missing: {missing}" if missing else "")


def calculations():
    d = load_json(ROOT / "engineering/calculations/power-stage-results.json")
    if d is None:
        return add("VAL-CALC", "Power-stage calculations", "CALC", "NOT RUN", "engineering/calculations/")
    out = []
    for i, c in enumerate(d["checks"], start=1):
        out.append(add(f"VAL-CALC-{i:02d}", c["check"], "CALC", c["status"],
                       "engineering/calculations/power-stage-results.md",
                       f'{c["value"]} {c["unit"]} (limit {c["kind"]} {c["limit"]})'))
    return out


def schematic(variant):
    summary = REP / f"schematic-{variant}.json"
    erc_report = REP / f"erc-{variant}.json"
    sch = paths.HARDWARE / variant / "nubm44_driver.kicad_sch"
    net = sch.with_suffix(".net")
    d, erc = load_json(summary), load_json(erc_report)
    problems = []
    if not isinstance(d, dict) or d.get("variant") != variant or any(
            type(d.get(k)) is not int or d[k] < 0 for k in ("erc_errors", "erc_warnings")) or any(
            type(d.get(k)) is not int or d[k] <= 0 for k in ("netlist_parts", "netlist_nets")) or not isinstance(
            d.get("connectivity_differences"), list) or d.get("upgrade_rc") != 0 or str(
            d.get("schematic", "")).replace("\\", "/") != sch.relative_to(ROOT).as_posix():
        problems.append("missing or malformed schematic summary")
    problems += kicad_report_problems(erc, "erc", sch)
    if summary.is_file():
        problems += freshness_problems(summary, [sch, net, erc_report,
                                                ROOT / "engineering/design/connectivity.yaml",
                                                ROOT / "engineering/design/parameters.yaml"])
    if erc_report.is_file():
        problems += freshness_problems(erc_report, [sch])
    if problems:
        status = "NOT RUN" if not summary.exists() or not erc_report.exists() else "FAIL"
        for prefix, item in (("ERC", "ERC"), ("NET", "Netlist equals connectivity.yaml")):
            add(f"VAL-{prefix}-{variant}", f"{item} ({variant})", "CAD", status,
                f"reports/schematic-{variant}.json", "; ".join(problems))
        return status
    violations = [v for sheet in erc["sheets"] for v in sheet["violations"]]
    counts_match = (sum(v["severity"] == "error" for v in violations) == d["erc_errors"]
                    and sum(v["severity"] == "warning" for v in violations) == d["erc_warnings"])
    add(f"VAL-ERC-{variant}", f"ERC ({variant})", "CAD",
        "PASS" if not violations and counts_match else "FAIL", f"reports/erc-{variant}.json",
        f"{len(violations)} unresolved findings" + ("; summary count mismatch" if not counts_match else ""))
    return add(f"VAL-NET-{variant}", f"Netlist equals connectivity.yaml ({variant})", "CAD",
               "PASS" if not d["connectivity_differences"] else "FAIL", f"reports/schematic-{variant}.json",
               f"{len(d['connectivity_differences'])} differences")


def drc(variant):
    report = REP / f"drc-{variant}.json"
    d = load_json(report)
    pcb = paths.HARDWARE / variant / "nubm44_driver.kicad_pcb"
    problems = kicad_report_problems(d, "drc", pcb)
    if report.is_file():
        problems += drc_evidence_problems(variant, report)
    if not pcb.is_file():
        problems.append("PCB does not exist")
    if problems:
        status = "NOT RUN" if not report.exists() or not pcb.exists() else "FAIL"
        for prefix, item in (("ROUTE", "PCB placed and fully routed"), ("PARITY", "PCB matches schematic"),
                             ("DRC", "DRC")):
            add(f"VAL-{prefix}-{variant}", f"{item} ({variant})", "CAD", status,
                f"reports/drc-{variant}.json", "; ".join(problems))
        return status
    viol = d["violations"]
    errors = [v for v in viol if v["severity"] == "error"]
    warnings = [v for v in viol if v["severity"] == "warning"]
    unconn = d["unconnected_items"]
    parity = d["schematic_parity"]
    add(f"VAL-ROUTE-{variant}", f"PCB placed and fully routed ({variant})", "CAD",
        "PASS" if not unconn else "FAIL", f"reports/drc-{variant}.json", f"{len(unconn)} unconnected items")
    add(f"VAL-PARITY-{variant}", f"PCB matches schematic ({variant})", "CAD",
        "PASS" if not parity else "FAIL", f"reports/drc-{variant}.json", f"{len(parity)} parity issues")
    types = {}
    for v in viol:
        types[v["type"]] = types.get(v["type"], 0) + 1
    return add(f"VAL-DRC-{variant}", f"Unresolved DRC findings ({variant})", "CAD", "PASS" if not viol else "FAIL",
               f"reports/drc-{variant}.json",
               f"{len(errors)} errors, {len(warnings)} warnings, {len(viol) - len(errors) - len(warnings)} exclusions {types}"
               + "; ignored checks: " + (", ".join(f"{r['key']} ({DRC_IGNORED_REASONS[r['key']]})"
                                                  for r in d["ignored_checks"]) or "none"))


def simulation():
    d = load_json(ROOT / "simulation/results/results.json")
    if d is None:
        return add("VAL-SIM", "Simulations", "SIM", "NOT RUN", "simulation/")
    for r in d:
        add(f"VAL-{r['id']}", r["name"], "SIM", r["status"], "simulation/results/results.md",
            json.dumps(r.get("metrics", {}), default=float)[:160])


def firmware():
    tcc = next((ROOT / "tools/tcc").rglob("tcc.exe"), None) if (ROOT / "tools/tcc").exists() else None
    if tcc is None:
        return add("VAL-FW-TEST", "Firmware unit tests", "TEST(host)", "NOT RUN", "firmware/tests")
    exe = ROOT / "build/test_app.exe"
    exe.parent.mkdir(exist_ok=True)
    r = subprocess.run([str(tcc), "-o", str(exe), str(ROOT / "firmware/tests/test_app.c"), str(ROOT / "firmware/src/app.c")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return add("VAL-FW-TEST", "Firmware unit tests", "TEST(host)", "FAIL", "firmware/tests", r.stderr[-200:])
    r = subprocess.run([str(exe)], capture_output=True, text=True)
    add("VAL-FW-TEST", "Firmware state-machine unit tests (host)", "TEST(host)",
        "PASS" if r.returncode == 0 else "FAIL", "firmware/tests/test_app.c", r.stdout.strip().splitlines()[-1] if r.stdout else "")
    avr = next((ROOT / "tools/avr-gcc").rglob("avr-gcc.exe"), None) if (ROOT / "tools/avr-gcc").exists() else None
    if avr is None:
        return add("VAL-FW-BUILD", "Firmware target build", "BUILD", "NOT RUN", "firmware/")
    r = subprocess.run([str(avr), "-mmcu=attiny1616", "-Os", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        "-o", str(ROOT / "build/fw_check.elf"), str(ROOT / "firmware/src/main.c"), str(ROOT / "firmware/src/app.c")],
                       capture_output=True, text=True)
    return add("VAL-FW-BUILD", "Firmware builds for ATtiny1616 with -Werror", "BUILD",
               "PASS" if r.returncode == 0 else "FAIL", "firmware/build.ps1", r.stderr[-200:])


def exports(variant):
    report = paths.MANUFACTURING / "pcbway" / variant / "reports" / "export-check.json"
    d = load_json(report)
    if not report.exists():
        return add(f"VAL-EXPORT-{variant}", f"PCBWay export package ({variant})", "CAD", "NOT RUN", "")
    if not isinstance(d, dict) or d.get("variant") != variant or d.get("status") not in ("PASS", "FAIL") or not isinstance(d.get("problems"), list):
        return add(f"VAL-EXPORT-{variant}", f"PCBWay export package ({variant})", "CAD", "FAIL",
                   str(report.relative_to(ROOT)), "missing or malformed export check")
    problems = list(d["problems"])
    inputs, files, hashes = d.get("inputs"), d.get("files"), d.get("file_sha256")
    if not all(isinstance(value, dict) for value in (inputs, files, hashes)) or d.get("required_files") != required_export_files(variant):
        problems.append("missing or malformed export source/output hash manifest")
    else:
        source_paths = [paths.HARDWARE / variant / f"nubm44_driver.{suffix}"
                        for suffix in ("kicad_pcb", "kicad_sch", "kicad_pro")]
        source_paths.append(ROOT / "documentation/stack-up.md")
        source_paths += design_source_paths(variant)
        for p in source_paths:
            key = p.relative_to(ROOT).as_posix()
            if not p.is_file() or inputs.get(key) != hashlib.sha256(p.read_bytes()).hexdigest():
                problems.append(f"stale export evidence: {key} hash differs or input missing")
        package = report.parent.parent
        for rel in set(files) | set(required_export_files(variant)):
            if not isinstance(rel, str) or not (package / rel).resolve().is_relative_to(package.resolve()):
                problems.append(f"invalid export artifact path: {rel}")
                continue
            p = package / rel
            if not p.is_file() or type(files.get(rel)) is not int or files[rel] <= 0:
                problems.append(f"missing, empty or unmanifested export artifact: {rel}")
            elif p.stat().st_size != files[rel] or hashes.get(rel) != hashlib.sha256(p.read_bytes()).hexdigest():
                problems.append(f"export artifact size/hash differs: {rel}")
    return add(f"VAL-EXPORT-{variant}", f"PCBWay export package internally consistent ({variant})", "CAD",
               "PASS" if d["status"] == "PASS" and not problems else "FAIL",
               f"manufacturing/pcbway/{variant}/reports/export-check.json", "; ".join(map(str, problems)))


def layout_review(variant):
    """The power-layout review must have been generated from the current board, parameters and
    calculations. Its screening results are review items for a human disposition, not a gate input."""
    report = REP / f"layout-review-{variant}.json"
    eid, item = f"VAL-LAYOUT-{variant}", f"Power-layout review current for the board ({variant})"
    if not report.exists():
        return add(eid, item, "CAD", "NOT RUN", "")
    d = load_json(report)
    inputs = d.get("inputs") if isinstance(d, dict) else None
    if not isinstance(inputs, dict) or not isinstance(d.get("findings"), list):
        return add(eid, item, "CAD", "FAIL", report.relative_to(ROOT).as_posix(), "missing or malformed review report")
    problems = []
    for key, p in (("board_sha256", paths.HARDWARE / variant / "nubm44_driver.kicad_pcb"),
                   ("parameters_sha256", ROOT / "engineering/design/parameters.yaml"),
                   ("calculations_sha256", ROOT / "engineering/calculations/power-stage-results.json")):
        if not p.is_file() or inputs.get(key) != hashlib.sha256(p.read_bytes()).hexdigest():
            problems.append(f"stale layout review: {p.relative_to(ROOT).as_posix()} hash differs")
    levels = [f.get("level") for f in d["findings"]]
    detail = "; ".join(problems) if problems else (
        f"{levels.count('REVIEW')} REVIEW / {levels.count('INFO')} INFO screening results; "
        "dispositions in engineering/layout-review.md")
    return add(eid, item, "CAD", "FAIL" if problems else "PASS", report.relative_to(ROOT).as_posix(), detail)


def requirement_blocks():
    t = (ROOT / "engineering/requirements.md").read_text(encoding="utf-8")
    blocked = re.findall(r"^\| (REQ-[A-Z0-9-]+) \|[^|]*\|[^|]*\|[^|]*\| BLOCKED \|", t, re.M)
    at_risk = re.findall(r"^\| (REQ-[A-Z0-9-]+) \|[^|]*\|[^|]*\|[^|]*\| AT-RISK \|", t, re.M)
    add("VAL-REQ-BLOCKED", "Requirements awaiting owner decisions", "INSPECT",
        "FAIL" if blocked else "PASS", "engineering/requirements.md", ", ".join(blocked) or "none")
    add("VAL-REQ-RISK", "Requirements at risk (documented, not blocking CAD)", "INSPECT", "PASS",
        "engineering/requirements.md", ", ".join(at_risk) or "none")
    return blocked


def gates(blocked):
    st = {e["id"]: e["status"] for e in entries}
    counts = {}
    for e in entries:
        counts[e["id"]] = counts.get(e["id"], 0) + 1

    def ok(ids):
        return all(counts.get(k) == 1 and st.get(k) == "PASS" for k in ids)

    g = {}
    g["A"] = "PASS" if st.get("VAL-A1") == "PASS" else "OPEN"
    g["B"] = "PASS" if ok([f"VAL-{check}-{v}" for v in spec.VARIANTS for check in ("ERC", "NET")]) else "OPEN"
    g["C"] = "PASS" if ok(SIMULATION_IDS) else "OPEN"
    for v in spec.VARIANTS:
        g[f"D ({v})"] = "PASS" if ok([f"VAL-ROUTE-{v}", f"VAL-PARITY-{v}"]) else "OPEN"
        g[f"E ({v})"] = "PASS" if ok([f"VAL-{check}-{v}" for check in ("ERC", "NET", "ROUTE", "DRC", "PARITY")]) else "OPEN"
        files_ok = ok([f"VAL-EXPORT-{v}"])
        if files_ok and all(g[k] == "PASS" for k in ("B", "C", f"D ({v})", f"E ({v})")):
            g[f"F ({v})"] = "HELD (owner decisions: " + ", ".join(blocked) + ")" if blocked else "PASS"
        else:
            g[f"F ({v})"] = "OPEN"
    g["G"] = "OPEN: requires assembled-prototype testing (cannot be closed by software)"
    return g


def sync_requirement_gates(computed):
    """Keep the requirement register's gate table derived from the same evidence."""
    requirement_path = ROOT / "engineering/requirements.md"
    text = requirement_path.read_text(encoding="utf-8")
    for gate in "ABCDEFG":
        values = [(key, value) for key, value in computed.items()
                  if key == gate or key.startswith(f"{gate} (")]
        status = "; ".join(f"{key}: {value}" if key != gate else value for key, value in values)
        text = re.sub(rf"^(\| {gate} \| [^|]* \| )[^|]*( \|)$",
                      lambda match: match[1] + status + match[2], text, flags=re.M)
    requirement_path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    entries.clear()
    research()
    calculations()
    for v in spec.VARIANTS:
        schematic(v)
        drc(v)
        layout_review(v)
        exports(v)
    simulation()
    firmware()
    blocked = requirement_blocks()
    g = gates(blocked)
    sync_requirement_gates(g)
    REP.mkdir(exist_ok=True)
    (REP / "validation-register.json").write_text(json.dumps({"date": str(date.today()), "gates": g, "entries": entries},
                                                             indent=1), encoding="utf-8")
    lines = [f"# Validation register", "", f"Generated by `automation/validation/validate.py` on {date.today()}.",
             "Statuses come from tool reports; none are hard-coded.", "", "## Release gates", "",
             "| Gate | Status |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in g.items()]
    lines += ["", "## Register", "", "| ID | Item | Method | Status | Evidence | Detail |", "|---|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['id']} | {e['item']} | {e['method']} | **{e['status']}** | {e['evidence']} | {e['detail']} |")
    lines += ["", "Physical verification still required (Gate G): see documentation/testing/test-plan.md."]
    (REP / "validation-register.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    fails = [e for e in entries if e["status"] != "PASS" and e["id"] != "VAL-REQ-BLOCKED"]
    print(f"{len(entries)} entries; FAIL/NOT RUN: {len(fails)}")
    for k, v in g.items():
        print(f"  gate {k}: {v}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
