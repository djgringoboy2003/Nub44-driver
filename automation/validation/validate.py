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
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths, spec  # noqa: E402

REP = ROOT / "reports"
entries: list[dict] = []


def add(eid, item, method, status, evidence, detail=""):
    entries.append({"id": eid, "item": item, "method": method, "status": status, "evidence": evidence,
                    "detail": detail})
    return status


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
    d = load_json(REP / f"schematic-{variant}.json")
    if d is None:
        return add(f"VAL-SCH-{variant}", f"Schematic ERC + netlist ({variant})", "CAD", "NOT RUN", "")
    add(f"VAL-ERC-{variant}", f"ERC ({variant}): errors {d['erc_errors']}, warnings {d['erc_warnings']}", "CAD",
        "PASS" if d["erc_errors"] == 0 and d["erc_warnings"] == 0 else "FAIL", f"reports/erc-{variant}.json")
    return add(f"VAL-NET-{variant}", f"Netlist equals connectivity.yaml ({variant})", "CAD",
               "PASS" if not d["connectivity_differences"] else "FAIL", f"reports/schematic-{variant}.json",
               f"{len(d['connectivity_differences'])} differences")


def drc(variant):
    d = load_json(REP / f"drc-{variant}.json")
    pcb = paths.HARDWARE / variant / "nubm44_driver.kicad_pcb"
    if d is None or not pcb.exists():
        add(f"VAL-ROUTE-{variant}", f"PCB placed and fully routed ({variant})", "CAD", "NOT RUN", "")
        return add(f"VAL-DRC-{variant}", f"DRC ({variant})", "CAD", "NOT RUN", "")
    viol = d.get("violations", [])
    errors = [v for v in viol if v["severity"] == "error"]
    unconn = d.get("unconnected_items", [])
    parity = d.get("schematic_parity", [])
    add(f"VAL-ROUTE-{variant}", f"PCB placed and fully routed ({variant})", "CAD",
        "PASS" if not unconn else "FAIL", f"reports/drc-{variant}.json", f"{len(unconn)} unconnected items")
    add(f"VAL-PARITY-{variant}", f"PCB matches schematic ({variant})", "CAD",
        "PASS" if not parity else "FAIL", f"reports/drc-{variant}.json", f"{len(parity)} parity issues")
    types = {}
    for v in errors:
        types[v["type"]] = types.get(v["type"], 0) + 1
    return add(f"VAL-DRC-{variant}", f"DRC errors ({variant})", "CAD", "PASS" if not errors else "FAIL",
               f"reports/drc-{variant}.json", f"{len(errors)} errors {types}")


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
    d = load_json(paths.MANUFACTURING / "pcbway" / variant / "reports" / "export-check.json")
    if d is None:
        return add(f"VAL-EXPORT-{variant}", f"PCBWay export package ({variant})", "CAD", "NOT RUN", "")
    return add(f"VAL-EXPORT-{variant}", f"PCBWay export package internally consistent ({variant})", "CAD",
               d["status"], f"manufacturing/pcbway/{variant}/reports/export-check.json",
               "; ".join(d["problems"])[:200])


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

    def ok(prefixes):
        rel = [s for k, s in st.items() if any(k.startswith(p) for p in prefixes)]
        return bool(rel) and all(s == "PASS" for s in rel)

    g = {}
    g["A"] = "PASS" if st.get("VAL-A1") == "PASS" else "OPEN"
    g["B"] = "PASS" if ok(["VAL-ERC-", "VAL-NET-"]) else "OPEN"
    g["C"] = "PASS" if ok(["VAL-SIM-"]) else "OPEN"
    for v in spec.VARIANTS:
        g[f"D ({v})"] = "PASS" if st.get(f"VAL-ROUTE-{v}") == "PASS" else "OPEN"
        g[f"E ({v})"] = "PASS" if st.get(f"VAL-DRC-{v}") == "PASS" and st.get(f"VAL-PARITY-{v}") == "PASS" else "OPEN"
        files_ok = st.get(f"VAL-EXPORT-{v}") == "PASS"
        if files_ok and g[f"E ({v})"] == "PASS" and g["B"] == "PASS":
            g[f"F ({v})"] = "HELD (owner decisions: " + ", ".join(blocked) + ")" if blocked else "PASS"
        else:
            g[f"F ({v})"] = "OPEN"
    g["G"] = "OPEN: requires assembled-prototype testing (cannot be closed by software)"
    return g


def main() -> int:
    research()
    calculations()
    for v in spec.VARIANTS:
        schematic(v)
        drc(v)
        exports(v)
    simulation()
    firmware()
    blocked = requirement_blocks()
    g = gates(blocked)
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
    fails = [e for e in entries if e["status"] in ("FAIL", "NOT RUN") and e["id"] != "VAL-REQ-BLOCKED"]
    print(f"{len(entries)} entries; FAIL/NOT RUN: {len(fails)}")
    for k, v in g.items():
        print(f"  gate {k}: {v}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
