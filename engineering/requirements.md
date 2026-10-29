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
| REQ-OUT-01 | Maximum output current 4.5 A (owner, 2026-10-29, DD-36; brief 4.0 A, DD-13). | BRIEF, owner change | CALC, SIM, TEST | VERIFIED-SIM | Hardware is sized and verified by calculation for 4.5 A (R8 8.66 kΩ, R3 24.9 kΩ; 21/21 checks with two owner deviations, DD-36), and SIM-03 regulates 4.479 A. 4.5 A exceeds the NUBM44 3.0 A typical and LD-05's 4.2 A maximum operating current; about 7 W optical exceeds its 6.0 W maximum. Owner-accepted diode-life risk (DD-36, cf. DD-13). 3.0/3.5/4.0 A builds by R8 only. NEEDS-TEST on the bench. |
| REQ-OUT-02 | True constant-current regulation of laser current. | BRIEF | SIM, TEST | VERIFIED-SIM | SIM-03: 3.996 A at every battery (3.0–4.2 V) × diode corner, including Vf < Vbat (buck mode). Model-level; NEEDS-TEST. |
| REQ-OUT-03 | Output current accuracy within ±5 % at 4.0 A over 0–50 °C board temperature. | ASSUMPTION | CALC, TEST | VERIFIED-CALC | Worst-case tolerance stack ±3.6 % (`engineering/calculations/power-stage-results.md`). |
| REQ-OUT-04 | Output voltage adapts to the diode forward voltage (no fixed-voltage setpoint). | BRIEF | SIM | DESIGNED | Current feedback only, no voltage setpoint; 0.8–22 V converter range. |
| REQ-OUT-05 | Laser current must never exceed the set current by more than 10 % during start-up, mode changes, battery transients or reconnection of the load. | DERIVED (REQ-SAFE-05) | SIM, TEST | VERIFIED-SIM | SIM-01/02/06: no overshoot above the 4.479 A regulated current at start-up or flash turn-on (limit 1.1 × 4.5 A = 4.95 A; behavioural model). NEEDS-TEST on hardware. |

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
| REQ-PWR-02 | Efficiency ≥ 93 % at 4.0 V input and the full output current (4.5 A since DD-36), judged by bench measurement. Owner deviations from the brief's > 95 %: 94 % (2026-10-25, DD-26), then 93 % (2026-10-29, DD-37). | BRIEF (target), owner deviation | CALC, TEST | VERIFIED-CALC | At 4.5 A the loss model gives 94.10 % at 4.0 V. With the evaluation board's routed copper, including switch-node copper the model omits, the estimate is 93.56 % (`reports/layout-review-evaluation-board.md`), 0.56 points above the target. NEEDS-TEST: bench efficiency (T1.7). |
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
| REQ-MFG-01 | PCBWay fabrication and assembly package generated from the real CAD files by one command. | BRIEF | CAD | VERIFIED-CAD | Both review packages pass internal checks with source/artifact hashes. Gate F passes its automated checks for the evaluation board and stays open for the compact board; neither is a manufacturing release. Since the 2026-10-26 audit the export reads the DRC state: the compact package is classed DRAFT_REVIEW_INCOMPLETE_BOARD and its fabrication ZIP carries DO_NOT_FABRICATE.txt; per-board release levels are in reports/release-readiness.md (both DRAFT_REVIEW).  Independent pre-order review (2026-10-27): evaluation U1/L1/orientation reviewed; RS1/PowerPAK and U3 land DFM disposition outstanding (AUD-PCB-06). Local documents rechecked 2026-10-28 with exact remedies, same two evaluation blockers; no CAD changed. Release-review completeness/freshness defects AUD-VAL-11/12 and dashboard scope defect AUD-DOC-05 remain OPEN; see reports/pre-order-review.md section 10. |
| REQ-MFG-02 | BOM and placement data validated against the placed footprints. | BRIEF | CAD | VERIFIED-CAD | Exporter independently re-reads BOM/CPL and checks refs, counts, signed positions, rotation and side against actual board/native KiCad data. Both actual exports pass: 30 BOM lines (one per orderable part, since 2026-10-27; was 48) / 53 parts and 52 centroid rows per variant. JLCPCB-format files for the evaluation board are derived from the checked PCBWay package (automation/export/export_jlcpcb.py). QUOTE-01 (2026-10-28) independently compared all nine original fields on 30 BOM lines including exact MPN suffixes and J1 DNS, zero discrepancies; reports/bom-quote-check.json and reports/bom-quote-sourcing-review.md. CAD/package hashes unchanged. |
| REQ-MFG-03 | No manufacturing order is placed automatically. | BRIEF | INSPECT | DESIGNED | Scripts only generate local files; no ordering integration or order action. MANUFACTURING_RELEASE additionally needs Gate G bench evidence and a signed approval file matching the package hashes (automation/export/release_check.py). |
| REQ-SRC-01 | Component database with sourcing data; unverified data recorded as UNKNOWN. | BRIEF | INSPECT | DESIGNED | sourcing/components.csv and generator; supplier availability and price unverified. sourcing/check_sourcing.py (validator entry VAL-SRC) checks the records against connectivity.yaml and the part ratings against the circuit: 0 FAIL, 29 WARN (compact BOM descriptions, C14 derating, R16 fault overload). QUOTE-01 now registered separately with original private XLS, verified arithmetic and dollar-format/ISO-currency ambiguity. Live source references and per-line 5/3-board sourcing quantities/risks in reports/bom-quote-sourcing-review.md and reports/bom-sourcing-options.csv; AliExpress Choice prices/UK delivery UNKNOWN. GBP/UK follow-up adds FX-01 conditional quote conversion, native GBP distributor price snapshots, UK eBay qualification and unadopted substitute candidates in the same report/CSV; current delivered offers UNKNOWN. Generated sourcing CSVs unchanged. Review evidence integrated into main at owner request; status remains DESIGNED pending supplier and physical verification. |
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

