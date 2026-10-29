# Budget-2S implementation and handover

Updated 2026-10-29. Codex (AI review), requested by owner, decision DD-30; continued by Claude Code
(AI), decision DD-31 (single output P-FET, UV backstop, operating-point model).

**Stage: electrical qualification. No budget fabrication package exists and no order is authorised by this
document.** The owner requested implementation of the separate two-cell, unrestricted-size, £60 driver.
This checkpoint replaces the planning-only state with numeric sources, executable calculations, a
preliminary ngspice current-loop model and an explicit fault/qualification register. It does not inherit
the original single-cell boards' CAD, firmware or release results.

## Source and command map

| Purpose | Authoritative source / output |
|---|---|
| Numeric candidate and study assumptions | `engineering/design/budget-2s/parameters.yaml` |
| Separate source resolution | `automation/nubm44/variants.py`; original A/B defaults remain unchanged |
| Circuit connectivity | Reserved `engineering/design/budget-2s/connectivity.yaml`; **not created until the circuit is qualified** |
| Placement | Reserved `hardware/budget-2s/placement.yaml`; **not created** |
| Electrical qualification | `automation/budget/qualify.py` → `reports/budget-2s/qualification.md`, JSON and hash manifest |
| Operating point, dropout, UV/OV margins, efficiency estimate | `automation/budget/power.py` (called by `qualify.py`; results in the same report) |
| Preliminary current loop | `automation/budget/loop_model.py` → `reports/budget-2s/loop-model.md`, all 243 corners in JSON, ngspice `.cir`/raw data/log, hash manifest |
| Manufacturer records | BUD-01…22 in `research/sources/budget-driver-sources.md`; downloaded PDFs ignored, hashes recorded |
| Earlier costs and design rationale | `engineering/budget-driver-plan.md`, `reports/bom-quote-sourcing-review.md` |

Run from the repository root (prefix shell commands with `rtk`, per the owner’s RTK.md):

```powershell
rtk proxy .venv/Scripts/python.exe automation/budget/qualify.py
rtk proxy .venv/Scripts/python.exe automation/budget/loop_model.py
rtk proxy .venv/Scripts/python.exe -m pytest tests -q
rtk proxy .venv/Scripts/python.exe automation/validation/validate.py
```

`qualify.py` currently **exits 1**, because all twelve manufacturing prerequisites remain unresolved: four
CONDITIONAL calculations (setpoint, dropout, UV, OVP margin), one FAIL (efficiency estimate below 94%, owner
decision) and seven OPEN. That is the intended readiness result, not a failed Python invocation.
`loop_model.py` exits 0 only when its actual sensitivity margins and independent ngspice/equation agreement
pass; its physical qualification stays OPEN. Existing `validate.py` still validates **A/B only**. A return
code of zero there is not evidence for budget-2s. Do not add budget failures to the A/B known-limitations
baseline to conceal them. Do not add `budget-2s` to legacy default loops until every downstream generator,
firmware/sourcing check, layout model and release gate supports the independent circuit.

## Development architecture

Protected balanced 2S pack → fuse → reverse-polarity P-FET → TPS54821 buck and bulk output filter →
four-terminal 10 mΩ shunt → single P-FET output disconnect (source at VBUCK, gate grounded when on, DD-31)
→ grounded-cathode laser. Keep bulk capacitance upstream of the disconnect. The disconnect's body diode
blocks VBUCK → laser; a back-to-back second FET would only block the reverse path and was removed. The INA186A2 primary current loop and separate INA300 comparator use distinct
Kelvin traces from the shunt; they still share its physical failure modes. OVP must observe physical VBUCK
upstream of the disconnect, rather than the converter's current-derived feedback or only an isolated laser.

The 3.3 V rail supplies the SOIC ATtiny, sensing/protection and hardware latch. Supervised asynchronous
clear, external interlock, OC and UV/OV trips must override firmware. A deliberate arm edge sets the latch;
firmware mode control may inhibit emission but must never clear a hardware fault automatically. Buck EN
and the output FET driver need a **qualified default-off buffer and bias network**. That interface is not
complete: do not wire the Schmitt latch directly into an arbitrary EN pulldown and assume its 3.3 V drive
or absence-of-supply behaviour. Preserve fault/default-off behaviour on a stopped CPU, reset and brownout.

