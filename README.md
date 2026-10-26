# NUBM44 laser diode driver

A constant-current driver for the Nichia NUBM44 high-power blue laser diode, from a single Li-ion cell,
targeting a 22 mm round PCB (plus a larger evaluation board) for PCBWay fabrication and assembly. Designed in KiCad 10 from version-controlled sources
(parameters, connectivity, placement), with automated checks and manufacturing export.

> **Safety:** the NUBM44 is a Class 4 laser source. Bench work needs a dummy load first, then appropriate
> eyewear, interlocks and a controlled area. This design is **not** validated on hardware (Gate G open).

## Status

- **Evaluation board (Variant B, 45 × 40 mm):** CAD complete. Routed with 0 DRC findings, power-layout
  reviewed, PCBWay review package generated. Next step is a prototype order, placed manually by the owner.
- **Compact board (Variant A, Ø 22 mm):** routing draft with 20 open signal connections, parked until the
  evaluation prototype has produced bench data (owner decision; `engineering/compact-feasibility.md`).
- **Physical validation (Gate G):** not started; it needs an assembled prototype.

[PROGRESS.md](PROGRESS.md) has the live state, gate status and next actions. Agents should start with
[AGENTS.md](AGENTS.md).

## Key specifications (design targets; see `engineering/requirements.md` for status)

| Item | Value |
|---|---|
| Input | 1 × Li-ion, 2.83–4.2 V at the board (18650/21700, ≥ 15 A CDR recommended) |
| Output | Constant current, 4.0 A (owner decision DD-13; 3.0 / 3.5 A by one resistor), compliance about 0.8–22 V |
| Converter | TI TPS552882 4-switch buck-boost, 595 kHz, 1.0 µH |
| Current regulation | 10 mΩ high-side shunt, INA186A2, ±3.6 % worst case (calculated) |
| Protection | Reverse polarity (P-FET), hardware UVLO, 4.8–5.2 A hardware current ceiling, hiccup short protection, open-load trip, interlock, default-off enable, thermal monitoring |
| Modes | Continuous, flash (2 Hz default); mode change by short power interruption or optional switch pad |
| Efficiency (estimated) | 94.6 % at 4.0 V (target ≥ 94 %, owner deviation DD-26), 91.3 % at 3.0 V |
| PCB | 4 layers, 1.6 mm, ENIG: Ø 22 mm compact board (Variant A) and 45 × 40 mm evaluation board (Variant B) |

## Getting started

```powershell
.\scripts\setup.ps1          # installs/repairs the toolchain (no admin rights needed)
.venv\Scripts\python.exe engineering\calculations\power_stage.py   # re-run engineering calculations
.venv\Scripts\python.exe -m pytest tests                           # unit tests
```

Entry points:

```powershell
.\scripts\doctor.ps1
.\scripts\build.ps1 -Variant compact-22mm   # regenerates/reroutes; evaluation-board or all also supported
.\scripts\validate.ps1                     # tests + evidence register; fails while checks are unresolved
.\scripts\export-pcbway.ps1 -Variant evaluation-board
.\scripts\package.ps1                      # DRAFT review ZIP with source/evidence hashes
```

`build.ps1 -SkipRouting` reuses a session only when its DSN/SES hashes match. Read the actual gate state in
[the validation register](reports/validation-register.md). Export consistency and review packaging do not
release a board for manufacturing. Physical tests remain open. Battery polarity (centre spring B+, ring B−)
is marked on both boards' silkscreen.
See [assembly instructions](documentation/assembly.md) and [the bench plan](documentation/testing/test-plan.md).

If local PowerShell execution policy blocks a script, invoke it for that process with
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1` (substitute the desired script).
The checked toolchain runs without changing machine policy or requiring administrator rights.

## Repository layout

See the map in [AGENTS.md](AGENTS.md#repository-map).
