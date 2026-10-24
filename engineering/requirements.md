# Engineering requirement register

Authoritative list of requirements for the NUBM44 driver. Every design artefact traces back to an ID here.

- **Source** says where a requirement came from: `BRIEF` (the project brief), `DERIVED` (engineering consequence of
  another requirement), or `ASSUMPTION` (a default chosen here that the owner should confirm).
- **Verify** is how the requirement is checked: `CALC` (engineering calculation), `SIM` (simulation),
  `CAD` (ERC/DRC or a scripted CAD check), `INSPECT` (design review), `TEST` (physical test on hardware).
- **Status** values: `OPEN` (not yet addressed), `DESIGNED` (implemented in the design, not yet verified),
  `VERIFIED-CALC`, `VERIFIED-SIM`, `VERIFIED-CAD`, `NEEDS-TEST` (only hardware testing can close it),
  `AT-RISK` (evidence suggests it may not be met), `INFEASIBLE` (evidence shows it cannot be met as written),
  `BLOCKED` (needs an owner decision).

Statuses are updated as work proceeds; see the change history in git.

## 1. Load and output

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-LD-01 | Drive a genuine Nichia NUBM44 laser diode. | BRIEF | INSPECT | DESIGNED | No public Nichia NUBM44 datasheet exists; ratings come from a module maker's table plus community LIV data (`research/nubm44-research.md`). |
| REQ-OUT-01 | Maximum output current 4.0 A. | BRIEF | CALC, SIM, TEST | AT-RISK | Hardware is sized and verified by calculation for 4.0 A. 4.0 A exceeds the NUBM44 typical 3.0 A and, for most units, the 6.0 W optical maximum (DD-13). |
| REQ-OUT-02 | True constant-current regulation of laser current. | BRIEF | SIM, TEST | DESIGNED | High-side shunt → INA186 → FB loop on a buck-boost that regulates whether Vf is above or below Vbat (DD-01, DD-02). |
| REQ-OUT-03 | Output current accuracy within ±5 % at 4.0 A over 0–50 °C board temperature. | ASSUMPTION | CALC, TEST | VERIFIED-CALC | Worst-case tolerance stack ±3.6 % (`engineering/calculations/power-stage-results.md`). |
| REQ-OUT-04 | Output voltage adapts to the diode forward voltage (no fixed-voltage setpoint). | BRIEF | SIM | DESIGNED | Current feedback only, no voltage setpoint; 0.8–22 V converter range. |
| REQ-OUT-05 | Laser current must never exceed the set current by more than 10 % during start-up, mode changes, battery transients or reconnection of the load. | DERIVED (REQ-SAFE-05) | SIM, TEST | OPEN | Overshoot is the main cause of laser diode failure. |

## 2. Battery input

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-BAT-01 | Single-cell lithium-ion input, 3.7 V nominal. | BRIEF | INSPECT | OPEN | |
| REQ-BAT-02 | Operating input range to be determined by research (expected about 2.8–4.2 V under load). | BRIEF | CALC | VERIFIED-CALC | 2.83 V (hardware UVLO off) to 4.20 V at the board; firmware cut-off 2.9 V loaded. |
| REQ-BAT-03 | Evaluate 16340, 14500, 18500, 18650 and 21700 cells; separate "fits" from "electrically suitable". | BRIEF | CALC | VERIFIED-CALC | 18650/21700 cells with ≥ 15 A CDR are suitable; 16340 and 14500 are unsuitable; 18350/18500 marginal (`research/battery-and-mechanics.md`). |
| REQ-BAT-04 | One explicit battery polarity definition (centre spring and perimeter contact) used everywhere: schematic, PCB, silkscreen, drawings, instructions. | BRIEF | INSPECT, CAD | BLOCKED | Interpretation adopted: spring = B+, ring = B− (DD-12). Owner must confirm before Gate F release. |
| REQ-BAT-05 | Battery undervoltage lockout prevents over-discharge of the cell. | BRIEF | CALC, TEST | DESIGNED | Hardware UVLO via EN/UVLO divider (3.08 V on / 2.83 V off) plus firmware cut-off. |

## 3. Power conversion

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-PWR-01 | Prefer a high-efficiency boost topology; compare at least three architectures numerically. | BRIEF | CALC | VERIFIED-CALC | Four architectures compared (`research/architecture-comparison.md`). |
| REQ-PWR-02 | Efficiency target > 95 % at 4.0 V input, 4 A output. | BRIEF (target) | CALC, TEST | AT-RISK | Estimated 94.6 % at 4.0 V with the required protection; > 95 % is not achievable without removing protection. |
| REQ-PWR-03 | Efficiency target ≥ 86 % at 3.0 V input, 4 A output. | BRIEF (target) | CALC, TEST | VERIFIED-CALC | Estimated 91.3 % at 3.0 V (worst diode). Bench confirmation needed. |
| REQ-PWR-04 | Converter components operate with margin: switch/inductor peak current ≥ 20 % below the minimum rated limit at worst case (minimum battery, maximum Vf, maximum current). | DERIVED | CALC | VERIFIED-CALC | Worst average inductor current 8.9 A including a 20 % margin against the 10.2 A minimum ILIM; 8.5 A peak against 14 A Isat. |
| REQ-PWR-05 | Input and output filtering. | BRIEF | CALC, SIM | DESIGNED | 3 × 22 µF input, 4 × 22 µF output; ripple 8.9 % p-p worst corner. |

