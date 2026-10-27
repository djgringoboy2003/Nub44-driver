"""Derive a JLCPCB upload package from the verified PCBWay review package. Never places an order.

Inputs are the files of manufacturing/pcbway/<variant>/ exactly as export_pcbway.py wrote and hashed them, so the
Gerber and drill bytes are identical to the PCBWay package (nothing is re-plotted). The tool refuses a package whose
hashes no longer match its export-check, a failed export and an incomplete board (DRAFT_REVIEW_INCOMPLETE_BOARD).

Outputs in manufacturing/jlcpcb/<variant>/:
  <variant>-jlcpcb-gerbers.zip   flat ZIP: 11 Gerber layers + PTH/NPTH Excellon drill files (no PDFs, no job file)
  BOM_JLCPCB.csv                 Comment, Designator, Footprint, JLCPCB Part #, Manufacturer, MPN (DNP parts omitted)
  CPL_JLCPCB.csv                 Designator, Mid X, Mid Y, Layer, Rotation (same origin and signs as the PCBWay CPL)
  README.md                      what is and is not verified
  reports/jlcpcb-check.json      source hashes, output hashes, consistency checks

LCSC/JLCPCB part numbers are filled only where research recorded one (sourcing/components.csv, 2026-10-24); the
rest are blank and must be matched in JLCPCB's BOM tool. Rotations are KiCad's; JLCPCB's library orientation can
differ for some packages, so every part must be checked in JLCPCB's placement preview before ordering.

    .venv\\Scripts\\python.exe automation\\export\\export_jlcpcb.py --variant evaluation-board
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ("compact-22mm", "evaluation-board")
BOM_COLUMNS = ["Comment", "Designator", "Footprint", "JLCPCB Part #", "Manufacturer", "MPN"]
CPL_COLUMNS = ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def source_problems(pkg: Path, check: dict) -> list[str]:
    problems = []
    if check.get("status") != "PASS":
        problems.append("PCBWay export check is not PASS")
    if check.get("package_class") != "DRAFT_REVIEW" or not (check.get("cad_state") or {}).get("complete"):
        problems.append("board is not complete (incomplete-board package): no JLCPCB files are made for it")
    for rel, digest in (check.get("file_sha256") or {}).items():
        p = pkg / rel
        if not p.is_file() or sha256(p) != digest:
            problems.append(f"PCBWay package file changed or missing since its export check: {rel}")
    return problems


def lcsc_numbers(variant: str, root: Path) -> dict[str, str]:
    out = {}
    for r in read_csv(root / "sourcing" / "components.csv"):
        if r["variant"] == variant and r["preferred_supplier"].startswith("LCSC") and re.fullmatch(r"C\d+", r["supplier_part_number"]):
            out[r["mpn"]] = r["supplier_part_number"]
    return out


def build(variant: str, root: Path = ROOT, out: Path | None = None) -> dict:
    pkg = root / "manufacturing" / "pcbway" / variant
    out = out or root / "manufacturing" / "jlcpcb" / variant
    check = json.loads((pkg / "reports" / "export-check.json").read_text(encoding="utf-8"))
    result = {"variant": variant, "date": str(date.today()), "status": "FAIL", "problems": source_problems(pkg, check),
              "source_package": pkg.relative_to(root).as_posix(),
              "source_sha256": {rel: check["file_sha256"][rel] for rel in sorted(check.get("file_sha256", {}))
                                if rel.startswith(("gerbers/", "drill/", "assembly/BOM_PCBWay_template.csv",
                                                   "assembly/CPL_PCBWay.csv"))},
              "manufacturing_release": False, "orders_placed_by_tooling": False}
    if result["problems"]:
        return result
    (out / "reports").mkdir(parents=True, exist_ok=True)
    # flat fabrication ZIP with the identical Gerber and drill bytes
    fab = sorted(p for p in (pkg / "gerbers").iterdir() if p.suffix != ".gbrjob") + sorted((pkg / "drill").glob("*.drl"))
    zpath = out / f"{variant}-jlcpcb-gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in fab:
            z.write(p, p.name)
    # BOM (DNP parts omitted: JLCPCB has no do-not-place column)
    lcsc = lcsc_numbers(variant, root)
    groups: dict[tuple, dict] = {}
    for r in read_csv(pkg / "assembly" / "BOM_PCBWay_template.csv"):
        if r["Type"] == "DNS":
            continue
        key = (r["*Mfg Part #"], r["*Package/Footprint "])
        g = groups.setdefault(key, {"value": r["Description / Value"].split(" - ", 1)[0], "mfr": r["Manufacturer"],
                                    "refs": []})
        g["refs"] += [x.strip() for x in r["*Designator"].split(",")]
    order = lambda ref: (ref.rstrip("0123456789"), int(ref[len(ref.rstrip("0123456789")):] or 0))  # noqa: E731
    bom_rows = [[f"{g['value']} {mpn}", ",".join(sorted(g["refs"], key=order)), fp, lcsc.get(mpn, ""), g["mfr"], mpn]
                for (mpn, fp), g in sorted(groups.items(), key=lambda kv: order(sorted(kv[1]["refs"], key=order)[0]))]
    with open(out / "BOM_JLCPCB.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(BOM_COLUMNS); w.writerows(bom_rows)
    # CPL (same coordinates as the PCBWay CPL; rotation normalised to 0..360)
    cpl_rows = []
    for r in read_csv(pkg / "assembly" / "CPL_PCBWay.csv"):
        cpl_rows.append([r["designator"], r["pos_x"], r["pos_y"], "Top" if r["side"] == "top" else "Bottom",
                         f"{float(r['rotation']) % 360:.2f}"])
    with open(out / "CPL_JLCPCB.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(CPL_COLUMNS); w.writerows(cpl_rows)
    # independent consistency checks
    problems = []
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if z.testzip() or sorted(names) != sorted(p.name for p in fab):
            problems.append("ZIP incomplete or corrupt")
        for p in fab:
            if hashlib.sha256(z.read(p.name)).hexdigest() != sha256(p):
                problems.append(f"ZIP member differs from the PCBWay package: {p.name}")
    if len([n for n in names if re.search(r"\.(gtl|g1|g2|gbl)$", n)]) != 4 or not any(n.endswith("-PTH.drl") for n in names):
        problems.append("ZIP lacks a copper layer or the plated drill file")
    pcb_cpl = {r["designator"]: r for r in read_csv(pkg / "assembly" / "CPL_PCBWay.csv")}
    jlc_cpl = {r["Designator"]: r for r in read_csv(out / "CPL_JLCPCB.csv")}
    if set(pcb_cpl) != set(jlc_cpl):
        problems.append("CPL designators differ from the PCBWay CPL")
    for ref, r in jlc_cpl.items():
        s = pcb_cpl.get(ref, {})
        if (r["Mid X"], r["Mid Y"]) != (s.get("pos_x"), s.get("pos_y")) or \
                abs((float(r["Rotation"]) - float(s.get("rotation", "nan"))) % 360) > 1e-6:
            problems.append(f"CPL entry differs from the PCBWay CPL: {ref}")
    bom_refs = sorted(x.strip() for r in read_csv(out / "BOM_JLCPCB.csv") for x in r["Designator"].split(","))
    if bom_refs != sorted(jlc_cpl):
        problems.append("BOM designators differ from the placed parts")
    blank = [r[5] for r in bom_rows if not r[3]]
    readme = [f"# JLCPCB upload files: {variant} (DRAFT, review before ordering)", "",
              f"Derived on {result['date']} by `automation/export/export_jlcpcb.py` from `{result['source_package']}`, whose",
              "export check passed. The Gerber and drill bytes are identical to the PCBWay package. No tool places an order.", "",
              "| Upload | File |", "|---|---|",
              f"| Gerber/drill (fabrication) | `{zpath.name}` |", "| Assembly BOM | `BOM_JLCPCB.csv` |",
              "| Assembly placement (CPL) | `CPL_JLCPCB.csv` |", "",
              f"- {len(bom_rows)} BOM lines, {len(cpl_rows)} placed parts, all on the top side; J1 (wire pad) is not placed.",
              f"- JLCPCB part numbers are filled for {len(bom_rows) - len(blank)} lines (LCSC numbers recorded on 2026-10-24); "
              f"match the other {len(blank)} lines in JLCPCB's BOM tool by MPN, and confirm stock for every line.",
              "- Rotations are KiCad's. **Check every part in JLCPCB's placement preview** (pin 1 of U1, U2, U3; the PowerPAK "
              "MOSFETs Q1-Q3; diodes D1-D3; RS1's Kelvin pads) and correct it there before paying.",
              "- Parts not confirmed at LCSC on 2026-10-24: TPS552882RPMR (U1), SISS80DN-T1-GE3 (Q2, Q3: JLC stock 0), "
              "MCS1632R010FER (RS1). Use JLCPCB global sourcing or consign them; do not accept substitutes without review.",
              "- Board options, layer order and the pre-order checks: `documentation/ordering-guide.md`."]
    (out / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    outputs = [zpath, out / "BOM_JLCPCB.csv", out / "CPL_JLCPCB.csv", out / "README.md"]
    result.update(status="PASS" if not problems else "FAIL", problems=problems, bom_lines=len(bom_rows),
                  cpl_parts=len(cpl_rows), lines_without_part_number=blank,
                  outputs={p.relative_to(root).as_posix(): sha256(p) for p in outputs})
    (out / "reports" / "jlcpcb-check.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return result


def check_problems(variant: str, root: Path = ROOT) -> list[str] | None:
    """For the validator: None when no JLCPCB package exists, else the reasons it cannot be trusted."""
    report = root / "manufacturing" / "jlcpcb" / variant / "reports" / "jlcpcb-check.json"
    if not report.is_file():
        return None
    try:
        d = json.loads(report.read_text(encoding="utf-8"))
    except ValueError:
        return ["malformed jlcpcb-check.json"]
    problems = [] if d.get("status") == "PASS" else ["JLCPCB package check is not PASS"]
    for rel, digest in (d.get("source_sha256") or {}).items():
        p = root / d.get("source_package", "") / rel
        if not p.is_file() or sha256(p) != digest:
            problems.append(f"stale: PCBWay source {rel} changed; rerun export_jlcpcb.py")
    for rel, digest in (d.get("outputs") or {}).items():
        p = root / rel
        if not p.is_file() or sha256(p) != digest:
            problems.append(f"JLCPCB output {rel} differs from its check")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="evaluation-board", choices=VARIANTS)
    r = build(ap.parse_args().variant)
    print(f"{r['variant']}: JLCPCB package {r['status']}; problems: {r['problems']}")
    if r["status"] == "PASS":
        print(f"  {r['bom_lines']} BOM lines, {r['cpl_parts']} placed parts; "
              f"{len(r['lines_without_part_number'])} lines need a JLCPCB part number")
    return 0 if r["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
