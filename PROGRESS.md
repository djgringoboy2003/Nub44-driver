# Progress

## Current state (handover)

_Last updated: 2026-10-24._

| Gate | Status | Evidence |
|---|---|---|
| A Research complete | **Done** | `research/*.md`, `research/architecture-comparison.md`, `engineering/requirements.md` |
| B Electrical design (schematic, netlist) | **In progress** | Connectivity defined in `engineering/design-decisions.md` DD-02…DD-11; library generation started |
| C Simulation | Not started | — |
| D PCB placed and routed | Not started | Toolchain round-trip proven (pcbnew API → DSN → FreeRouting → SES → DRC clean) on a test board |
| E ERC/DRC clean | Not started | — |
| F Manufacturing files | Not started | PCBWay formats researched (`research/pcbway-requirements.md`) |
| G Physical validation | Not started (needs hardware) | — |

**Design status in one paragraph:**
- **Power stage and current regulation:** TPS552882 buck-boost (VIN from a high-side SiSS23DN
  reverse-polarity P-FET; external SiSS80DN buck-leg FETs; XGL5030-102 1 µH). Laser current regulation:
  10 mΩ high-side shunt → INA186A2 (G = 50) → 6.65k/10.0k divider → FB = 1.2 V at 3.996 A. Backup ceiling:
  TPS552882 ISP/ISN 4.8–5.2 A.
- **Enable chain:** EN/UVLO is a VBAT divider (3.08 V on / 2.83 V off) with three open-drain pull-downs:
  MCU (default off), interlock, and an over-voltage Zener backstop. The MCU is an ATtiny1616.
- **Calculations:** `engineering/calculations/power_stage.py` gives 20 of 21 checks PASS. The one FAIL is a
  genuine finding: efficiency at 4.0 V is 94.6 % against the > 95 % target.

**Open owner decisions / blockers:**
1. **Battery polarity:** REQ-BAT-04 is BLOCKED. The working interpretation is spring = B+, ring = B−; the owner must confirm.
2. **Default current:** 4.0 A (as specified) is above the NUBM44's typical 3.0 A. Recommend 3.5 A; it is a single resistor change.
3. **Efficiency:** the > 95 % at 4 V target is not achievable with the required protection (≈ 94.6 % estimated).
4. **Sourcing:** stock is UNKNOWN for several parts (TPS552882 at LCSC, XGL5030-102, SiSS80DN).

## Next actions (in order)

1. Generate the project library: footprints (`automation/nubm44/fpgen.py`, in progress), symbols (TPS552882,
   INA186, PowerPAK MOSFETs, contacts), 3D placeholder models.
2. Write `engineering/design/connectivity.yaml` (all parts, MPNs, footprints, pin→net).
3. Schematic build script, then `kicad-cli sch upgrade`, ERC, netlist export, and a pin-by-pin comparison with
   connectivity.yaml.
4. ngspice behavioural simulations: start-up, flash transitions, open load, short circuit, battery step,
   loop response.
5. PCB generation (pcbnew API): 22 mm outline, 4-layer stack-up, placement YAML, critical power routing,
   FreeRouting for the rest, zones, DRC with schematic parity. Then Variant B (evaluation board).
6. Exports: Gerbers, drill, BOM/centroid in PCBWay format, renders, iBOM, PDFs; `manufacturing/pcbway/` package.
7. Firmware (ATtiny1616): state machine, emission delay, interlock, LVC, thermal, flash, off-time mode memory.
8. Entry-point scripts: `doctor.ps1`, `build.ps1`, `validate.ps1`, `export-pcbway.ps1`, `package.ps1`.
9. Final report.

## Log

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
