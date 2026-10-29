"""Build the separate budget-2s KiCad library (hardware/budget-2s/lib/budget2s.kicad_sym).

Symbols come from hardware/budget-2s/lib/symbols/*.yaml plus MOSFET symbols renumbered from
KiCad's generic Device:Q_NMOS/Q_PMOS for their package pinouts. The A/B library under
hardware/libraries is never touched. Project footprints, when needed, go to budget2s.pretty.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import kicad_lib, paths, symgen  # noqa: E402

LIB_DIR = kicad_lib.BUDGET_LIB_DIR
SYMBOLS = LIB_DIR / f"{kicad_lib.BUDGET_LIB}.kicad_sym"

# name, base, footprint, pin mapping, stacked pins, description (pinout source)
FETS = [
    ("Q_NMOS_SOT523", "Device:Q_NMOS", "Package_TO_SOT_SMD:SOT-523", {"G": "1", "S": "2", "D": "3"}, {},
     "N-MOSFET SOT-523: 1 G, 2 S, 3 D (DMG1012T, LEAD-04 p.1)"),
    ("Q_PMOS_SOT523", "Device:Q_PMOS", "Package_TO_SOT_SMD:SOT-523", {"G": "1", "S": "2", "D": "3"}, {},
     "P-MOSFET SOT-523: 1 G, 2 S, 3 D (DMG1013T, BUD-23 p.1)"),
    ("Q_PMOS_SO8", "Device:Q_PMOS", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", {"S": "1", "G": "4", "D": "5"},
     {"1": ["2", "3"], "5": ["6", "7", "8"]}, "P-MOSFET SO-8: 1-3 S, 4 G, 5-8 D (DMP2022LSS, BUD-15 p.1)"),
    ("Q_PMOS_PowerPAK1212", "Device:Q_PMOS", "Package_SO:Vishay_PowerPAK_1212-8_Single",
     {"G": "4", "D": "5", "S": "1"}, {"1": ["2", "3"]},
     "P-MOSFET PowerPAK 1212-8: 1-3 S, 4 G, 5 D drain pad (SiSS23DN, PREORDER-02; same as A/B Q1)"),
]


def tps54821_rhl0014a():
    """TI RHL0014A VQFN-14 3.5 x 3.5 mm (TPS54821), top view, mm.

    Land pattern from SLVSB14B p.40 (drawing 4228405/A 01/2022): signal pads 0.6 x 0.24 (R0.05) on 3.3 mm
    row/column spacing, 0.5 mm pitch; pins 1/14 and 7/8 at x = -/+0.75. Pad 15 copper: 2.05 mm square
    plus two 0.2 mm fingers per end at x = +/-0.275 reaching y = +/-1.93, filled between them to
    y = +/-1.43; solder mask 0.07 mm beyond the copper (non-solder-mask-defined). Five thermal vias at the
    p.40 positions, 0.3 mm drill / 0.6 mm pad (TI shows 0.2 mm), open inside the pad's mask opening, tented
    on B.Cu, solidly connected to the pours. Paste follows p.41 (0.2 x 0.73 mm finger strips) except the four
    corner apertures: TI's 0.92 mm squares at (+/-0.56, +/-0.56) would overlap our larger drill holes, so they
    are 0.82 mm squares at (+/-0.61, +/-0.61), keeping 0.2 mm from every via centre (about 64% of TI's area).
    """
    from nubm44 import fpgen
    from nubm44.sexpr import S, Sym
    items = []
    for pin, y in zip(range(2, 7), (-1.0, -0.5, 0.0, 0.5, 1.0)):
        items.append(fpgen.smd_rr(pin, -1.65, y, 0.6, 0.24))
    for pin, y in zip(range(9, 14), (1.0, 0.5, 0.0, -0.5, -1.0)):
        items.append(fpgen.smd_rr(pin, 1.65, y, 0.6, 0.24))
    for pin, x, y in ((1, -0.75, -1.65), (14, 0.75, -1.65), (7, -0.75, 1.65), (8, 0.75, 1.65)):
        items.append(fpgen.smd_rr(pin, x, y, 0.24, 0.6))
    top = [(-1.025, -1.025), (-0.375, -1.025), (-0.375, -1.93), (-0.175, -1.93), (-0.175, -1.43),
           (0.175, -1.43), (0.175, -1.93), (0.375, -1.93), (0.375, -1.025), (1.025, -1.025)]
    poly = top + [(x, -y) for x, y in reversed(top)]
    pad15 = fpgen.smd_custom(15, poly, anchor=(0.0, 0.0))
    for i, node in enumerate(pad15):  # copper and mask only; paste comes from the apertures below
        if isinstance(node, list) and node and node[0] == "layers":
            pad15[i] = S("layers", "F.Cu", "F.Mask")
    pad15.insert(-1, S("solder_mask_margin", 0.07))
    items.append(pad15)
    apertures = [(sx * 0.61, sy * 0.61, 0.82, 0.82) for sx in (-1, 1) for sy in (-1, 1)]
    apertures += [(sx * 0.275, sy * 1.565, 0.2, 0.73) for sx in (-1, 1) for sy in (-1, 1)]
    for x, y, w, h in apertures:
        items.append(S("pad", "", Sym("smd"), Sym("rect"), S("at", x, y), S("size", w, h),
                       S("layers", "F.Paste"), S("uuid", fpgen._uid("paste", x, y))))
    for x, y in ((0.0, 0.0), (-0.845, 0.0), (0.845, 0.0), (0.0, -0.845), (0.0, 0.845)):
        via = fpgen.tht_circle(15, x, y, 0.6, 0.3, layers=("*.Cu",))
        via.insert(-1, S("zone_connect", 2))  # solid to every GND pour: heat path, and no relief slivers in the EP
        items.append(via)
    items += [fpgen._rect(-1.75, -1.75, 1.75, 1.75, "F.Fab", 0.1), fpgen._rect(-2.2, -2.2, 2.2, 2.2, "F.CrtYd", 0.05),
              fpgen._line(-1.75, -1.25, -1.25, -1.75, "F.Fab", 0.1), fpgen._circle(-1.2, -2.15, 0.1, "F.SilkS", 0.12, True),
              fpgen._line(-1.86, -1.86, -1.25, -1.86, "F.SilkS", 0.12), fpgen._line(1.25, -1.86, 1.86, -1.86, "F.SilkS", 0.12),
              fpgen._line(-1.86, 1.86, -1.25, 1.86, "F.SilkS", 0.12), fpgen._line(1.25, 1.86, 1.86, 1.86, "F.SilkS", 0.12),
              fpgen._fp_text("${REFERENCE}", 0, 0, "F.Fab", 0.5)]
    return fpgen.footprint("TI_RHL0014A_VQFN-14-1EP_3.5x3.5mm_P0.5mm",
                           "TI RHL0014A VQFN-14 3.5x3.5 mm (TPS54821). Land/stencil per SLVSB14B pp.40-41, "
                           "drawing 4228405/A; 0.3/0.6 mm thermal vias, corner paste reduced clear of them.",
                           "VQFN RHL0014A TPS54821", items, ref_y=-3.0, val_y=3.0)


def fet_symbols() -> list:
    return [symgen.derive_renumbered(kicad_lib.get_symbol(base), name, mapping=mapping, stacked=stacked,
                                     props={"Footprint": fp, "Description": desc, "Value": name})
            for name, base, fp, mapping, stacked, desc in FETS]


def main() -> int:
    names = symgen.build_library(LIB_DIR / "symbols", SYMBOLS, version=20241209, generator_version="9.0",
                                 extra_symbols=fet_symbols())
    pretty = LIB_DIR / f"{kicad_lib.BUDGET_LIB}.pretty"
    pretty.mkdir(parents=True, exist_ok=True)
    from nubm44.sexpr import dump
    fps = [tps54821_rhl0014a()]
    for fp in fps:
        dump(fp, pretty / f"{fp[1]}.kicad_mod")
    for cmd in (["sym", "upgrade", str(SYMBOLS)], ["fp", "upgrade", str(pretty)]):
        r = subprocess.run([str(paths.kicad_cli()), *cmd], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            return r.returncode
    print(f"budget2s symbols: {names}")
    print(f"budget2s footprints: {[str(fp[1]) for fp in fps]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
