"""Build the component database and cost estimate from connectivity.yaml + verified supplier data.

Outputs: sourcing/components.csv, sourcing/alternatives.csv, sourcing/costs.csv
Supplier data comes only from research/component-candidates.csv (retrieved 2026-10-24) and the
lead-engineer lookups in research/source-index.md. Anything else is written as UNKNOWN; no stock or
price is ever estimated.
Run: .venv\\Scripts\\python.exe sourcing\\build_sourcing.py
"""
from __future__ import annotations

import csv
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import spec  # noqa: E402

OUT = ROOT / "sourcing"
U = "UNKNOWN"

# Ratings from manufacturer datasheets / series specifications (source IDs in research/source-index.md).
RATINGS = {
    "TPS552882RPMR": {"v": "VIN 2.7-36 V, VOUT 0.8-22 V", "i": "14 A min avg inductor limit (RILIM 20k)", "p": "-", "tol": "VREF +-1 %"},
    "INA186A2IDCKR": {"v": "VS 1.7-5.5 V, VCM -0.2..40 V", "i": "-", "p": "-", "tol": "gain +-1 %, VOS +-50 uV"},
    "ATTINY1616-MNR": {"v": "1.8-5.5 V", "i": "-", "p": "-", "tol": "-"},
    "SISS23DN-T1-GE3": {"v": "-20 V", "i": "see datasheet", "p": "-", "tol": "Rds 6.3 mOhm max @ -2.5 V"},
    "SISS80DN-T1-GE3": {"v": "20 V", "i": "see datasheet", "p": "-", "tol": "Rds 1.15 mOhm max @ 4.5 V"},
    "DMG1012T-7": {"v": "20 V", "i": "0.63 A", "p": "-", "tol": "-"},
    "XGL5030-102MEC": {"v": "-", "i": "Isat 10.2 A (20 %) / 14 A (30 %), Irms 12.8 A", "p": "-", "tol": "+-20 %"},
    "MCS1632R010FER": {"v": "-", "i": "-", "p": "1 W", "tol": "+-1 %"},
    "PMEG4010CEJ,115": {"v": "40 V", "i": "1 A", "p": "-", "tol": "-"},
    "RB521S30T1G": {"v": "30 V", "i": "200 mA", "p": "-", "tol": "-"},
    "BZX585-C6V2": {"v": "6.2 V Zener", "i": "-", "p": "300 mW", "tol": "+-5 %"},
    "CL21A226MOQNNNE": {"v": "16 V", "i": "-", "p": "-", "tol": "+-20 % X5R"},
    "CL10A106KP8NNNC": {"v": "10 V", "i": "-", "p": "-", "tol": "+-10 % X5R"},
    "CL05B104KO5NNNC": {"v": "16 V", "i": "-", "p": "-", "tol": "+-10 % X7R"},
    "CL05B563KO5NNNC": {"v": "16 V", "i": "-", "p": "-", "tol": "+-10 % X7R"},
    "GRM033R61A104KE15D": {"v": "10 V", "i": "-", "p": "-", "tol": "+-10 % X5R"},
    "GRM1555C1H681JA01D": {"v": "50 V", "i": "-", "p": "-", "tol": "+-5 % C0G"},
    "GRM0335C1H681JA01D": {"v": "50 V", "i": "-", "p": "-", "tol": "+-5 % C0G"},
    "NCP15XH103F03RC": {"v": "-", "i": "-", "p": "-", "tol": "+-1 %, B 3380 K"},
    "NCP03XH103F05RL": {"v": "-", "i": "-", "p": "-", "tol": "+-1 %, B 3380 K"},
}
SERIES = [  # commodity resistor series ratings (Yageo RC/RT series specifications)
    (r"^RC0201FR-", {"v": "25 V", "i": "-", "p": "1/20 W", "tol": "+-1 %"}),
    (r"^RC0402FR-", {"v": "50 V", "i": "-", "p": "1/16 W", "tol": "+-1 %"}),
    (r"^RT0402BRD", {"v": "50 V", "i": "-", "p": "1/16 W", "tol": "+-0.1 %, 25 ppm/K"}),
]
# Supplier facts retrieved by the lead engineer (not in component-candidates.csv)
EXTRA = {
    "TPS552882RPMR": {"supplier": "TI store", "spn": "TPS552882RPMR", "stock": "2950 (TI store, 2026-10-24, PWR-20)", "price": U},
    "XGL5030-102MEC": {"supplier": "LCSC / Coilcraft", "spn": "C6937849", "stock": U, "price": U},
    "MCS1632R010FER": {"supplier": "DigiKey", "spn": "MCS1632R010FER", "stock": U, "price": U},
}
ALTERNATES = [
    ("RS1", "MCS1632R010FER", "RALEC", "LR1206-21R010F4", "LCSC C154635", "Same 1206 land pattern; 10 mOhm 1 W 1 %. Verify TCR/datasheet."),
    ("Q1", "SISS23DN-T1-GE3", "Diodes Inc.", "DMP2005UFG-13", "LCSC C2922355", "PowerDI3333-8: DIFFERENT land pattern; footprint change and review required."),
    ("Q2,Q3", "SISS80DN-T1-GE3", "Diodes Inc.", "DMN22M5UFG-7", "LCSC C3289380 (stock 0 on 2026-10-24)", "PowerDI3333-8: DIFFERENT land pattern; 2.0 mOhm @4.5 V."),
    ("Q2,Q3", "SISS80DN-T1-GE3", "Infineon", "IRLHM620TRPBF", "LCSC C538149", "EOL notice in datasheet: not for new designs; PQFN 3.3x3.3 land pattern differs."),
    ("L1", "XGL5030-102MEC", "Coilcraft", "XAL5030-102MEC", U, "Same 5.28 x 5.48 mm land pattern family; check Isat/DCR."),
    ("U2", "INA186A2IDCKR", "Texas Instruments", "INA186A3IDCKR", "LCSC C2058245", "Gain 100: requires FB divider recalculation (R8/R9)."),
]


