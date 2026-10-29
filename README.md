# NUBM44 laser diode driver

A constant-current driver for the Nichia NUBM44 high-power blue laser diode, from a single Li-ion cell,
targeting a 22 mm round PCB (plus a larger evaluation board) for PCBWay fabrication and assembly. Designed in KiCad 10 from version-controlled sources
(parameters, connectivity, placement), with automated checks and manufacturing export.

> **Safety:** the NUBM44 is a Class 4 laser source. Bench work needs a dummy load first, then appropriate
> eyewear, interlocks and a controlled area. This design is **not** validated on hardware (Gate G open).

## Status

- **Evaluation board (Variant B, 45 × 40 mm):** CAD complete (DRC 0/0/0/0), power-layout reviewed, DRAFT PCBWay
  review package generated. Release readiness: **DRAFT_REVIEW**; it becomes a PROTOTYPE_CANDIDATE once five human
  footprint/orientation reviews are recorded (`engineering/release/design-reviews.yaml`). Orders are placed by the
  owner by hand.
- **Compact board (Variant A, Ø 22 mm):** routing draft with 20 open signal connections, parked until the
  evaluation prototype has produced bench data (owner decision DD-27; strategy in
  `engineering/pcb-review-2026-10-26.md`). Its fabrication ZIP carries `DO_NOT_FABRICATE.txt`.
- **Separate budget-2s driver:** owner accepts two series Li-ion cells, unrestricted size and a £60 target
  per working unit. Electrical qualification has started (DD-30): independent numeric sources, conditional
  calculations and a preliminary ngspice loop study. Efficiency, UVLO and fault-control issues remain OPEN;
  no budget PCB/manufacturing package exists. Continue from the
  [implementation handover](engineering/budget-2s-design.md) and [plan](engineering/budget-driver-plan.md).
- **Physical validation (Gate G):** not started; it needs an assembled prototype and recorded bench data.
- **Firmware:** reworked after an independent audit (DD-28); 531 host checks, register-model tests of the hardware
  layer and a mutation check; not yet run on hardware.

**Ordering:** files and options for PCBWay and JLCPCB are in [documentation/ordering-guide.md](documentation/ordering-guide.md);
the pre-order review brief is [documentation/pre-order-review.md](documentation/pre-order-review.md).

Live state: [PROGRESS.md](PROGRESS.md) and the generated dashboard `reports/dashboard/index.html` (open it in a
browser). Agents start with [AGENTS.md](AGENTS.md); people with the
[developer guide](documentation/developer-guide.md). Audit: [reports/comprehensive-project-audit.md](reports/comprehensive-project-audit.md).

## Key specifications (original A/B design targets; see `engineering/requirements.md` for status)

| Item | Value |
|---|---|
| Input | 1 × Li-ion, 2.83–4.2 V at the board (18650/21700, ≥ 15 A CDR recommended) |
| Output | Constant current, 4.5 A (owner decision DD-36; 3.0 / 3.5 / 4.0 A by one resistor), compliance about 0.8–22 V |
| Converter | TI TPS552882 4-switch buck-boost, 595 kHz, 1.0 µH |
| Current regulation | 10 mΩ high-side shunt, INA186A2, ±3.6 % worst case (calculated) |
| Protection | Reverse polarity (P-FET), hardware UVLO, 4.8–5.2 A hardware current ceiling, hiccup short protection, open-load trip, interlock, default-off enable, thermal monitoring |
| Modes | Continuous, flash (2 Hz default); mode change by short power interruption or optional switch pad |
| Efficiency (estimated) | 94.6 % at 4.0 V (target ≥ 94 %, owner deviation DD-26), 91.3 % at 3.0 V |
| PCB | 4 layers, 1.6 mm, ENIG: Ø 22 mm compact board (Variant A) and 45 × 40 mm evaluation board (Variant B) |

## Getting started

```powershell
.\scripts\setup.ps1          # installs/repairs the toolchain (no admin rights needed)
.venv\Scripts\python.exe -m pytest tests                               # unit tests
.venv\Scripts\python.exe firmware\build.py --mutation                  # firmware host tests, ATtiny1616 build, mutation check
.venv\Scripts\python.exe automation\validation\validate.py            # register, readiness, dashboard (exit 1 = new or changed failure)
.venv\Scripts\python.exe automation\validation\validate.py --mode fast  # same checks without KiCad/ngspice/avr-gcc
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
[the validation register](reports/validation-register.md) and the per-board level in
[release readiness](reports/release-readiness.md) (DRAFT_REVIEW, PROTOTYPE_CANDIDATE, MANUFACTURING_RELEASE; see the
[release checklist](documentation/release-checklist.md)). Export consistency and review packaging do not
release a board for manufacturing. CI (`.github/workflows/ci.yml`) runs the portable checks on Linux and the firmware
target build on Windows. Physical tests remain open. Battery polarity (centre spring B+, ring B−)
is marked on both boards' silkscreen.
See [assembly instructions](documentation/assembly.md) and [the bench plan](documentation/testing/test-plan.md).

If local PowerShell execution policy blocks a script, invoke it for that process with
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1` (substitute the desired script).
The checked toolchain runs without changing machine policy or requiring administrator rights.

## Repository layout

See the map in [AGENTS.md](AGENTS.md#repository-map).
