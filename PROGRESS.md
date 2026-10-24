# Progress

## Current state (handover)

_Last updated: 2026-10-24 (evening)._

| Gate | Status | Evidence |
|---|---|---|
| A Research complete | **Done** | `research/*.md`, `research/architecture-comparison.md`, `engineering/requirements.md` |
| B Electrical design | **Done** (owner polarity confirmation pending) | `engineering/design/connectivity.yaml` → `hardware/*/nubm44_driver.kicad_sch`; ERC 0/0; netlist = spec pin-for-pin (`reports/schematic-*.json`) |
| C Simulation | **Done (model-level)** | `simulation/run_sims.py` → `simulation/results/results.md`: SIM-01…SIM-11 PASS in a behavioural averaged model (no vendor model exists) |
| D PCB placed and routed | **In progress (Variant A)** | All 65 parts placed (`hardware/compact-22mm/placement.yaml`); pours and via fields defined; FreeRouting leaves about 35–48 connections unrouted |
| E ERC/DRC clean | Not yet | DRC report `reports/drc-compact-22mm.json` (latest run) |
| F Manufacturing files | Not started | Formats researched (`research/pcbway-requirements.md`) |
| G Physical validation | Not started (needs hardware) | — |

**Design status:**
- **Power stage:** TPS552882 buck-boost, 595 kHz, 1 µH.
- **Current regulation:** a 10 mΩ Kelvin shunt (net-tie footprint) feeds the INA186A2, whose output drives FB
  through a 6.65k/10.0k divider (3.996 A). The ISP/ISN backup ceiling is 4.8–5.2 A.
- **Enable chain:** an EN/UVLO divider (3.08/2.83 V) with MCU, interlock and Zener over-voltage pull-downs.
- **Firmware:** ATtiny1616; builds at 2.4 kB, 26/26 unit checks pass (`firmware/build.ps1`).
- **Calculations:** 20 of 21 PASS. The one FAIL is the efficiency target: 94.6 % estimated at 4 V against > 95 %.

**Open owner decisions / blockers:**
1. Battery polarity: REQ-BAT-04 is BLOCKED. Working assumption is spring = B+, ring = B−.
2. Default current: 4.0 A as specified, which is above the NUBM44's 3.0 A typical. Recommend 3.5 A (change R8 only).
3. Efficiency: the > 95 % at 4 V target is not achievable with the required protection (≈ 94.6 %).
4. Sourcing: stock is UNKNOWN for several parts.
5. Variant A routing density: FreeRouting has not completed the 22 mm board. See Next actions 1.

## Next actions (in order)

1. **Finish routing Variant A.** Options, in order of preference:
   - (a) Re-run FreeRouting now that the real 0.15 mm net classes are in the DSN; until the last run the DSN
     carried a single 0.2 mm default class.
   - (b) Improve placement for routability: group MCU nets, move more parts to the bottom side.
   - (c) Complete the remaining connections with a scripted router.
   - (d) If the board still cannot route cleanly, document the limit (Phase 8) and keep Variant B as the
     route-complete board.
2. Variant B (evaluation board) placement and routing; with relaxed density this should route completely.
3. Exports: Gerbers/drill (X2 off), PCBWay BOM and centroid in plugin format, iBOM, renders, schematic PDF,
   assembly and fab drawings, stack-up note; `manufacturing/pcbway/` and the zip.
4. Entry scripts: `doctor.ps1`, `build.ps1`, `validate.ps1` (validation register + gate computation),
   `export-pcbway.ps1`, `package.ps1`.
5. Sourcing database `sourcing/components.csv` (from connectivity.yaml plus researched supplier data; UNKNOWN where
   not verified) and cost estimate.
6. Documentation: assembly instructions, bench test plan (Gate G, dummy load first), final report.

**How to rebuild what exists:**
```powershell
.venv\Scripts\python.exe automation\setupuild_library.py          # symbols + footprints
.venv\Scripts\python.exe automation\schematicuild_schematic.py     # schematics + ERC + netlist check
.venv\Scripts\python.exe automation\placementuild_pcb.py --variant compact-22mm --stage all
.venv\Scripts\python.exe engineering\calculations\power_stage.py
.venv\Scripts\python.exe simulationun_sims.py
.irmwareuild.ps1
.venv\Scripts\python.exe -m pytest tests
```

## Log

### 2026-10-24 (evening): library, schematic, simulation, firmware, PCB pipeline
- **Library:**
  - TPS552882 footprint from calibrated PDF vector extraction.
  - 1206 Kelvin shunt footprint with net tie.
  - Segmented ring contact.
  - Spring and test pads.
  - Symbols from verified pin tables; PowerPAK MOSFET symbols renumbered to the footprint pads.
- **Schematics:** generated for both variants. ERC 0/0 and netlists equal the spec. Per-variant footprints and
  MPNs: Variant A uses 0201 parts and fewer test pads (DD-17).
- **Simulation:** cycle-averaged behavioural model in ngspice 47. 11 tests PASS after fixing a model bug (the INA186
  output impedance) and unrealistic test stimuli.
- **Firmware:** ATtiny1616, avr-gcc 15.2.0 build, TinyCC host unit tests.
- **PCB pipeline:** pcbnew API placement with an automatic small-part placer, automatic via fields (no via-in-pad)
  and GND fanout, DSN → FreeRouting (jar) → SES, pours, DRC with schematic parity, dangling-via cleanup.
- **Lessons recorded in the code:**
  - `SaveBoard()` overwrites `.kicad_pro` rules, and `LoadBoard()` does not resolve net classes; both are
    re-applied through the API.
  - Annular custom pads break Specctra export, so the ring is segmented.
  - Pad bounding boxes mislead hit tests for the ring; use real shapes (`pad.HitTest`).

### 2026-10-24: research, architecture, calculations (commit 862e82d)
- Workspace was empty and not a git repo; initialised `main`. The previous design files named in the brief are not
  on this machine. The concept was audited from the brief (`engineering/previous-design-audit.md`); every proposed
  part fails a datasheet limit.
- Machine: Windows 10 Pro 22H2 x64, i5-7300U, 16 GB RAM. Non-admin account, so all tools are per-user or project-local.
- Installed:
  - KiCad 10.0.6 (winget, user scope)
  - ngspice 47
  - Temurin JRE 25.0.4.1 + FreeRouting 2.5.0 jar (the native CLI crashes)
  - InteractiveHtmlBom 2.12.0
  - Python venv
- Verified:
  - Schematic writer: KiCad ERC and netlist export agree with intended connectivity at all four rotations.
  - pcbnew → DSN → FreeRouting → SES → KiCad DRC round trip: 0 violations, 0 unconnected.
- Five parallel research tasks (laser, converters, components, batteries/mechanics, PCBWay/CAD) hit the account
  usage limit once. They were resumed with bounded budgets and completed.
- Architecture A (TPS552882) selected over a TPS61288 boost with clamp, the TPS552892, and the XL6009.
