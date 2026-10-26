"""Automated sourcing and rating checks (audit AUD-SRC-01/02, AUD-MFG-03).

Compares the sourcing records with the authoritative design sources and checks part ratings against the circuit:

- components.csv / costs.csv equal what build_sourcing.py derives from connectivity.yaml (stale CSV = FAIL);
- the package size encoded in each MPN matches its footprint (FAIL) and its description (WARN);
- capacitor voltage ratings against the worst voltage across each capacitor (FAIL below it, WARN below 1.5x);
- resistor power against the normal-operation voltage (FAIL above rating) and a single-fault voltage (WARN);
- inductor and shunt ratings in the sourcing table against parameters.yaml (FAIL on mismatch);
- datasheet traceability, UNKNOWN supplier data and data age (INFO/WARN).

Net voltages come from parameters.yaml and the cited datasheets; the MPN decode tables follow the manufacturers'
part-numbering systems (Yageo RC/RT, Murata GRM/NCP, Samsung CL) and must be confirmed against each datasheet.
Writes sourcing/sourcing-check.json and sourcing/sourcing-check.md; exit 1 when any FAIL is found.
Run: .venv\\Scripts\\python.exe sourcing\\check_sourcing.py
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import spec  # noqa: E402

OUT = ROOT / "sourcing"
DATA_MAX_AGE_DAYS = 90

P = yaml.safe_load((ROOT / "engineering/design/parameters.yaml").read_text(encoding="utf-8"))
V_BAT = P["battery"]["v_full"]                                   # 4.2 V
V_OUT_NORMAL = 4.8                                               # highest diode corner incl. shunt and wiring (CALC-15 basis)
V_OUT_FAULT = 7.3                                                # Zener backstop upper bound, DD-05
V_VCC = 5.4                                                      # TPS552882 VCC max, SLVSFC5 p.6

# (normal, single-fault) worst DC voltage of each net to GND, with its basis
NET_V = {
    "BAT_SPRING": (V_BAT, V_BAT, "battery full (parameters.yaml)"), "VBAT": (V_BAT, V_BAT, "battery full"),
    "VMCU": (V_BAT, V_BAT, "VBAT through D2"), "Q1_G": (V_BAT, V_BAT, "reverse-FET gate, bounded by VBAT"),
    "VOUT": (V_OUT_NORMAL, V_OUT_FAULT, "max diode corner; Zener backstop 7.3 V (DD-05)"),
    "LD_P": (V_OUT_NORMAL, V_OUT_FAULT, "as VOUT"), "ISP_K": (V_OUT_NORMAL, V_OUT_FAULT, "as VOUT"),
    "ISN_K": (V_OUT_NORMAL, V_OUT_FAULT, "as VOUT"), "SW1": (V_BAT, V_BAT, "buck switch node"),
    "SW2": (V_OUT_NORMAL, V_OUT_FAULT, "boost switch node swings to VOUT"),
    "VCC5": (V_VCC, V_VCC, "TPS552882 VCC max (SLVSFC5 p.6)"),
    "EN_UVLO": (V_BAT * 33.2 / 83.1, V_BAT, "divider R5/R6; fault: R6 open"),
    "CS_OUT": (2.6, V_BAT, "0.5 V/A at the 5.2 A ceiling; fault: INA186 output at its VBAT supply"),
    "FB": (1.3, V_BAT, "1.2 V regulation"), "COMP": (2.5, V_VCC, "COMP clamp"), "COMP_RC": (2.5, V_VCC, "COMP clamp"),
    "VBAT_SENSE": (V_BAT / 2, V_BAT, "VBAT/2"), "VOUT_SENSE": (V_OUT_NORMAL / 6, V_OUT_FAULT, "VOUT/6"),
    "NTC_PWR": (V_BAT, V_BAT, "MCU pin at VMCU"), "NTC_BRD": (V_BAT, V_BAT, "MCU pin"), "NTC_LD": (V_BAT, V_BAT, "MCU pin"),
    "IND_OUT": (V_BAT, V_BAT, "MCU pin"), "IND_PAD": (V_BAT, V_BAT, "external LED pad"),
    "LASER_EN_N": (V_BAT, V_BAT, "MCU pin / R17"), "INTLK_N": (V_BAT, V_BAT, "R18 pull-up to VBAT"),
    "INTLK_MCU": (V_BAT, V_BAT, "MCU pin"), "OV_G": (V_OUT_FAULT - 6.2, V_OUT_FAULT, "Zener D3 6.2 V below VOUT"),
    "FSW": (1.0, V_VCC, "1.0 V pin"), "ILIM": (0.6, V_VCC, "0.6 V pin"),
}
# voltage across two-terminal parts whose terminals are both non-ground
PAIR_V = {frozenset(("BOOT1", "SW1")): (V_VCC, V_VCC, "bootstrap: VCC across the capacitor"),
          frozenset(("BOOT2", "SW2")): (V_VCC, V_VCC, "bootstrap: VCC across the capacitor")}

# MPN -> (case size, dielectric, rated volts) decoders
SIZE_CODES = [(r"^RC0201|^GRM03|^NCP03", "0201"), (r"^RC0402|^RT0402|^GRM15|^CL05|^NCP15", "0402"),
              (r"^CL10", "0603"), (r"^CL21", "0805"), (r"^MCS1632", "1206")]
MURATA_V = {"0J": 6.3, "1A": 10, "1C": 16, "1E": 25, "1H": 50}
MURATA_D = {"R6": "X5R", "R7": "X7R", "5C": "C0G"}
SAMSUNG_V = {"Q": 6.3, "P": 10, "O": 16, "A": 25, "B": 50}
SAMSUNG_D = {"A": "X5R", "B": "X7R", "C": "C0G"}
RESISTOR_W = {"0201": 0.05, "0402": 0.0625}                      # Yageo RC/RT series ratings (build_sourcing SERIES)


def decode(mpn: str) -> dict:
    out = {}
    for pat, size in SIZE_CODES:
        if re.match(pat, mpn):
            out["size"] = size
    m = re.match(r"^GRM\d{3}([0-9A-Z]{2})([0-9A-Z]{2})", mpn)
    if m:
        out["dielectric"], out["volts"] = MURATA_D.get(m[1]), MURATA_V.get(m[2])
    m = re.match(r"^CL\d\d([ABC])\d{3}[A-Z]([A-Z])", mpn)
    if m:
        out["dielectric"], out["volts"] = SAMSUNG_D.get(m[1]), SAMSUNG_V.get(m[2])
    return out


def ohms(value: str) -> float | None:
    m = re.fullmatch(r"([0-9.]+)\s*([mkM]?)", value.strip())
    if not m:
        return None
    return float(m[1]) * {"": 1, "m": 1e-3, "k": 1e3, "M": 1e6}[m[2]]


def footprint_size(fp: str) -> str | None:
    m = re.search(r"_(0201|0402|0603|0805|1206)_", fp)
    return m[1] if m else None


def across(pins: dict) -> tuple[float, float, str] | None:
    nets = [n for n in pins.values() if n not in ("NC",)]
    if len(nets) != 2:
        return None
    a, b = nets
    if frozenset(nets) in PAIR_V:
        return PAIR_V[frozenset(nets)]
    if "GND" in nets:
        other = b if a == "GND" else a
        return NET_V.get(other)
    va, vb = NET_V.get(a), NET_V.get(b)
    if va and vb:   # series part: normal = difference of normal levels, fault = the other side shorted to GND
        return (abs(va[0] - vb[0]), max(va[1], vb[1]), f"series {a}-{b}; fault: one side shorted to GND")
    return None


def load_build_sourcing():
    s = importlib.util.spec_from_file_location("nubm44_build_sourcing", ROOT / "sourcing" / "build_sourcing.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def check() -> dict:
    findings = []

    def add(sev, ref, check_name, detail):
        findings.append({"severity": sev, "ref": ref, "check": check_name, "detail": detail})

    bs = load_build_sourcing()
    rows, costs = bs.compute()
    try:
        with open(OUT / "components.csv", encoding="utf-8", newline="") as fh:
            current = list(csv.reader(fh))
        if current[0] != bs.HEADER or [list(map(str, r)) for r in rows] != current[1:]:
            add("FAIL", "components.csv", "stale", "differs from connectivity.yaml + research data: run sourcing/build_sourcing.py")
    except (OSError, IndexError, csv.Error) as exc:
        add("FAIL", "components.csv", "missing", str(exc))

    for variant in spec.VARIANTS:
        for p in spec.parts_for(variant):
            if not p.get("in_bom", True):
                continue
            ref, mpn, fp, desc = p["ref"], str(p["mpn"]), p["footprint"], str(p.get("desc", ""))
            tag = f"{variant}:{ref}"
            d = decode(mpn)
            fsize = footprint_size(fp)
            if d.get("size") and fsize and d["size"] != fsize:
                add("FAIL", tag, "package", f"{mpn} is a {d['size']} part on footprint {fp}")
            dsize = re.findall(r"\b(0201|0402|0603|0805|1206)\b", desc)
            if d.get("size") and dsize and d["size"] not in dsize:
                add("WARN", tag, "description", f"description says {'/'.join(dsize)} but {mpn} is {d['size']} (AUD-MFG-03)")
            dv = re.search(r"\b(\d+(?:\.\d+)?) V\b", desc)
            if d.get("volts") and dv and float(dv[1]) != d["volts"]:
                add("WARN", tag, "description", f"description says {dv[1]} V but {mpn} is rated {d['volts']:g} V")
            ddiel = re.search(r"\b(X5R|X7R|C0G)\b", desc)
            if d.get("dielectric") and ddiel and ddiel[1] != d["dielectric"]:
                add("WARN", tag, "description", f"description says {ddiel[1]} but {mpn} is {d['dielectric']}")
            v = across(p["pins"])
            if ref.startswith("C") and d.get("volts"):
                if v is None:
                    add("INFO", tag, "capacitor voltage", "net voltage not tabulated")
                elif d["volts"] < v[1]:
                    add("FAIL", tag, "capacitor voltage", f"{d['volts']:g} V rating below {v[1]:.2f} V ({v[2]})")
                elif d["volts"] < 1.5 * v[1]:
                    add("WARN", tag, "capacitor voltage",
                        f"{d['volts']:g} V rating < 1.5 x {v[1]:.2f} V ({v[2]}); check DC-bias capacitance")
            if ref.startswith("R") and not ref.startswith("RS") and not ref.startswith("RT"):
                r_ohm, size = ohms(str(p["value"])), d.get("size") or fsize
                rating = RESISTOR_W.get(size or "")
                if r_ohm and rating and v:
                    p_norm, p_fault = v[0] ** 2 / r_ohm, v[1] ** 2 / r_ohm
                    if p_norm > rating:
                        add("FAIL", tag, "resistor power", f"{p_norm * 1e3:.1f} mW in normal operation > {rating * 1e3:g} mW")
                    elif p_fault > rating:
                        add("WARN", tag, "resistor power",
                            f"{p_fault * 1e3:.1f} mW in a single fault ({v[2]}) > {rating * 1e3:g} mW rating")
    # parameters.yaml against the sourcing rating table
    ind, shunt = P["components"]["inductor"], P["components"]["shunt"]
    text = bs.RATINGS.get(ind["part"], {}).get("i", "")
    for key, label in (("isat_20pct_a", "Isat"), ("isat_30pct_a", "Isat"), ("irms_20c_a", "Irms")):
        if f"{ind[key]:g} A" not in text:
            add("FAIL", "L1", "rating table", f"sourcing rating '{text}' lacks {label} {ind[key]:g} A from parameters.yaml")
    if f"{shunt['p_rated_w']:g} W" not in bs.RATINGS.get(shunt["part"], {}).get("p", ""):
        add("FAIL", "RS1", "rating table", "shunt power rating differs from parameters.yaml")
    i_fault = max(P["converter"]["isp_isn_limit_v"]) / shunt["r_ohm"]
    p_shunt = i_fault ** 2 * shunt["r_ohm"]
    if p_shunt > shunt["p_rated_w"]:
        add("FAIL", "RS1", "shunt power", f"{p_shunt:.2f} W at the {i_fault:.1f} A ceiling > {shunt['p_rated_w']} W")
    # supplier data and traceability
    today = date.today()
    for r in rows:
        variant, refs, mpn, datasheet, retrieved, stock, price = r[0], r[1], r[4], r[12], r[17], r[15], r[16]
        tag = f"{variant}:{refs}"
        if mpn in ("UNKNOWN", "-"):
            add("INFO", tag, "mpn", "no MPN (hand-fitted or PCB feature)")
            continue
        if "UNKNOWN" in (stock, price):
            add("INFO", tag, "supplier data", f"{mpn}: stock or price UNKNOWN; confirm at order time")
        if retrieved not in ("-", "") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", retrieved):
            age = (today - date.fromisoformat(retrieved)).days
            if age > DATA_MAX_AGE_DAYS:
                add("WARN", tag, "data age", f"{mpn}: supplier data {age} days old (> {DATA_MAX_AGE_DAYS})")
        if datasheet in ("~", "", None) and not re.match(r"^(RC0|RT0)", mpn):
            add("INFO", tag, "datasheet", f"{mpn}: no datasheet URL in connectivity.yaml")
    for a in bs.ALTERNATES:
        if "DIFFERENT land pattern" in a[5]:
            add("INFO", a[0], "alternate", f"{a[2]} {a[3]} is not a drop-in replacement (different land pattern)")
    priced = {v: [c for c in costs if c[0] == v and c[3] != "UNKNOWN"] for v in spec.VARIANTS}
    summary = {v: {"lines": sum(1 for c in costs if c[0] == v), "priced_lines": len(priced[v]),
                   "known_subtotal_usd": round(sum(c[4] for c in priced[v]), 2)} for v in spec.VARIANTS}
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("FAIL", "WARN", "INFO")}
    return {"date": str(today), "status": "FAIL" if counts["FAIL"] else "PASS", "counts": counts,
            "cost_summary": summary, "findings": findings,
            "note": "Ratings and decode tables must be confirmed against each datasheet; stock and prices are not verified."}


def write(result: dict) -> None:
    (OUT / "sourcing-check.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    c = result["counts"]
    lines = ["# Sourcing check", "", f"Generated by `sourcing/check_sourcing.py` on {result['date']}: **{result['status']}** "
             f"({c['FAIL']} FAIL, {c['WARN']} WARN, {c['INFO']} INFO). {result['note']}", "",
             "| Variant | BOM lines | Priced lines | Known subtotal (USD, not a quote) |", "|---|---|---|---|"]
    for v, s in result["cost_summary"].items():
        lines.append(f"| {v} | {s['lines']} | {s['priced_lines']} | {s['known_subtotal_usd']} |")
    for sev in ("FAIL", "WARN", "INFO"):
        rows = [f for f in result["findings"] if f["severity"] == sev]
        if rows:
            lines += ["", f"## {sev}", "", "| Part | Check | Detail |", "|---|---|---|"]
            lines += [f"| {f['ref']} | {f['check']} | {f['detail']} |" for f in rows]
    (OUT / "sourcing-check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = check()
    write(result)
    print(f"sourcing check: {result['status']} {result['counts']}")
    for f in result["findings"]:
        if f["severity"] != "INFO":
            print(f"  {f['severity']} {f['ref']} {f['check']}: {f['detail']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