## 9. Separate budget-driver requirements

Scope: DD-29/30, [budget-driver plan](budget-driver-plan.md) and
[implementation handover](budget-2s-design.md), updated 2026-10-29. These rows apply only to the separate
budget circuit. Sections 1–8 and their computed A/B gates continue to describe the existing 1S boards.
All budget requirements remain OPEN. Independent numeric sources, conditional electrical screens and a
preliminary ngspice model now exist; full circuit qualification, CAD, firmware and manufacturing evidence
do not. The legacy full validator/dashboard cover A/B only; budget readiness is reported separately in
`reports/budget-2s/qualification.md` and does not pass.

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-BUD-01 | Permit two Li-ion cells in series; remove the 22 mm size constraint for this version. | BRIEF (owner, 2026-10-28), DD-29/30 | INSPECT, CAD, TEST | OPEN | Separate numeric sources created. DD-31 calculation: the maximum-resistance model regulates 5.2 V / maximum setpoint down to about 5.78 V input, conditional on the input/output resistance allocations; the hardware UV now sits below the loaded 6.0 V floor (BUD-ISS-02 mitigated in calculation). Bench dropout, pack and firmware cutoff OPEN. Original REQ-BAT-01/REQ-MECH-01 still apply to A/B. |
| REQ-BUD-02 | Target ≤£60 per accepted working driver, comparing batches of 3 and 5. | BRIEF (owner, 2026-10-28), DD-29 | INSPECT | OPEN | Full purchased quantities, PCB/stencil, paid assembly/inspection, tax, all freight, fees and rework count. Excludes laser/battery; pack/BMS/charger/host/tools/unpaid-labour scope assumptions are explicit in the plan. Complete delivered price UNKNOWN; £180/£300 are batch ceilings, not quotes. |
| REQ-BUD-03 | True CC with a 4.5 A main setpoint (owner, DD-33; 3.0/3.5/4.0 A as one-resistor builds), 3.8–5.2 V laser compliance, ±5% accuracy over 0–50 °C and ≤4.95 A normal transient peaks. | BRIEF (owner, 2026-10-29, DD-33); DERIVED (REQ-OUT-01…05) | CALC, SIM, TEST | OPEN | Conditional 4.3279–4.6542 A envelope from qualify.py; every owner V–I build is within ±5% (conditional). Precision-resistor MPNs and hot-shunt envelope remain unqualified. Preliminary 243-case loop study passes its assumed sensitivity screen; switching/compliance/normal transient proof remains OPEN. 4.5 A exceeds LD-05's 4.2 A maximum operating current: owner-accepted diode-life risk (DD-33, cf. DD-13). |
| REQ-BUD-04 | Retain default-off, external hardware interlock, independent backup overcurrent near 5.3 A (DD-33), reverse/UVLO/OVP/open/short/discharge protection and thermal/sensor fault handling. | DERIVED (REQ-PROT-01, REQ-SAFE-01…12) | CALC, SIM, INSPECT, TEST | OPEN | Conditional backup window 5.1036–5.4810 A (DD-33) includes fast-mode NAF and lies above the 4.95 A transient ceiling. DD-31: single P-FET disconnect; OVP has a calculated false-trip margin above the highest normal VBUCK. DD-32: default-off interface (series MOSFET AND pairs on latch and fault line, firmware-permit inhibit defaulting on, logic-independent EN bound at low VCTRL); 34 static checks pass conditionally (BUD-IF-01). Default-off buffer, total shutdown delay, SOA, stored-energy/fault handling and complete 2S circuit remain OPEN (BUD-ISS-02…04). Converter internal switch limit is not a laser-current ceiling. |
| REQ-BUD-05 | Use a protected balanced 2S pack with individual-cell protection and a suitable external 2S charger. | DERIVED (2S scope, battery protection) | INSPECT, TEST | OPEN | Exact pack/BMS/fuse/current/charging specification and separate system cost UNKNOWN. Aggregate voltage alone cannot protect each cell. No integrated charger planned. |
| REQ-BUD-06 | Retain continuous and 2 Hz / 50% modes, deliberate enable and latched faults. | DERIVED (REQ-MODE-01…04, DD-28) | SIM, TEST | OPEN | Fixed hardware current setpoint first. New HAL, ADC scaling, pin map, supply/hold-up and clock must be qualified; existing host tests are reusable methods only. |
| REQ-BUD-07 | Efficiency ≥93% at nominal 7.4 V and the main setpoint (4.5 A at its 4.72 V owner point), judged by bench measurement; report full-load 6.0/8.4 V, all diode corners and every owner V–I point. Owner deviation 2026-10-29 from the proposed 94% (DD-31 option a), confirmed with DD-33. | ASSUMPTION (similar efficiency, new input), owner deviation | CALC, TEST | OPEN | Operating-point estimate about 93.05% at 7.4 V / 4.72 V / 4.5 A (typical corner; only about 0.05 points of margin; maximum-resistance corner about 90%). Owner points: about 94.1% at 3.0 A, 93.9% at 3.5 A, 93.5% at 4.0 A. Labelled estimates and allocations; all corners in `reports/budget-2s/qualification.md`. No measurement. Original A/B estimates do not apply. |
| REQ-BUD-08 | Design around cheap, easy-to-source parts readily available from UK distributors or fast China channels (owner, 2026-10-29, DD-34); genuine parts for semiconductors; prefer accessible packages with stock KiCad footprints, a defined heat path and standard fabrication. | BRIEF (owner, 2026-10-29, DD-34); DERIVED (cost/assembly/footprint reviews) | CALC, INSPECT, CAD, TEST | OPEN | DD-34 swaps: SiSS23DN output FET (UK stocked) and WSL2512 shunt (LCSC stocked) replace DMP2005UFG-7 (40-week lead) and WSK2512. Remaining risks: TPS54821 (no stock KiCad footprint, 12-week DigiKey lead, LCSC stock), SRP1265A (no stock footprint), INA300/HCS74/DMG101xT/DMP2022LSS UK stock unverified. Two-layer feasibility is unproven; hidden converter pad and PowerPAK joint remain. Complete GBP inspection/assembly cost UNKNOWN. |
| REQ-BUD-09 | Implement separate authoritative variant sources and evidence, then qualify on a dummy load before laser use. | DERIVED (AGENTS.md, REQ-SAFE-12) | INSPECT, CAD, SIM, TEST | OPEN | Separate numeric source, source resolver and hash-bound calculation/model evidence implemented. DD-35: separate connectivity, `budget2s` library and generated schematic with ERC 0 errors and an exact pin-by-pin netlist match (2 warnings for the not-yet-generated U1/L1 footprints). Placement/PCB and downstream sourcing/export/firmware/release support remain to implement. Only real MEASURED budget-board records can close physical qualification. No order is placed automatically. |