| Function | Development candidate | Qualification / action before adoption |
|---|---|---|
| Externally compensated buck | TPS54821RHLT, BUD-01 | Retains a hidden pad. 17 A maximum switch limit is not a laser-current limit. Efficiency is at risk at low Vf; qualify before freezing. |
| Magnetics | SRP1265A-4R7M, BUD-05 | Larger package accepted. Catalogue Isat exceeds switch limit, but hot biased L/core loss/fault response remain UNKNOWN. |
| Primary sensing | INA186A2IDCKR, PREORDER-07; WSK2512R0100FEA, BUD-22 | Four-terminal shunt has a different land than a generic 2512. Exact 0.1% divider MPN/TCR and shunt temperature envelope OPEN. |
| Independent OC | INA300AIDGSR, BUD-06 | Hard-enable from rail; latched HIGH; fast DELAY and HYS float. The 2.52 kΩ candidate includes 500 µV NAF. No MCU-controlled disable/reset. |
| Physical UV/OV | TLV6700DDCR, BUD-18 | Separate thresholds, tied open-drain fault clear. UV policy conflicts with full 6.0 V operation; physical OV response/survival remain OPEN. |
| Fault/arm latch | SN74HCS74DR, BUD-19 | All inputs are Schmitt; slow fault pullups acceptable in principle. Buffer/load proof and simultaneous clear/arm recovery remain OPEN. Ordinary LVC74A is not an automatic substitute. |
| Control reset supervisor | TLV803EA29DBZR, BUD-20 | 2.93 V nominal/200 ms; exact DBZ pinout. Apply threshold/delay bounds and rail sequencing. |
| 3.3 V control supply | MCP1703AT-3302E/MB, BUD-21 | SOT-89 pin 1 GND, 2/tab VIN, 3 VOUT. Use full-temperature ±3% plus load/line terms, actual effective output C, thermal and reverse-current review. |
| MCU | ATTINY1616-SN, PREORDER-08 | SOIC-20 port map below. Candidate 10 MHz; HAL, ADC/reference, fuses, brownout and target build not yet adapted. |
| Reverse input FET | DMP2022LSS-13, BUD-15 | SO-8, ±12 V gate; gate grounded, so \|Vgs\| = VBAT_PROTECTED ≥ 4.5 V in operation. Qualify orientation, fuse and hot/transient stress. |
| Output disconnect (single) | **DMP2005UFG-7** selected for development (DD-31), BUD-16; DMP2022LSS-13 compared | Lower loss at every generated operating point. \|Vgs\| ≥ 3.84 V in operation (2.5 V specification applies); ±10 V gate versus 8.4 V switch-short fault, transient clamp OPEN. Exposed-drain land/paste/X-ray review OPEN. |
| Low-current gate driver | AO3400A, BUD-17 | Requires sufficient guaranteed gate drive; typical threshold is not an on-resistance guarantee. Exact bias/buffer/clamp still OPEN. |

No commercial precision-resistor/capacitor/connector/fuse suffix is invented to complete a BOM. Those lines,
all final prices, stock and complete delivered GBP totals remain UNKNOWN. Candidates are new-circuit study
choices, not authorised substitutions into A/B or an orderable approved BOM.

## Findings that must be resolved before layout

| ID | Finding | Remedy / evidence needed | State |
|---|---|---|---|
| BUD-ISS-01 | Original easy-SOIC disconnect proposal consumed too much loss allowance. DD-31: back-to-back pair replaced by one DMP2005UFG-7; the operating-point model bounds dropout (BUD-PWR-01 CONDITIONAL). The efficiency **estimate** at 7.4 V / 4.5 V / 4 A is still below 94% (BUD-EFF-01 FAIL). | **Owner decision** (DD-31): accept a lower budget target judged on the bench, or change the architecture. REQ-BUD-07 is not relaxed silently. Then make the fuse, connector and copper meet the `power_model` allocations, and measure efficiency. | MITIGATED IN MODEL; efficiency target needs owner decision |
| BUD-ISS-02 | 147 kΩ / 10 kΩ UV comparator could trip at 6.303 V, inside the proposed 6.0 V operating range. DD-31: 130 kΩ makes the hardware UV a backstop below the loaded floor (BUD-UV-01 CONDITIONAL, margin in the report). | Write the firmware operating cutoff (stop before dropout; refuse arming on a low resting pack). Choose a pack whose cells are rated to the `pack_cutoff_floor_v` assumption. Verify the input allocation with the real fuse/connector. Protected balanced pack/per-cell BMS remains mandatory. | MITIGATED IN CALCULATION; firmware policy and pack OPEN |
| BUD-ISS-03 | Bare latch/EN/FET interfaces have no complete guaranteed 3.3 V drive/loss-of-supply proof. | Finish a default-off buffer/driver/bias design, prove high/low voltages and current over supply/tolerance, supervisor and interlock sequencing, and absence of back-power. Then model and bench inject rail/CPU faults. | OPEN |
| BUD-ISS-04 | Catalogue 10 µs OC is a typical detector setting, not a guaranteed total shutdown or laser-safe fault energy. | Include comparator window/overdrive, fault wiring, latch, buffer, FET charge, SOA, capacitors and inductive paths. Obtain guaranteed bounds where available; record remaining UNKNOWNs and measure the complete chain. | OPEN |
| BUD-ISS-05 | A simple loop study initially failed 19/243 corners with 330 Ω compensation; a 180 Ω analysis candidate passes the stated assumed sweep. | Keep the generated 180 Ω evidence; qualify actual controller/laser/capacitor dynamics, component tolerances and switching faults. The earlier 330 Ω result explains why the candidate changed, not a reason to waive margins. | MITIGATED IN MODEL; real-circuit qualification OPEN |