def norm(mpn: str) -> str:
    return mpn.upper().replace(",115", "").replace("-T1-GE3", "")


def research_index() -> dict:
    rows = list(csv.DictReader(open(ROOT / "research/component-candidates.csv", encoding="utf-8")))
    return {norm(r["mpn"]): r for r in rows}


def ratings(mpn: str) -> dict:
    if mpn in RATINGS:
        return RATINGS[mpn]
    for pat, r in SERIES:
        if re.match(pat, mpn):
            return r
    return {"v": U, "i": U, "p": U, "tol": U}


HEADER = ["variant", "reference_designators", "quantity", "manufacturer", "mpn", "value", "tolerance",
          "voltage_rating", "current_rating", "power_rating", "package", "footprint", "datasheet",
          "preferred_supplier", "supplier_part_number", "availability", "approx_price_usd",
          "data_retrieved", "verified", "approved_alternatives", "notes"]


def compute() -> tuple[list, list]:
    """Component rows and cost lines exactly as build() writes them (sourcing/check_sourcing.py compares them)."""
    idx = research_index()
    rows, costs = [], []
    for variant in spec.VARIANTS:
        groups: "OrderedDict[str, list]" = OrderedDict()
        for p in spec.parts_for(variant):
            if not p.get("in_bom", True):
                continue
            groups.setdefault(p["mpn"], []).append(p)
        for mpn, parts in groups.items():
            p0 = parts[0]
            refs = ",".join(p["ref"] for p in parts)
            r = idx.get(norm(mpn))
            ex = EXTRA.get(mpn)
            rt = ratings(mpn)
            if r and r["lcsc_pn"] not in ("", U):
                sup, spn, stock, price, ret, ver = "LCSC", r["lcsc_pn"], r["lcsc_stock"] or U, r["lcsc_price_usd_qty"] or U, r["data_retrieved"], r["verified"]
            elif ex:
                sup, spn, stock, price, ret, ver = ex["supplier"], ex["spn"], ex["stock"], ex["price"], "2026-10-24", "PARTIAL"
            else:
                sup, spn, stock, price, ret, ver = U, U, U, U, "-", "NO"
            alts = "; ".join(f"{a[2]} {a[3]}" for a in ALTERNATES if mpn == a[1])
            note = "DNP: hand-fitted battery spring, select to suit host" if p0.get("dnp") else (
                "commodity part: supplier data not verified, choose an equivalent at order time" if ver == "NO" else "")
            rows.append([variant, refs, len(parts), p0["mfr"], mpn, p0["value"], rt["tol"], rt["v"], rt["i"], rt["p"],
                         p0["footprint"].split(":", 1)[-1], p0["footprint"], p0.get("datasheet", "~"), sup, spn, stock,
                         price, ret, ver, alts or "-", note])
            unit = U
            m = re.search(r"\$([0-9.]+)", price or "")
            if m:
                unit = float(m.group(1))
            costs.append([variant, mpn, len(parts), unit, "" if unit == U else round(unit * len(parts), 4), price])
    return rows, costs


def build() -> None:
    rows, costs = compute()
    with open(OUT / "components.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(HEADER); w.writerows(rows)
    with open(OUT / "alternatives.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["references", "primary_mpn", "alt_manufacturer", "alt_mpn", "alt_supplier_pn", "notes"])
        w.writerows(ALTERNATES)
    with open(OUT / "costs.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "mpn", "qty_per_board", "unit_price_usd_small_qty", "line_cost_usd", "price_basis"])
        w.writerows(costs)
        for variant in spec.VARIANTS:
            known = [c for c in costs if c[0] == variant and c[3] != U]
            unknown = [c for c in costs if c[0] == variant and c[3] == U]
            w.writerow([variant, "SUBTOTAL (known prices only)", "", "",
                        round(sum(c[4] for c in known), 2),
                        f"{len(known)} lines priced, {len(unknown)} lines UNKNOWN; NOT a quote"])
    print(f"components.csv rows: {len(rows)}; costs lines: {len(costs)}")


if __name__ == "__main__":
    build()
