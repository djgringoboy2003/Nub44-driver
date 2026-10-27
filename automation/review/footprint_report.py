"""Footprint review pack: pad tables of the footprints that need a human review before ordering.

For each footprint listed in engineering/release/design-reviews.yaml (FP-U1, FP-L1, FP-POWERPAK, FP-RS1, ORIENT) this
writes the exact pad geometry used on the boards (from the footprint files the build uses), the pad-to-net mapping
from connectivity.yaml, symbol pin names where the project defines them, the placed rotation on the evaluation board
and the manufacturer document to compare against. It does not judge anything: the comparison is the reviewer's.

    .venv\\Scripts\\python.exe automation\\review\\footprint_report.py      # writes reports/footprint-review.md
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths, spec  # noqa: E402
from nubm44.sexpr import child, children, load  # noqa: E402

OUT = ROOT / "reports" / "footprint-review.md"
VARIANT = "evaluation-board"

ITEMS = [
    ("FP-U1", ["U1"], "nubm44:TI_RPM0026A_VQFN-HR-26_4x3.5mm_P0.5mm",
     "TI SLVSFC5 (LEAD-01, local copy research/datasheets/pwr_tps552882_slvsfc5.pdf): RPM0026A package outline and "
     "example board layout / stencil (drawing 4224618/A, about p.36-40). Compare pad sizes, 0.5 mm pitch, the three "
     "centre pads (24 PGND, 25 SW2, 26 VOUT) and pin 1; the centre pads are bridged to pins 9, 21 and 11 on the board (DD-16).",
     "hardware/libraries/symbols/TPS552882.yaml"),
    ("FP-L1", ["L1"], "Inductor_SMD:L_Coilcraft_XAL5030-XXX",
     "Coilcraft XGL5030 datasheet and recommended land pattern (LEAD-05; PDF not stored locally). The board uses KiCad's "
     "XAL5030 pattern; confirm the XGL5030 body (about 5.28 x 5.48 mm) and terminals fit it.", None),
    ("FP-POWERPAK", ["Q1", "Q2", "Q3"], "Package_SO:Vishay_PowerPAK_1212-8_Single",
     "Vishay SiSS23DN and SiSS80DN datasheets (research/datasheets/cmp_Vishay_SiSS23DN.pdf, cmp_Vishay_SiSS80DN.pdf): "
     "pinout (S 1-3, G 4, D = drain pad and pins 5-8) and Vishay's PowerPAK 1212-8 single land pattern. Q1 is the "
     "P-channel reverse-polarity FET; its drain must be BAT_SPRING and its source VBAT.", None),
    ("FP-RS1", ["RS1"], "nubm44:R_1206_3216Metric_Kelvin",
     "Ohmite MCS1632R010FER datasheet land pattern (LEAD-07; PDF not stored locally). Pads 1/4 carry the current; 2/3 "
     "are the Kelvin sense pads, joined to 1/4 only at the resistor (net tie).", None),
    ("ORIENT", ["U3"], "Package_DFN_QFN:VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm",
     "Microchip ATtiny1614/16/17 datasheet (LEAD-03) package drawing; plus pin-1 and polarity of every IC, diode and "
     "MOSFET in manufacturing/pcbway/evaluation-board/drawings/assembly_top.pdf and assembly/ibom.html.", None),
]


def footprint_file(fpid: str) -> Path:
    lib, name = fpid.split(":", 1)
    if lib == "nubm44":
        return paths.LIBRARIES / "nubm44.pretty" / f"{name}.kicad_mod"
    try:
        return paths.kicad_footprints_dir() / f"{lib}.pretty" / f"{name}.kicad_mod"
    except FileNotFoundError:                     # KiCad not installed (e.g. CI): reported as not found
        return Path(f"{lib}.pretty") / f"{name}.kicad_mod"


def pads(fp_path: Path) -> list[dict]:
    root = load(fp_path)
    out = []
    for p in children(root, "pad"):
        at, size, layers = child(p, "at"), child(p, "size"), child(p, "layers")
        entry = {"number": str(p[1]), "type": str(p[2]), "shape": str(p[3]),
                 "x": float(at[1]), "y": float(at[2]), "rot": float(at[3]) if len(at) > 3 else 0.0,
                 "w": float(size[1]) if size else None, "h": float(size[2]) if size else None,
                 "layers": " ".join(str(x) for x in layers[1:]) if layers else ""}
        prim = child(p, "primitives")
        if entry["shape"] == "custom" and prim:          # report the real outline, not the 0.2 mm anchor
            xs, ys = [], []
            if entry["w"] is not None:                    # the anchor rectangle is copper too
                xs += [-entry["w"] / 2, entry["w"] / 2]
                ys += [-entry["h"] / 2, entry["h"] / 2]
            for poly in children(prim, "gr_poly"):
                stroke = child(poly, "width") or child(child(poly, "stroke") or [], "width")
                half = float(stroke[1]) / 2 if stroke else 0.0  # a stroked outline adds copper on each side
                for xy in children(child(poly, "pts"), "xy"):
                    xs += [float(xy[1]) - half, float(xy[1]) + half]
                    ys += [float(xy[2]) - half, float(xy[2]) + half]
            if xs:
                entry["shape"] = (f"custom polygon, extent x {entry['x'] + min(xs):.4f}..{entry['x'] + max(xs):.4f}, "
                                  f"y {entry['y'] + min(ys):.4f}..{entry['y'] + max(ys):.4f}")
                entry["w"], entry["h"] = max(xs) - min(xs), max(ys) - min(ys)
        out.append(entry)
    return out


def pin_names(sym_yaml: str | None) -> dict[str, str]:
    if not sym_yaml:
        return {}
    data = yaml.safe_load((ROOT / sym_yaml).read_text(encoding="utf-8"))
    return {str(p["number"]): p["name"] for side in data["pins"].values() for p in side}


def placed() -> dict[str, dict]:
    cpl = ROOT / "manufacturing" / "pcbway" / VARIANT / "assembly" / "CPL_PCBWay.csv"
    with open(cpl, encoding="utf-8-sig", newline="") as fh:
        return {r["designator"]: r for r in csv.DictReader(fh)}


def build() -> str:
    parts = {p["ref"]: p for p in spec.parts_for(VARIANT)}
    cpl = placed()
    lines = ["# Footprint review pack (evaluation board)", "",
             "Generated by `automation/review/footprint_report.py` from the footprint files the build uses. It lists the "
             "geometry; it does not judge it. Record each completed comparison in "
             "`engineering/release/design-reviews.yaml` (status DONE, reviewer, date, evidence with document revision and "
             "page). Coordinates are footprint-local millimetres, KiCad convention (y down), pad centre and size; for "
             "custom pads w/h is the polygon extent.", ""]
    for rid, refs, fpid, reference, sym in ITEMS:
        path = footprint_file(fpid)
        lines += [f"## {rid}: {', '.join(refs)} ({fpid})", "", f"**Compare against:** {reference}", ""]
        if not path.is_file():
            lines += [f"Footprint file not found: `{path}` (KiCad library not installed here).", ""]
            continue
        rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else f"KiCad library: {path.parent.name}/{path.name}"
        lines += [f"Footprint file: `{rel}` (SHA-256 `{hashlib.sha256(path.read_bytes()).hexdigest()[:16]}`)", ""]
        names = pin_names(sym)
        nets = {ref: {str(k): v for k, v in parts[ref]["pins"].items()} for ref in refs if ref in parts}
        head = "| Pad | Type | Shape | x | y | w | h | rot |" + (" Pin name |" if names else "") + \
               "".join(f" {ref} net |" for ref in nets)
        lines += [head, "|" + "---|" * (head.count("|") - 1)]
        for p in sorted(pads(path), key=lambda p: (int(p["number"]) if p["number"].isdigit() else 999, p["number"])):
            w = "-" if p["w"] is None else f"{p['w']:.4f}"
            h = "-" if p["h"] is None else f"{p['h']:.4f}"
            row = (f"| {p['number'] or '(none)'} | {p['type']} | {p['shape']} | {p['x']:.4f} | {p['y']:.4f} | "
                   f"{w} | {h} | {p['rot']:g} |")
            if names:
                row += f" {names.get(p['number'], '')} |"
            row += "".join(f" {nets[ref].get(p['number'], '')} |" for ref in nets)
            lines.append(row)
        placed_rows = [f"{ref} at ({cpl[ref]['pos_x']}, {cpl[ref]['pos_y']}) mm, rotation {cpl[ref]['rotation']} deg, "
                       f"{cpl[ref]['side']}" for ref in refs if ref in cpl]
        lines += ["", "Placed on the evaluation board (PCBWay centroid, y up): " + "; ".join(placed_rows) + ".", ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT.write_text(build(), encoding="utf-8")
    print(f"footprint review pack: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
