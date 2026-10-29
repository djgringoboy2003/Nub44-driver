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


def fet_symbols() -> list:
    return [symgen.derive_renumbered(kicad_lib.get_symbol(base), name, mapping=mapping, stacked=stacked,
                                     props={"Footprint": fp, "Description": desc, "Value": name})
            for name, base, fp, mapping, stacked, desc in FETS]


def main() -> int:
    names = symgen.build_library(LIB_DIR / "symbols", SYMBOLS, version=20241209, generator_version="9.0",
                                 extra_symbols=fet_symbols())
    (LIB_DIR / f"{kicad_lib.BUDGET_LIB}.pretty").mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(paths.kicad_cli()), "sym", "upgrade", str(SYMBOLS)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        return r.returncode
    print(f"budget2s symbols: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
