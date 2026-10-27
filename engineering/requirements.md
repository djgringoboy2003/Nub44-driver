# Engineering requirement register

Authoritative list of requirements for the NUBM44 driver. Every design artefact traces back to an ID here.

- **Source** says where a requirement came from: `BRIEF` (the project brief), `DERIVED` (engineering consequence of
  another requirement), or `ASSUMPTION` (a default chosen here that the owner should confirm).
- **Verify** is how the requirement is checked: `CALC` (engineering calculation), `SIM` (simulation),
  `CAD` (ERC/DRC or a scripted CAD check), `INSPECT` (design review), `TEST` (physical test on hardware).
- **Status** values: `OPEN` (not yet addressed), `DESIGNED` (implemented in the design, not yet verified),
  `VERIFIED-CALC`, `VERIFIED-SIM`, `VERIFIED-CAD`, `VERIFIED-TEST` (measured on an assembled prototype),
  `NEEDS-TEST` (only hardware testing can close it),
  `AT-RISK` (evidence suggests it may not be met), `INFEASIBLE` (evidence shows it cannot be met as written),
  `BLOCKED` (needs an owner decision).

Statuses are updated as work proceeds; see the change history in git.

## 1. Load and output

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-LD-01 | Drive a genuine Nichia NUBM44 laser diode. | BRIEF | INSPECT | DESIGNED | No public Nichia NUBM44 datasheet exists; ratings come from a module maker's table plus community LIV data (`research/nubm44-research.md`). |
| REQ-OUT-01 | Maximum output current 4.0 A. | BRIEF | CALC, SIM, TEST | VERIFIED-SIM | Hardware is sized and verified by calculation for 4.0 A, and SIM-03 regulates 3.996 A. 4.0 A exceeds the NUBM44 typical 3.0 A and, for most units, the 6.0 W optical maximum. Owner decision 2026-10-25: keep 4.0 A and accept the diode-life risk (DD-13). NEEDS-TEST on the bench. |
| REQ-OUT-02 | True constant-current regulation of laser current. | BRIEF | SIM, TEST | VERIFIED-SIM | SIM-03: 3.996 A at every battery (3.0–4.2 V) × diode corner, including Vf < Vbat (buck mode). Model-level; NEEDS-TEST. |
| REQ-OUT-03 | Output current accuracy within ±5 % at 4.0 A over 0–50 °C board temperature. | ASSUMPTION | CALC, TEST | VERIFIED-CALC | Worst-case tolerance stack ±3.6 % (`engineering/calculations/power-stage-results.md`). |
| REQ-OUT-04 | Output voltage adapts to the diode forward voltage (no fixed-voltage setpoint). | BRIEF | SIM | DESIGNED | Current feedback only, no voltage setpoint; 0.8–22 V converter range. |
| REQ-OUT-05 | Laser current must never exceed the set current by more than 10 % during start-up, mode changes, battery transients or reconnection of the load. | DERIVED (REQ-SAFE-05) | SIM, TEST | VERIFIED-SIM | SIM-01/02/06: no overshoot above 4.0 A at start-up or flash turn-on (behavioural model). NEEDS-TEST on hardware. |

## 2. Battery input

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-BAT-01 | Single-cell lithium-ion input, 3.7 V nominal. | BRIEF | INSPECT | DESIGNED | Source architecture and input protection support one cell; hardware tests remain open. |
| REQ-BAT-02 | Operating input range to be determined by research (expected about 2.8–4.2 V under load). | BRIEF | CALC | VERIFIED-CALC | 2.83 V (hardware UVLO off) to 4.20 V at the board; firmware cut-off 2.9 V loaded. |
| REQ-BAT-03 | Evaluate 16340, 14500, 18500, 18650 and 21700 cells; separate "fits" from "electrically suitable". | BRIEF | CALC | VERIFIED-CALC | 18650/21700 cells with ≥ 15 A CDR are suitable; 16340 and 14500 are unsuitable; 18350/18500 marginal (`research/battery-and-mechanics.md`). |
| REQ-BAT-04 | One explicit battery polarity definition (centre spring and perimeter contact) used everywhere: schematic, PCB, silkscreen, drawings, instructions. | BRIEF | INSPECT, CAD | DESIGNED | Owner decision 2026-10-25 (DD-12): either orientation is acceptable provided the board marks it clearly. Definition used: centre spring = B+, ring = B−. Silkscreen: compact "B+" beside the spring pad and "B-" beside the ring (both sides); evaluation "B+ INPUT"/"B- INPUT" at the wire pads. `tests/test_placement.py` checks that both boards carry the labels within PCBWay legend limits. Host check: T3.3. |
| REQ-BAT-05 | Battery undervoltage lockout prevents over-discharge of the cell. | BRIEF | CALC, TEST | DESIGNED | Hardware UVLO via EN/UVLO divider (3.08 V on / 2.83 V off) plus firmware cut-off. |