The generated report gives exact calculated bounds rather than copying rounded numbers into a second
source. Setpoint accuracy is conditional on procurement and the stated hot-shunt assumption. The capacitor
energy screen includes an 8.4 V buck switch-short case; a small laser-side capacitor does not limit energy
from an inductor or a failed/slow disconnect.

## SOIC MCU port reference

Source PREORDER-08, DS40002204A pp.15,18. These are verified manufacturer port/pad assignments, **not a new
netlist**. Keeping a port function does not preserve its old VQFN physical pad number.

| SOIC pin | Port / supply | Intended role to carry or qualify |
|---:|---|---|
| 1 | VDD | Regulated control rail; never raw 2S |
| 2 | PA4 / ADC0 AIN4 | NTC excitation or reassigned under a documented HAL profile |
| 3 | PA5 / ADC0 AIN5 | Board NTC |
| 4 | PA6 / ADC0 AIN6 | Current monitor |
| 5 | PA7 / ADC0 AIN7 | Physical output voltage monitor |
| 6 | PB5 / ADC0 AIN8 | 2S battery monitor with new divider/reference |
| 7 | PB4 / ADC0 AIN9 | Optional laser NTC |
| 8 | PB3 | Spare / diagnostics |
| 9 | PB2 | Indicator; recalculate external-short fault power |
| 10 | PB1 | Independent OC/fault state monitor |
| 11 | PB0 | Converter status if useful; never a substitute for physical OVP |
| 12–15 | PC0–PC3 | Budget arm/fault/supply interfaces, exact allocation OPEN |
| 16 | PA0 / UPDI | Programming/debug |
| 17 | PA1 | Emission inhibit, polarity/interface OPEN |
| 18 | PA2 | Hardware interlock state |
| 19 | PA3 | User input |
| 20 | GND | Ground; no SOIC exposed pad |

ADC protection/scaling, ratiometric NTC measurement, reference supply headroom, source impedance/settling,
2S pack stop/restart thresholds, hold-up/mode behaviour and fault-reset policy require a separate firmware
profile and tests. Do not flash the existing VQFN board image and assume equivalent sensing.

## Fault matrix and prototype acceptance work

Every row is an analysis/test requirement, not a measured result. Use a current-limited supply and suitably
rated dummy load before any laser. Only actual MEASURED records may enter the bench-results directory.

