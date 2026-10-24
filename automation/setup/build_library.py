"""Build the project KiCad library: symbols, footprints and placeholder 3D models.

Outputs (all regenerated, do not hand-edit):
  hardware/libraries/nubm44.kicad_sym     symbols (YAML specs + derived PowerPAK MOSFETs)
  hardware/libraries/nubm44.pretty/       footprints (automation/nubm44/fpgen.py)
  hardware/models/*.wrl                   simple body models where no vendor model exists

Both libraries are then upgraded to the native KiCad 10 format with kicad-cli.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import fpgen, kicad_lib, paths, symgen  # noqa: E402

POWERPAK_DESC = "MOSFET in Vishay PowerPAK 1212-8: pins 1-3 S, 4 G, 5 D (drain pad), matching footprint Package_SO:Vishay_PowerPAK_1212-8_Single"


def fet_symbols() -> list:
    out = []
    for base, name, desc in (("Device:Q_NMOS", "Q_NMOS_PowerPAK1212", "N-channel " + POWERPAK_DESC),
                             ("Device:Q_PMOS", "Q_PMOS_PowerPAK1212", "P-channel " + POWERPAK_DESC)):
        sym = kicad_lib.get_symbol(base)
        out.append(symgen.derive_renumbered(
            sym, name, mapping={"G": "4", "D": "5", "S": "1"}, stacked={"1": ["2", "3"]},
            props={"Footprint": "Package_SO:Vishay_PowerPAK_1212-8_Single", "Description": desc,
                   "Value": name}))
    return out


def wrl_box(path: Path, w: float, d: float, h: float, color=(0.12, 0.12, 0.12), pin1=True) -> None:
    """VRML 2.0 body box (KiCad WRL unit = 0.1 inch)."""
    k = 1 / 2.54
    shapes = [f"""Transform {{ translation 0 0 {h * k / 2:.4f} children [ Shape {{
  appearance Appearance {{ material Material {{ diffuseColor {color[0]} {color[1]} {color[2]} }} }}
  geometry Box {{ size {w * k:.4f} {d * k:.4f} {h * k:.4f} }} }} ] }}"""]
    if pin1:
        shapes.append(f"""Transform {{ translation {-(w / 2 - 0.45) * k:.4f} {(d / 2 - 0.45) * k:.4f} {h * k + 0.002:.4f} children [ Shape {{
  appearance Appearance {{ material Material {{ diffuseColor 0.9 0.9 0.9 }} }}
  geometry Cylinder {{ radius {0.2 * k:.4f} height 0.004 }} }} ] }}""")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#VRML V2.0 utf8\n# generated placeholder body, not a vendor model\n" + "\n".join(shapes) + "\n",
                    encoding="utf-8")


def main() -> int:
    lib_dir = paths.LIBRARIES
    sym_names = symgen.build_library(lib_dir / "symbols", lib_dir / "nubm44.kicad_sym",
                                     version=20241209, generator_version="9.0", extra_symbols=fet_symbols())
    fp_names = fpgen.build_all(lib_dir / "nubm44.pretty")
    wrl_box(paths.MODELS / "TI_RPM0026A.wrl", 4.0, 3.5, 1.0)

    cli = str(paths.kicad_cli())
    for cmd in ([cli, "sym", "upgrade", str(lib_dir / "nubm44.kicad_sym")],
                [cli, "fp", "upgrade", str(lib_dir / "nubm44.pretty")]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            return r.returncode
    print(f"symbols: {sym_names}")
    print(f"footprints: {fp_names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