## 3. Power conversion

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-PWR-01 | Prefer a high-efficiency boost topology; compare at least three architectures numerically. | BRIEF | CALC | VERIFIED-CALC | Four architectures compared (`research/architecture-comparison.md`). |
| REQ-PWR-02 | Efficiency ≥ 94 % at 4.0 V input, 4 A output. Owner deviation 2026-10-25 from the brief's > 95 % target (DD-26). | BRIEF (target), owner deviation | CALC, TEST | VERIFIED-CALC | Loss model 94.6 % at 4.0 V. With routed copper, including the switch-node copper the model omits, the estimate is 94.1 % on the evaluation board and 94.4 % on the compact board (`reports/layout-review-<variant>.md`). NEEDS-TEST: bench efficiency (T1.7). |
| REQ-PWR-03 | Efficiency target ≥ 86 % at 3.0 V input, 4 A output. | BRIEF (target) | CALC, TEST | VERIFIED-CALC | Estimated 91.3 % at 3.0 V (worst diode). Bench confirmation needed. |
| REQ-PWR-04 | Converter components operate with margin: switch/inductor peak current ≥ 20 % below the minimum rated limit at worst case (minimum battery, maximum Vf, maximum current). | DERIVED | CALC | VERIFIED-CALC | Worst average inductor current 8.9 A including a 20 % margin against the 10.2 A minimum ILIM; 8.5 A peak against 14 A Isat. |
| REQ-PWR-05 | Input and output filtering. | BRIEF | CALC, SIM | DESIGNED | 3 × 22 µF input, 4 × 22 µF output; ripple 8.9 % p-p worst corner. |

## 4. Control and modes

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-MODE-01 | Continuous output mode. | BRIEF | TEST | DESIGNED | Firmware MODE_CONTINUOUS; host-tested (firmware/tests). Mode changes by power gap or debounced switch (DD-28). |
| REQ-MODE-02 | Flashing output mode. | BRIEF | SIM, TEST | VERIFIED-SIM | SIM-06 flash transitions; firmware unit test checks 2 Hz / 50 %. |
| REQ-MODE-03 | Default flash pattern 2 Hz, 50 % duty. | ASSUMPTION | INSPECT | DESIGNED | 2 Hz / 50 % in firmware (assumption; owner to confirm). |
| REQ-MODE-04 | Mode transitions cause no overshoot (REQ-OUT-05) and no output-capacitor discharge through the diode. | BRIEF | SIM, TEST | VERIFIED-SIM | SIM-06: each turn-on is a soft-started current ramp; turn-off reaches < 50 mA in 0.49 ms. |

