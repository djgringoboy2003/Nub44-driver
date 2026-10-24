"""Build the project KiCad library: symbols, footprints and placeholder 3D models.

Outputs (all regenerated, do not hand-edit):
  hardware/libraries/nubm44.kicad_sym     symbols (YAML specs + native project derivatives)
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

from nubm44 import fpgen, kicad_lib, paths, spec as spec_mod, symgen  # noqa: E402
from nubm44.sexpr import children  # noqa: E402

POWERPAK_DESC = "MOSFET in Vishay PowerPAK 1212-8: pins 1-3 S, 4 G, 5 D (drain pad), matching footprint Package_SO:Vishay_PowerPAK_1212-8_Single"
FOOTPRINT_SYMBOL_BASES = {
    "Battery_Contact": "Connector_Generic:Conn_01x01",
    "Laser_Connector": "Connector_Generic:Conn_01x02",
    "R_Shunt_Kelvin": "Device:R_Shunt",
    "TestPoint": "Connector:TestPoint",
}


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


def footprint_symbols() -> list:
    """Native library copies with the verified footprint choices from both variants.

    Filters belong to the project library, so schematic embedded copies remain
    identical to it. Keep generic KiCad filter options alongside exact selections.
    Pin numbers, electrical types and graphics remain those of the source symbol.
    """
    parts = [part for variant in spec_mod.VARIANTS for part in spec_mod.parts_for(variant)]
    out = []
    for name, base_id in FOOTPRINT_SYMBOL_BASES.items():
        selected = sorted({p["footprint"] for p in parts if p["lib"] == f"nubm44:{name}"})
        if not selected:
            raise ValueError(f"no connectivity entries select project symbol nubm44:{name}")
        base = kicad_lib.get_symbol(base_id)
        inherited = next((str(p[2]).split() for p in children(base, "property")
                          if p[1] == "ki_fp_filters"), [])
        filters = " ".join(dict.fromkeys(inherited + selected))
        out.append(symgen.derive_renumbered(
            base, name, mapping={}, stacked={}, props={"Value": name, "ki_fp_filters": filters}))
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
                                     version=20241209, generator_version="9.0",
                                     extra_symbols=fet_symbols() + footprint_symbols())
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