## 4. Control and modes

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-MODE-01 | Continuous output mode. | BRIEF | TEST | OPEN | |
| REQ-MODE-02 | Flashing output mode. | BRIEF | SIM, TEST | OPEN | |
| REQ-MODE-03 | Default flash pattern 2 Hz, 50 % duty. | ASSUMPTION | INSPECT | OPEN | The brief gives no pattern. Owner to confirm. |
| REQ-MODE-04 | Mode transitions cause no overshoot (REQ-OUT-05) and no output-capacitor discharge through the diode. | BRIEF | SIM, TEST | OPEN | |

## 5. Protection and safety

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-PROT-01 | Reverse-polarity protection using a MOSFET (not a series diode). | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-01 | Hardware shutdown path that does not depend on firmware. | BRIEF | INSPECT, TEST | OPEN | |
| REQ-SAFE-02 | External safety interlock: output is disabled in hardware when the interlock loop is open. | BRIEF | INSPECT, TEST | OPEN | |
| REQ-SAFE-03 | Default-disabled start-up: no emission on battery insertion until enabled by the user. | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-04 | Soft-start of laser current. | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-05 | Output overshoot limiting. | BRIEF | SIM, TEST | OPEN | See REQ-OUT-05. |
| REQ-SAFE-06 | Battery undervoltage lockout. | BRIEF | TEST | OPEN | Same as REQ-BAT-05. |
| REQ-SAFE-07 | Overcurrent protection. | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-08 | Thermal shutdown or thermal monitoring. | BRIEF | TEST | OPEN | |
| REQ-SAFE-09 | Open-load protection (laser disconnected). | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-10 | Output short-circuit protection. | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-11 | Safe shutdown with controlled output discharge. | BRIEF | SIM, TEST | OPEN | |
| REQ-SAFE-12 | Physical testing uses a dummy load and controlled laser-safety arrangements (Class 4). | BRIEF | INSPECT | OPEN | `documentation/testing/` |

## 6. Mechanical and PCB

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-MECH-01 | Circular PCB, 22.0 mm outside diameter (Variant A). | BRIEF | CAD | OPEN | |
| REQ-MECH-02 | Centre spring contact and perimeter battery contact. | BRIEF | CAD | OPEN | |
| REQ-MECH-03 | External laser diode connection pads. | BRIEF | CAD | OPEN | |
| REQ-MECH-04 | Evaluate 2-layer and 4-layer stack-ups. | BRIEF | CALC | VERIFIED-CALC | 4-layer chosen; 2-layer rejected for density and current paths (DD-14). |
| REQ-MECH-05 | Larger evaluation board (Variant B) with the same electrical architecture if 22 mm cannot carry full test access. | BRIEF | INSPECT | OPEN | Variant B must not silently replace Variant A. |
| REQ-PCB-01 | Layout priorities: small switching loops, input caps near switches, Kelvin sensing, quiet feedback, thermal copper, grounding strategy. | BRIEF | INSPECT, CAD | OPEN | |
| REQ-TEST-01 | Test points where practical. | BRIEF | CAD | OPEN | |

## 7. Tooling, manufacturing, documentation

| ID | Requirement | Source | Verify | Status | Notes |
|---|---|---|---|---|---|
| REQ-CAD-01 | Native, editable KiCad schematic and PCB. | BRIEF | CAD | OPEN | |
| REQ-CAD-02 | EasyEDA compatibility where practical. | BRIEF | INSPECT | OPEN | |
| REQ-CAD-03 | ERC and DRC run automatically; no violations silenced without a documented cause. | BRIEF | CAD | OPEN | |
| REQ-CAD-04 | Netlist cross-checked against a machine-readable connectivity specification. | BRIEF | CAD | OPEN | |
| REQ-MFG-01 | PCBWay fabrication and assembly package generated from the real CAD files by one command. | BRIEF | CAD | OPEN | |
| REQ-MFG-02 | BOM and placement data validated against the placed footprints. | BRIEF | CAD | OPEN | |
| REQ-MFG-03 | No manufacturing order is placed automatically. | BRIEF | INSPECT | OPEN | |
| REQ-SRC-01 | Component database with sourcing data; unverified data recorded as UNKNOWN. | BRIEF | INSPECT | OPEN | `sourcing/components.csv` |
| REQ-DOC-01 | CAD-derived documentation: schematic PDF, PCB views, 3D render, drawings, BOM, assembly and test instructions. | BRIEF | INSPECT | OPEN | |

## 8. Release gates

| Gate | Condition | Status |
|---|---|---|
| A | Research complete: requirements and component assumptions documented. | OPEN |
| B | Electrical design complete: schematic, verified pin assignments, netlist. | OPEN |
| C | Simulations executed and limitations documented. | OPEN |
| D | PCB complete: all components placed, all nets routed. | OPEN |
| E | ERC and DRC pass with no unresolved critical issues. | OPEN |
| F | PCBWay files generated and internally checked. | OPEN |
| G | Physical validation on an assembled prototype (thermal, electrical, fault). Cannot be closed by software. | OPEN |

Gate status is computed by `scripts/validate.ps1` from the validation register, not hard-coded.
