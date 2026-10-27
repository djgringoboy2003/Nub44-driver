"""Validation register, release gates and per-board readiness.

Collects the machine-readable evidence produced by the other tools and derives every status from it.
Nothing here is hard-coded to pass: a missing report is NOT RUN, stale or malformed evidence is FAIL, and a
check without bench data is never PASS. Calculation, simulation, firmware, DRC and export evidence is bound to
its inputs by SHA-256 (automation/nubm44/evidence.py); file modification times are only used for the legacy
schematic summary.

Modes (--mode):
  full (default)  every check, firmware target build and mutation check; writes reports/validation-register.*,
                  reports/release-readiness.* and the requirement gate table
  fast            portable checks without KiCad, avr-gcc or ngspice: evidence integrity, calculation and
                  simulation results, CAD report hashes, firmware host tests (writes build/validation-fast.json)
  eval-cad, compact-cad   CAD evidence and readiness of one board
  manufacturing   readiness of both boards from the current evidence
  bench           Gate G bench evidence (documentation/testing/results/)

Exit code: 0 when every failure is an unchanged entry of engineering/known-limitations.yaml, 1 for any new or
changed failure; with --strict, 1 for any entry that is not PASS. Gate G always needs hardware.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths, spec  # noqa: E402
from nubm44 import evidence as evidence_mod  # noqa: E402
from export.export_pcbway import required_files as required_export_files  # noqa: E402
from export import release_check  # noqa: E402

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


CALC_DIR = "engineering/calculations"
CALC_REQUIRED_INPUTS = ("engineering/design/parameters.yaml", "engineering/calculations/power_stage.py")
SIM_DIR = "simulation/results"
SIM_REQUIRED_INPUTS = ("engineering/design/parameters.yaml", "simulation/run_sims.py")


def calculations():
    """Each calculation check, re-judged from its value and limit, only if the evidence is current."""
    results, manifest = load_json(ROOT / CALC_DIR / "power-stage-results.json"), load_json(ROOT / CALC_DIR / "power-stage-evidence.json")
    if results is None and manifest is None:
        return add("VAL-CALC-EVID", "Power-stage calculation evidence", "CALC", "NOT RUN", f"{CALC_DIR}/",
                   "run engineering/calculations/power_stage.py")
    problems = evidence_mod.problems(manifest, ROOT, "calculation", CALC_REQUIRED_INPUTS)
    checks = results.get("checks") if isinstance(results, dict) else None
    if not isinstance(checks, list) or not checks:
        problems.append("results contain no checks")
    elif isinstance(manifest, dict) and [c.get("check") if isinstance(c, dict) else None for c in checks] != manifest.get("check_names"):
        problems.append("check list differs from the evidence manifest")
    tools = manifest.get("tools", {}) if isinstance(manifest, dict) else {}
    add("VAL-CALC-EVID", "Calculation evidence current (hashes of parameters, script and model code)", "CALC",
        "FAIL" if problems else "PASS", f"{CALC_DIR}/power-stage-evidence.json",
        "; ".join(problems[:6]) if problems else f"{len(checks)} checks; python {tools.get('python')}, numpy {tools.get('numpy')}")
    if problems:
        return "FAIL"
    for i, c in enumerate(checks, start=1):
        eid = f"VAL-CALC-{i:02d}"
        try:
            value, limit, kind, recorded = float(c["value"]), float(c["limit"]), c["kind"], c["status"]
            if kind not in ("max", "min") or recorded not in ("PASS", "FAIL"):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            add(eid, str(c.get("check", "?")) if isinstance(c, dict) else "?", "CALC", "FAIL",
                f"{CALC_DIR}/power-stage-results.md", "malformed check entry")
            continue
        judged = "PASS" if (value <= limit if kind == "max" else value >= limit) else "FAIL"
        add(eid, c["check"], "CALC", judged if judged == recorded else "FAIL", f"{CALC_DIR}/power-stage-results.md",
            f'{c["value"]} {c.get("unit", "")} (limit {kind} {c["limit"]})'
            + ("" if judged == recorded else "; recorded status contradicts the value and limit"))
    return "PASS"


SCH_REQUIRED_INPUTS = ("engineering/design/connectivity.yaml", "engineering/design/parameters.yaml")


def legacy_schematic_inputs(sch: Path) -> list[Path]:
    return [sch, sch.with_suffix(".net"), REP / f"erc-{sch.parent.name}.json",
            ROOT / "engineering/design/connectivity.yaml", ROOT / "engineering/design/parameters.yaml"]


def attest_schematic_evidence() -> list[str]:
    """One-off migration of legacy schematic evidence to a hash manifest. Writes a manifest only when the legacy
    modification-time check passes now; build_schematic.py writes manifests itself from then on."""
    spec_bs = importlib.util.spec_from_file_location("nubm44_build_schematic", ROOT / "automation/schematic/build_schematic.py")
    bs = importlib.util.module_from_spec(spec_bs)
    spec_bs.loader.exec_module(bs)
    done = []
    for v in spec.VARIANTS:
        sch = paths.HARDWARE / v / "nubm44_driver.kicad_sch"
        summary, erc_report = REP / f"schematic-{v}.json", REP / f"erc-{v}.json"
        if (REP / f"schematic-{v}-evidence.json").is_file():
            continue
        problems = freshness_problems(summary, legacy_schematic_inputs(sch)) + freshness_problems(erc_report, [sch])
        if problems:
            done.append(f"{v}: not attested ({'; '.join(problems)})")
            continue
        bs.write_evidence(v, sch, [erc_report, summary, sch.with_suffix(".net")], {"kicad-cli": "not rerun"},
                          attested="legacy evidence migrated by validate.py --attest-schematic after its modification-time "
                                   f"freshness check passed on {date.today()}; schematics were not regenerated")
        done.append(f"{v}: attested")
    return done


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
    manifest = REP / f"schematic-{variant}-evidence.json"
    if manifest.is_file():                        # hash-bound evidence (AUD-VAL-08)
        m = load_json(manifest)
        problems += evidence_mod.problems(m, ROOT, "schematic", SCH_REQUIRED_INPUTS)
        outs = m.get("outputs", {}) if isinstance(m, dict) else {}
        for p in (sch, net, erc_report, summary):
            if p.relative_to(ROOT).as_posix() not in outs:
                problems.append(f"schematic evidence manifest does not cover {p.name}")
    else:                                         # legacy evidence: modification times only
        if summary.is_file():
            problems += freshness_problems(summary, legacy_schematic_inputs(sch))
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
    """Each simulation result, only if the evidence is current; every expected ID must appear exactly once."""
    results, manifest = load_json(ROOT / SIM_DIR / "results.json"), load_json(ROOT / SIM_DIR / "evidence.json")
    if results is None and manifest is None:
        return add("VAL-SIM-EVID", "Simulation evidence", "SIM", "NOT RUN", "simulation/", "run simulation/run_sims.py")
    problems = evidence_mod.problems(manifest, ROOT, "simulation", SIM_REQUIRED_INPUTS)
    if not isinstance(results, list) or not results:
        problems.append("results.json is not a list of results")
    tools = manifest.get("tools", {}) if isinstance(manifest, dict) else {}
    add("VAL-SIM-EVID", "Simulation evidence current (hashes of parameters, script, calculation results)", "SIM",
        "FAIL" if problems else "PASS", f"{SIM_DIR}/evidence.json",
        "; ".join(problems[:6]) if problems else f"{len(results)} results; {tools.get('ngspice', 'ngspice UNKNOWN')}")
    if problems:
        return "FAIL"
    expected = manifest.get("simulation_ids") or [s.replace("VAL-", "") for s in SIMULATION_IDS]
    seen = set()
    for r in results:
        if not (isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("status") in ("PASS", "FAIL", "NOT RUN")
                and isinstance(r.get("metrics"), dict) and isinstance(r.get("name"), str)):
            add("VAL-SIM-MALFORMED", "Simulation result", "SIM", "FAIL", f"{SIM_DIR}/results.json", "malformed result entry")
            continue
        status, note = r["status"], ""
        if not isinstance(r.get("pass"), bool):
            status, note = "FAIL", "; pass flag is not a boolean"
        elif status == "PASS" and not r["pass"]:
            status, note = "FAIL", "; recorded PASS contradicts the result"
        seen.add(r["id"])
        add(f"VAL-{r['id']}", r["name"], "SIM", status, f"{SIM_DIR}/results.md",
            (json.dumps(r["metrics"], default=float)[:160] if r["metrics"] else str(r.get("error", ""))[:160]) + note)
    for sid in expected:
        if sid not in seen:
            add(f"VAL-{sid}", f"Simulation {sid}", "SIM", "NOT RUN", f"{SIM_DIR}/results.json", "result missing")
    return "PASS"


def sourcing():
    """Sourcing records against connectivity.yaml and part ratings against the circuit (FAIL-level findings only)."""
    path = ROOT / "sourcing" / "check_sourcing.py"
    if not path.is_file():
        return add("VAL-SRC", "Sourcing records and part ratings", "INSPECT", "NOT RUN", "sourcing/")
    s = importlib.util.spec_from_file_location("nubm44_check_sourcing", path)
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    result = module.check()
    module.write(result)
    fails = [f"{f['ref']} {f['check']}: {f['detail']}" for f in result["findings"] if f["severity"] == "FAIL"]
    c = result["counts"]
    return add("VAL-SRC", "Sourcing records current; package, voltage and power ratings consistent", "INSPECT",
               result["status"], "sourcing/sourcing-check.md",
               (("; ".join(fails[:5]) + "; ") if fails else "") + f"{c['FAIL']} FAIL, {c['WARN']} WARN, {c['INFO']} INFO")


def firmware_build_module():
    path = ROOT / "firmware/build.py"
    spec_ = importlib.util.spec_from_file_location("nubm44_firmware_build", path)
    module = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(module)
    return module


def firmware(target=True, mutation=True):
    """Run the firmware build driver (the single source of compile flags) and record each step."""
    fb = firmware_build_module()
    suites, compiler = fb.host_tests(ROOT / "build/fw-validate")
    statuses = {s["status"] for s in suites}
    checks = sum(s.get("checks", 0) for s in suites)
    fails = sum(s.get("failures", 0) for s in suites)
    bad = [f"{s['suite']}: {s['status']} {s.get('detail', '')[:120]}" for s in suites if s["status"] != "PASS"]
    status = "PASS" if statuses == {"PASS"} else ("NOT RUN" if statuses == {"NOT RUN"} else "FAIL")
    add("VAL-FW-TEST", "Firmware host tests: state machine, conversions, hold-up, runtime, HAL register model",
        "TEST(host)", status, "firmware/tests/, firmware/build.py",
        f"{len(suites)} suites, {checks} checks, {fails} failures; compiler: {compiler}" + ("; " + "; ".join(bad) if bad else ""))
    if target:
        t = fb.target_build()
        add("VAL-FW-BUILD", "Firmware builds for ATtiny1616 with -Werror", "BUILD", t["status"], "firmware/build.py",
            (f"flash {t['flash_bytes']} B, RAM {t['ram_bytes']} B; {t['compiler']}" if t["status"] == "PASS"
             else t.get("detail", "")[-300:]))
    if mutation:
        m = fb.mutation_check()
        killed = sum(r["status"] == "KILLED" for r in m.get("mutants", []))
        add("VAL-FW-MUTATION", "Firmware tests detect each audited defect (mutation check)", "TEST(host)", m["status"],
            "firmware/build.py --mutation",
            f"{killed}/{len(m.get('mutants', []))} mutants killed" if m.get("mutants") else m.get("detail", ""))


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
        problems += incomplete_marker_problems(variant, package, d)
    return add(f"VAL-EXPORT-{variant}", f"PCBWay export package internally consistent ({variant})", "CAD",
               "PASS" if d["status"] == "PASS" and not problems else "FAIL",
               f"manufacturing/pcbway/{variant}/reports/export-check.json", "; ".join(map(str, problems)))


def jlcpcb(variant):
    """Derived JLCPCB package (if one exists) must still match the PCBWay package it came from."""
    s = importlib.util.spec_from_file_location("nubm44_export_jlcpcb", ROOT / "automation/export/export_jlcpcb.py")
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    problems = module.check_problems(variant, ROOT)
    if problems is None:
        return None
    return add(f"VAL-JLC-{variant}", f"JLCPCB upload files derived from the current PCBWay package ({variant})", "CAD",
               "PASS" if not problems else "FAIL", f"manufacturing/jlcpcb/{variant}/reports/jlcpcb-check.json",
               "; ".join(problems[:4]))


def incomplete_marker_problems(variant, package: Path, check: dict) -> list[str]:
    """An export of a board whose DRC shows open items must say so inside the fabrication ZIP (AUD-MFG-01)."""
    drc_report = load_json(REP / f"drc-{variant}.json")
    if not isinstance(drc_report, dict):
        return []
    incomplete = bool(drc_report.get("unconnected_items")) or any(
        v.get("severity") == "error" for v in drc_report.get("violations", []) if isinstance(v, dict))
    if not incomplete:
        return []
    problems = []
    if check.get("package_class") != "DRAFT_REVIEW_INCOMPLETE_BOARD":
        problems.append("incomplete board exported without the DRAFT_REVIEW_INCOMPLETE_BOARD class")
    zpath = package / f"{variant}-gerbers.zip"
    try:
        with zipfile.ZipFile(zpath) as z:
            if "DO_NOT_FABRICATE.txt" not in z.namelist():
                problems.append("fabrication ZIP of an incomplete board lacks DO_NOT_FABRICATE.txt")
    except (OSError, zipfile.BadZipFile):
        problems.append("fabrication ZIP unreadable")
    return problems


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
    g["G"] = gate_g()
    return g


GATE_EVIDENCE = {
    "A": "documents present (inspection)",
    "B": "KiCad ERC and netlist comparison",
    "C": "model-level predictions (averaged ngspice model); not measurements",
    "D": "KiCad DRC connectivity",
    "E": "KiCad ERC/DRC",
    "F": "export package internal consistency; not a manufacturing release (see release readiness)",
    "G": "bench measurements on assembled prototypes only",
}


def gate_g() -> str:
    """Gate G is closed only by recorded bench evidence (reports/bench-summary.json), never by software checks."""
    summary = load_json(REP / "bench-summary.json")
    variants = summary.get("variants") if isinstance(summary, dict) else None
    if not isinstance(variants, dict) or not variants:
        return "OPEN: requires assembled-prototype testing (cannot be closed by software)"
    states = {v: (variants.get(v) or {}).get("gate_g", "NO DATA") for v in spec.VARIANTS}
    if all(s == "NO DATA" for s in states.values()):
        return "OPEN: requires assembled-prototype testing (no bench records yet; cannot be closed by software)"
    text = ", ".join(f"{v} {s}" for v, s in states.items())
    return ("PASS: " if all(s == "PASS" for s in states.values()) else "OPEN: ") + "bench evidence " + text


def load_known() -> list[dict]:
    data = None
    try:
        data = yaml.safe_load((ROOT / "engineering/known-limitations.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        pass
    out = []
    for category in ("accepted", "pending_disposition"):
        for item in (data or {}).get(category) or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                out.append(dict(item, category=category))
    return out


def classify(known: list[dict]) -> dict:
    """Split failures into unchanged known items and new or changed ones (the register keeps every FAIL)."""
    by_id = {k["id"]: k for k in known}
    result = {"known": [], "changed": [], "new": [], "resolved": []}
    for e in entries:
        if e["status"] == "PASS" or e["id"] == "VAL-REQ-BLOCKED":
            continue
        k = by_id.get(e["id"])
        if k is None:
            result["new"].append(e)
            continue
        detail = str(e.get("detail", ""))
        same = k.get("status") == e["status"] and (
            detail == k["detail"] if "detail" in k else str(k.get("detail_contains", "\0")) in detail)
        result["known" if same else "changed"].append(dict(e, category=k["category"], reason=k.get("reason", "")))
    st = {e["id"]: e["status"] for e in entries}
    result["resolved"] = [k for k in known if st.get(k["id"]) == "PASS"]
    return result


def bench_evidence() -> None:
    """Refresh reports/bench-summary.json from documentation/testing/results (MEASURED records only)."""
    s = importlib.util.spec_from_file_location("nubm44_bench", ROOT / "automation/bench/bench.py")
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    module.RESULTS, module.REPORTS = ROOT / "documentation/testing/results", REP
    catalogue = module.load_catalogue(ROOT / "documentation/testing/bench-tests.yaml")
    summary = module.summarise(module.RESULTS, catalogue)
    module.write_report(summary, catalogue, REP)
    for p in summary["invalid_records"]:
        add("VAL-BENCH-INVALID", "Bench record valid (schema, metadata, raw-data hashes, MEASURED origin)", "TEST",
            "FAIL", p, "see reports/bench-report.md")


def run_checks(mode: str) -> None:
    entries.clear()
    if mode in ("full", "manufacturing", "bench") and (ROOT / "automation/bench/bench.py").is_file():
        bench_evidence()
    variants = {"eval-cad": ["evaluation-board"], "compact-cad": ["compact-22mm"]}.get(mode, list(spec.VARIANTS))
    if mode in ("full", "fast", "manufacturing"):
        research()
        calculations()
        simulation()
        sourcing()
    for v in variants:
        if mode == "bench":
            break
        schematic(v)
        drc(v)
        layout_review(v)
        exports(v)
        if (ROOT / "automation/export/export_jlcpcb.py").is_file():
            jlcpcb(v)
    if mode in ("full", "manufacturing"):
        firmware(target=True, mutation=(mode == "full"))
    elif mode == "fast":
        firmware(target=False, mutation=False)
    elif mode in ("eval-cad", "compact-cad"):
        calculations()
        simulation()
        firmware(target=True, mutation=False)


def write_register(g: dict, cls: dict, readiness: dict) -> None:
    today = str(date.today())
    REP.mkdir(exist_ok=True)
    (REP / "validation-register.json").write_text(json.dumps(
        {"date": today, "gates": g, "gate_evidence": GATE_EVIDENCE, "entries": entries,
         "known_unchanged": [e["id"] for e in cls["known"]], "new_or_changed": [e["id"] for e in cls["new"] + cls["changed"]],
         "readiness": {v: r["level"] for v, r in readiness.items()}}, indent=1), encoding="utf-8")
    lines = ["# Validation register", "", f"Generated by `automation/validation/validate.py` on {today}.",
             "Statuses come from tool reports and hash-bound evidence; none are hard-coded. Calculations and simulations",
             "are predictions; only Gate G evidence is measured on hardware.", "", "## Release gates", "",
             "| Gate | Status | Evidence class |", "|---|---|---|"]
    lines += [f"| {k} | {v} | {GATE_EVIDENCE.get(k[0], '')} |" for k, v in g.items()]
    lines += ["", "## Board readiness", "", "| Variant | Level | Blockers to the next level |", "|---|---|---|"]
    for v, r in readiness.items():
        nxt = r["next_level"]
        todo = f"{len(r['blockers'][nxt])} for {nxt}" if nxt else "none"
        lines.append(f"| {v} | **{r['level']}** | {todo} |")
    lines += ["", "Details: [release-readiness.md](release-readiness.md).", "",
              "## Known limitations and open findings", "",
              "Listed in `engineering/known-limitations.yaml`. They remain FAIL below; the validator's exit code only "
              "ignores them while they are unchanged.", "", "| ID | Category | Status | Reason |", "|---|---|---|---|"]
    for e in cls["known"] + cls["changed"]:
        changed = " (CHANGED: update the file deliberately)" if e in cls["changed"] else ""
        lines.append(f"| {e['id']} | {e['category']}{changed} | {e['status']} | {str(e.get('reason', '')).strip()} |")
    if cls["new"]:
        lines += ["", "**New failures (not in known-limitations.yaml):** " + ", ".join(e["id"] for e in cls["new"])]
    lines += ["", "## Register", "", "| ID | Item | Method | Status | Evidence | Detail |", "|---|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['id']} | {e['item']} | {e['method']} | **{e['status']}** | {e['evidence']} | {e['detail']} |")
    lines += ["", "Physical verification still required (Gate G): see documentation/testing/test-plan.md."]
    (REP / "validation-register.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def rerun_stale() -> list[str]:
    """Regenerate calculation and simulation evidence whose inputs changed (generators run in this venv)."""
    done = []
    for kind, manifest, script, required in (
            ("calculation", ROOT / CALC_DIR / "power-stage-evidence.json", ROOT / CALC_DIR / "power_stage.py", CALC_REQUIRED_INPUTS),
            ("simulation", ROOT / SIM_DIR / "evidence.json", ROOT / "simulation/run_sims.py", SIM_REQUIRED_INPUTS)):
        if evidence_mod.problems(load_json(manifest), ROOT, kind, required):
            subprocess.run([sys.executable, str(script)], cwd=ROOT, timeout=3600)
            done.append(kind)
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="full",
                    choices=["full", "fast", "eval-cad", "compact-cad", "manufacturing", "bench"])
    ap.add_argument("--strict", action="store_true", help="exit 1 for any entry that is not PASS")
    ap.add_argument("--rerun-stale", action="store_true", help="rerun stale calculations and simulations first")
    ap.add_argument("--attest-schematic", action="store_true",
                    help="one-off: migrate legacy schematic evidence to a hash manifest if its mtime check passes")
    args = ap.parse_args(argv)

    if args.attest_schematic:
        for line in attest_schematic_evidence():
            print("schematic evidence", line)

    if args.rerun_stale:
        print("reran:", ", ".join(rerun_stale()) or "nothing (evidence current)")
    run_checks(args.mode)
    blocked = requirement_blocks()
    g = gates(blocked)
    known = load_known()
    cls = classify(known)
    pending = [k["id"] for k in known if k["category"] == "pending_disposition"]
    variants = {"eval-cad": ["evaluation-board"], "compact-cad": ["compact-22mm"]}.get(args.mode, list(spec.VARIANTS))
    readiness = {v: release_check.readiness(v, entries, ROOT, pending) for v in variants} if args.mode != "bench" else {}

    if args.mode == "full":
        sync_requirement_gates(g)
        write_register(g, cls, readiness)
        release_check.write_report(readiness, REP, str(date.today()))
        dash = ROOT / "automation/dashboard/build_dashboard.py"
        if dash.is_file():
            s = importlib.util.spec_from_file_location("nubm44_dashboard", dash)
            module = importlib.util.module_from_spec(s)
            s.loader.exec_module(module)
            module.ROOT, module.OUT = ROOT, REP / "dashboard" / "index.html"
            module.main()
    else:
        out = ROOT / "build" / f"validation-{args.mode}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps({"mode": args.mode, "gates": g, "entries": entries,
                                   "readiness": readiness}, indent=1), encoding="utf-8")

    not_pass = [e for e in entries if e["status"] != "PASS" and e["id"] != "VAL-REQ-BLOCKED"]
    print(f"mode {args.mode}: {len(entries)} entries; not PASS: {len(not_pass)} "
          f"(known, unchanged: {len(cls['known'])}; new: {len(cls['new'])}; changed: {len(cls['changed'])})")
    for e in cls["new"] + cls["changed"]:
        print(f"  {'NEW' if e in cls['new'] else 'CHANGED'} {e['id']}: {e['status']} {str(e.get('detail', ''))[:150]}")
    for k in cls["resolved"]:
        print(f"  RESOLVED {k['id']} now passes: remove it from engineering/known-limitations.yaml")
    for k, v in g.items():
        print(f"  gate {k}: {v}")
    for v, r in readiness.items():
        print(f"  readiness {v}: {r['level']}" + (f" (next {r['next_level']}: {len(r['blockers'][r['next_level']])} blockers)"
                                                  if r["next_level"] else ""))
    if args.strict:
        return 0 if not not_pass else 1
    return 0 if not (cls["new"] or cls["changed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