## 5. Protection and safety

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-PROT-01 | Reverse-polarity protection using a MOSFET (not a series diode). | BRIEF | SIM, TEST | VERIFIED-SIM | High-side SiSS23DN; SIM-10: 0.25 µA with −4.2 V applied. NEEDS-TEST. |
| REQ-SAFE-01 | Hardware shutdown path that does not depend on firmware. | BRIEF | INSPECT, TEST | VERIFIED-SIM | EN/UVLO wired-AND of MCU, interlock and OV backstop; SIM-07 shows < 0.1 ms to < 50 mA. |
| REQ-SAFE-02 | External safety interlock: output is disabled in hardware when the interlock loop is open. | BRIEF | INSPECT, TEST | VERIFIED-SIM | Q5 forces EN low with the loop open; SIM-07; firmware latches FAULT_INTERLOCK (manual reset). |
| REQ-SAFE-03 | Default-disabled start-up: no emission on battery insertion until enabled by the user. | BRIEF | SIM, TEST | DESIGNED | R17 pull-up holds Q4 on, so the converter is off; firmware 2 s emission delay after every power-up and every restart; a watchdog or unexpected reset latches a fault instead of re-arming (DD-28); host-tested, including the HAL register model. |
| REQ-SAFE-04 | Soft-start of laser current. | BRIEF | SIM, TEST | VERIFIED-SIM | 4 ms reference ramp → current ramp (SIM-01/02). |
| REQ-SAFE-05 | Output overshoot limiting. | BRIEF | SIM, TEST | VERIFIED-SIM | See REQ-OUT-05. |
| REQ-SAFE-06 | Battery undervoltage lockout. | BRIEF | CALC, TEST | VERIFIED-CALC | Hardware UVLO 3.08/2.83 V (calculation checks 13/14) plus firmware 2.9 V cut-off and 3.2 V start check at power-up and at the end of every arming period (host-tested, DD-28). The firmware measures VBAT ratiometrically so the thresholds stay within the reference's specified supply range. NEEDS-TEST (T2.6, T1.11). |
| REQ-SAFE-07 | Overcurrent protection. | BRIEF | SIM, TEST | VERIFIED-SIM | ISP/ISN ceiling 4.8–5.2 A plus 12 A average inductor limit; SIM-08. |
| REQ-SAFE-08 | Thermal shutdown or thermal monitoring. | BRIEF | TEST | DESIGNED | Board NTC (mandatory: open or short latches fault 11) + optional laser NTC (a short, or a loss after being present at power-up, latches fault 12); firmware latch at 85 °C / 60 °C (host-tested, DD-28); IC TSD 175 °C. Before DD-28 a failed sensor silently disabled the limit (AUD-FW-01). NEEDS-TEST (T2.7, T2.13). |
| REQ-SAFE-09 | Open-load protection (laser disconnected). | BRIEF | SIM, TEST | VERIFIED-SIM | SIM-09: Zener backstop alone limits VOUT to 6.7 V; AC0 trip at 5.6 V in firmware. |
| REQ-SAFE-10 | Output short-circuit protection. | BRIEF | SIM, TEST | VERIFIED-SIM | SIM-08: 4.0 A held into a 10 mΩ short; firmware latches FAULT_SHORT. |
| REQ-SAFE-11 | Safe shutdown with controlled output discharge. | BRIEF | SIM, TEST | VERIFIED-SIM | Input isolated when disabled; 4.7 kΩ bleeder discharges VOUT; SIM-06/07. |
| REQ-SAFE-12 | Physical testing uses a dummy load and controlled laser-safety arrangements (Class 4). | BRIEF | INSPECT | DESIGNED | Dummy-load-first procedure and controlled-area arrangements in documentation/testing/test-plan.md; no physical tests run. |

## 6. Mechanical and PCB

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-MECH-01 | Circular PCB, 22.0 mm outside diameter (Variant A). | BRIEF | CAD | DESIGNED | Circle of radius 11 mm in placement.yaml. Variant A is a parked routing draft (20 open connections, DD-27). |
| REQ-MECH-02 | Centre spring contact and perimeter battery contact. | BRIEF | CAD | DESIGNED | Contacts placed; ring radius corrected in source for edge margin (DD-21). Polarity defined and marked on the board (REQ-BAT-04). |
| REQ-MECH-03 | External laser diode connection pads. | BRIEF | CAD | VERIFIED-CAD | J3 PTH laser pads (4.0 mm pitch on the evaluation board, 3.5 mm on the compact board) are connected on both boards; no J3 item is open in either DRC. |
| REQ-MECH-04 | Evaluate 2-layer and 4-layer stack-ups. | BRIEF | CALC | VERIFIED-CALC | 4-layer chosen; 2-layer rejected for density and current paths (DD-14). |
| REQ-MECH-05 | Larger evaluation board (Variant B) with the same electrical architecture if 22 mm cannot carry full test access. | BRIEF | INSPECT | VERIFIED-CAD | Variant B four-layer 45 x 40 mm board has 68 parts, 13 labelled test points and repeated DRC 0/0/0/0; its power-layout review is done (DD-23). It is the first prototype (DD-27); bench validation remains open. |
| REQ-PCB-01 | Layout priorities: small switching loops, input caps near switches, Kelvin sensing, quiet feedback, thermal copper, grounding strategy. | BRIEF | INSPECT, CAD | DESIGNED | Evaluation board: power-layout review with copper current-flow analysis (`engineering/layout-review.md`); SW1/VOUT/LD_P pours corrected; package-limited SW2/PGND/AGND items (DD-16) and buck-leg drive loops documented with bench checks T2.9–T2.12. Compact draft: every power path connected and reviewed; 20 signal connections open on a via-capacity limit (`engineering/compact-feasibility.md`). |
| REQ-TEST-01 | Test points where practical. | BRIEF | CAD | VERIFIED-CAD | 10 compact test/connection pads and 13 evaluation test points placed; evaluation probe labels are source-defined. |

