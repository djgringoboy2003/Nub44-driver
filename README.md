# NUBM44 laser diode driver

A constant-current driver for the Nichia NUBM44 high-power blue laser diode, from a single Li-ion cell, on a
22 mm round PCB for PCBWay fabrication and assembly. Designed in KiCad 10 from version-controlled sources
(parameters, connectivity, placement), with automated checks and manufacturing export.

> **Safety:** the NUBM44 is a Class 4 laser source. Bench work needs a dummy load first, then appropriate
> eyewear, interlocks and a controlled area. This design is **not** validated on hardware (Gate G open).

## Status

See [PROGRESS.md](PROGRESS.md) for the live state, gate status and next actions. Agents should start with
[AGENTS.md](AGENTS.md).

## Key specifications (design targets; see `engineering/requirements.md` for status)

| Item | Value |
|---|---|
| Input | 1 × Li-ion, 2.83–4.2 V at the board (18650/21700, ≥ 15 A CDR recommended) |
| Output | Constant current, 4.0 A default (3.0 / 3.5 A by one resistor), compliance about 0.8–22 V |
| Converter | TI TPS552882 4-switch buck-boost, 595 kHz, 1.0 µH |
| Current regulation | 10 mΩ high-side shunt, INA186A2, ±3.6 % worst case (calculated) |
| Protection | Reverse polarity (P-FET), hardware UVLO, 4.8–5.2 A hardware current ceiling, hiccup short protection, open-load trip, interlock, default-off enable, thermal monitoring |
| Modes | Continuous, flash (2 Hz default); mode change by short power interruption or optional switch pad |
| Efficiency (estimated) | 94.6 % at 4.0 V, 91.3 % at 3.0 V |
| PCB | Ø 22 mm, 4 layers, 1.6 mm, ENIG (Variant A); larger evaluation board (Variant B) |

## Getting started

```powershell
.\scripts\setup.ps1          # installs/repairs the toolchain (no admin rights needed)
.venv\Scripts\python.exe engineering\calculations\power_stage.py   # re-run engineering calculations
.venv\Scripts\python.exe -m pytest tests                           # unit tests
```

The remaining entry points (`doctor`, `build`, `validate`, `export-pcbway`, `package`) are being built; PROGRESS.md
lists what exists.

## Repository layout

See the map in [AGENTS.md](AGENTS.md#repository-map).