| Event | Required hardware / firmware outcome | Present proof / missing test |
|---|---|---|
| Initial power, slow ramp or rail absent | Buck and output disconnect stay off; no arm edge until supervised rail and deliberate enable | Circuit/bias and sequencing OPEN |
| MCU reset, watchdog, stuck instruction or pin tristate | Hardware default off or independent fault chain stops output; no automatic re-arm after fault | Existing A/B host results do not prove budget hardware; profile and injection OPEN |
| Interlock opens / contact chatters | Asynchronous hardware clear and isolation, latched until deliberate recovery | Contact bias, timing and clear recovery OPEN |
| Current exceeds backup threshold / primary CSA fails low | Independent latched OC clears power without MCU help | Conditional threshold screen only; response/energy OPEN |
| Shunt shorts, Kelvin trace opens/shorts or CSA inputs fail | Defined safe disposition; identify common-cause blindness | Shared shunt can defeat both loops; analyse physical redundancy or mitigation before release |
| Load opens / current loop winds up | Upstream physical OVP shuts down, isolates and latches; no automatic pulsing | Threshold screen only; switching/startup/COMP model OPEN |
| Load reconnects, including before full discharge | Normal transient peak ≤4.4 A, no bulk-capacitor dump into diode | Switching model, disconnect sequencing and bench current/energy OPEN |
| Output short / repeated flash transitions | Controlled current and latched fault as appropriate; no damage or unsafe recovery | Converter switch limit is not a laser bound; model/bench OPEN |
| Buck high-side switch fails short | Output disconnect interrupts raw-pack fault; clamp/TVS/SOA and current paths remain rated | 8.4 V capacitor-energy screen only; fault delay/SOA/inductor paths OPEN |
| Output FET fails short / body diode conducts | Single-fault disposition documented; avoid claiming isolation from EN alone | Body-diode orientation and single-FET/driver faults OPEN |
| Reversed 2S input / plug transient | Defined reverse-blocking, fuse and voltage-clamp response; no control-rail backfeed | Exact fuse/clamp, orientation and transient test OPEN |
| Pack UV / one weak cell | Firmware stops at the operating cutoff; hardware UV (5.40–5.62 V falling) latches if firmware does not; BMS protects individual cells | UV backstop margin calculated (DD-31). Aggregate pack ADC cannot detect every imbalance; exact pack/BMS and firmware policy OPEN |
| Input sags into dropout, then recovers | Current must not overshoot 4.4 A while COMP unwinds; firmware stops before dropout | Dropout bound calculated. TPS54821 PWRGD falls when VSENSE < 92% of Vref (BUD-01 p.6), i.e. when current regulation is lost, and can serve as an MCU indication. Recovery transient needs a switching model and bench test |
| Board/laser NTC open, short or overtemperature | Fault latch/default off; optional sensor rules cannot disable board protection | New rail/reference/ADC profile and placement/bench OPEN |
| Disabled output / external hot-plug | Discharge criterion met; no stored-energy reconnection spike | Bleed arithmetic only; verify worst C, cable and detector/disconnect behaviour |

## Next implementation steps for another agent

1. Read AGENTS.md, PROGRESS Current state, this file and both generated budget reports. Verify hashes via
   `nubm44.evidence.problems`; regenerate with the producing scripts, never edit results.
2. BUD-ISS-01/02 are mitigated in calculation (DD-31). The efficiency target needs an owner decision. Next,
   resolve BUD-ISS-03/04: the guaranteed default-off buffer/driver and the total fault response and energy.
   The SN74HCS74 guarantees VOH ≥ VCC − 0.1 V and VOL ≤ 0.1 V only at |IO| ≤ 20 µA (BUD-19 p.5), so keep its
   loads high-impedance. TPS54821 EN has an internal pull-up whose current is given only as typical
   (BUD-01 p.5), so a default-off pulldown needs explicit margin. Choose exact passives, a fuse and connector
   that meet the `power_model` allocations, gate clamps and the protected 2S pack interface. Keep price/stock
   UNKNOWN until supported by dated supplier evidence. Request 3/5-unit quotes only through an owner-approved
   contact.
3. Extend the preliminary model to startup/flash/open/short/reconnect, finite voltage/COMP/SS limits and
   component corners. Record assumptions and actual failures. A laser survival bound remains a bench task.
4. Then create the **separate** canonical connectivity and reviewed symbol/land sources. Extend schematic,
   library, PCB, layout, sourcing, export, firmware and release tooling to select the registered budget
   sources. Never repoint the shared A/B YAML or reuse their PASS evidence. Review all exact pin/land maps.
5. Generate budget schematic/ERC/netlist, place and route a standard two-layer board if qualified; use four
   layers if electrical/thermal checks require it. Preserve tight switching loops and Kelvin routing despite
   unrestricted size. DRC → layout review → manufacturing exports → footprint/BOM/CPL checks, with all hashes.
6. Prepare the budget HAL/target build, host/register/mutation tests and a budget-specific bench-test schema;
   define release reviews and inspection (including hidden joints) before a PROTOTYPE_CANDIDATE disposition.
7. Obtain complete GBP landed quotes for 3/5 accepted working boards, paid inspection/rework and all spares;
   owner chooses the batch and places any order. A complete total is currently UNKNOWN.

At each milestone update this handover as needed, PROGRESS (Current/Next/Log), scoped requirements and any
affected audit/decision records; commit with the actual check results and push `main` to origin. Keep Gate G
OPEN until real budget-board data exists. Preserve the pre-existing untracked `reports/setup.log`.