## 7. Tooling, manufacturing, documentation

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-CAD-01 | Native, editable KiCad schematic and PCB. | BRIEF | CAD | VERIFIED-CAD | Both native KiCad 10 projects open in the toolchain. Evaluation routing/DRC clean; compact routing remains open. |
| REQ-CAD-02 | EasyEDA compatibility where practical. | BRIEF | INSPECT | OPEN | Not evaluated. The native KiCad files are the design record. |
| REQ-CAD-03 | ERC and DRC run automatically; no violations silenced without a documented cause. | BRIEF | CAD | VERIFIED-CAD | Entry scripts run ERC/DRC and reject missing, malformed or stale evidence; strict gate-dependency and tool-failure regressions added. Two documented non-electrical DRC omissions are recorded in DD-20. Evaluation DRC is clean; the compact board's 3 dangling-via warnings and 20 unconnected items remain open. |
| REQ-CAD-04 | Netlist cross-checked against a machine-readable connectivity specification. | BRIEF | CAD | VERIFIED-CAD | Netlist equals connectivity.yaml pin-for-pin (reports/schematic-*.json); checker sensitivity tested. |
| REQ-MFG-01 | PCBWay fabrication and assembly package generated from the real CAD files by one command. | BRIEF | CAD | VERIFIED-CAD | Both review packages pass internal checks with source/artifact hashes. Gate F passes its automated checks for the evaluation board and stays open for the compact board; neither is a manufacturing release. Since the 2026-10-26 audit the export reads the DRC state: the compact package is classed DRAFT_REVIEW_INCOMPLETE_BOARD and its fabrication ZIP carries DO_NOT_FABRICATE.txt; per-board release levels are in reports/release-readiness.md (both DRAFT_REVIEW). |
| REQ-MFG-02 | BOM and placement data validated against the placed footprints. | BRIEF | CAD | VERIFIED-CAD | Exporter independently re-reads BOM/CPL and checks refs, counts, signed positions, rotation and side against actual board/native KiCad data. Both actual exports pass: 30 BOM lines (one per orderable part, since 2026-10-27; was 48) / 53 parts and 52 centroid rows per variant. JLCPCB-format files for the evaluation board are derived from the checked PCBWay package (automation/export/export_jlcpcb.py). |
| REQ-MFG-03 | No manufacturing order is placed automatically. | BRIEF | INSPECT | DESIGNED | Scripts only generate local files; no ordering integration or order action. MANUFACTURING_RELEASE additionally needs Gate G bench evidence and a signed approval file matching the package hashes (automation/export/release_check.py). |
| REQ-SRC-01 | Component database with sourcing data; unverified data recorded as UNKNOWN. | BRIEF | INSPECT | DESIGNED | sourcing/components.csv and generator; supplier availability and price unverified. sourcing/check_sourcing.py (validator entry VAL-SRC) checks the records against connectivity.yaml and the part ratings against the circuit: 0 FAIL, 29 WARN (compact BOM descriptions, C14 derating, R16 fault overload). |
| REQ-DOC-01 | CAD-derived documentation: schematic PDF, PCB views, 3D render, drawings, BOM, assembly and test instructions. | BRIEF | INSPECT | DESIGNED | Assembly/stack-up notes, bench plan, design review report and CAD exports are present. Renders show KiCad library 3D bodies and a generated placeholder for the TPS552882; the PowerPAK MOSFETs have no 3D model, so enclosure/height validation remains open. |

## 8. Release gates

| Gate | Condition | Status |
|---|---|---|
| A | Research complete: requirements and component assumptions documented. | PASS |
| B | Electrical design complete: schematic, verified pin assignments, netlist. | PASS |
| C | Simulations executed and limitations documented. | PASS |
| D | PCB complete: all components placed, all nets routed. | D (compact-22mm): OPEN; D (evaluation-board): PASS |
| E | ERC and DRC pass with no unresolved critical issues. | E (compact-22mm): OPEN; E (evaluation-board): PASS |
| F | PCBWay files generated and internally checked. | F (compact-22mm): OPEN; F (evaluation-board): PASS |
| G | Physical validation on an assembled prototype (thermal, electrical, fault). Cannot be closed by software. | OPEN: requires assembled-prototype testing (no bench records yet; cannot be closed by software) |

Gate status is computed by `scripts/validate.ps1` from the validation register, not hard-coded.
