# Design decisions

Each entry records the decision, the evidence and the alternatives considered. Numerical values live in
`engineering/design/parameters.yaml`; calculated margins are in `engineering/calculations/power-stage-results.md`.

## DD-01 Converter architecture: TPS552882 4-switch buck-boost
The NUBM44 compliance window (3.8–5.2 V) overlaps the loaded cell range (2.83–4.2 V). Only a buck-boost both
regulates on either side of the input and isolates the diode when off. Full comparison:
`research/architecture-comparison.md`. Alternatives: TPS61288 boost + clamp (B), TPS552892 (C), XL6009 (D).

## DD-02 Primary current regulation: high-side shunt → INA186A2 → FB
- 10 mΩ shunt between VOUT and the laser anode (LD+). The laser cathode is board ground, which is also
  battery negative and the host body. A stray contact between the cathode lead and the host therefore
  cannot bypass current sensing.
- INA186A2 (gain 50, ±50 µV, common mode to 40 V, runs from 1.7 V) gives 0.5 V/A.
- Divider R_FB_TOP 6.65 kΩ / R_FB_BOT 10.0 kΩ (0.1 %) → FB = 1.2 V at 3.996 A.
- Soft start ramps the TPS552882 reference 0→1.2 V in 4 ms, so the laser current ramps 0→I_set in 4 ms.
- Worst-case setpoint tolerance ±3.6 % (target ±5 %).
- Alternate setpoints change R_FB_TOP only: 3.5 A → 4.53 kΩ, 3.0 A → 2.49 kΩ.

## DD-03 Independent backup current ceiling: TPS552882 ISP/ISN
ISP/ISN sense the same shunt. The internal loop limits V(ISP−ISN) to 48/50/52 mV, i.e. **4.8–5.2 A**. This loop
does not depend on the INA186, the FB network or firmware. The 10 mΩ shunt (rather than 5 mΩ) is chosen
specifically so this ceiling is meaningful; it costs 0.08 W. CDC is left floating, so ISP/ISN inject nothing
into FB.

## DD-04 Reverse-polarity protection: high-side P-MOSFET (SiSS23DN)
Drain to the centre spring, source to VBAT, gate to GND through 100 kΩ. A low-side N-FET would lose
≈ 0.1–0.2 W less, but board ground would no longer equal the host body. If the laser cathode lead then
touched the host, the protection would be bypassed on reverse insertion, shorting the cell through the
converter's body diodes. The high-side P-FET keeps ground = host and is immune to that double fault.
Stock risk (LCSC 220 pcs): alternate DMP2005UFG has a different footprint and needs a footprint review first.

## DD-05 Open-load / over-voltage protection without touching FB
- A diode OR from a VOUT divider into FB was analysed and rejected. The diode's ~110 mV/decade soft knee and
  −2 mV/K drift either disturb the current setpoint near the maximum diode voltage, or force the clamp above
  ~6.8 V.
- **Primary trip:** ATtiny1616 AC0 compares VOUT/6 against its DAC reference (5.6 V equivalent). It is a hardware
  comparator, configured by firmware. The firmware forces EN low and latches the fault.
- **Firmware-independent backstop:** BZT52C6V2 Zener into a DMG1012T gate (4.7 kΩ pull-down) pulls EN/UVLO low
  at about 6.4–7.3 V.
- **Last resort:** the TPS552882's internal 23.5 V OVP.
- Output capacitors are rated 16 V and the INA186 40 V. A 4.7 kΩ bleeder discharges VOUT after shutdown; with the
  input isolated this costs no standby current.

## DD-06 Hardware enable chain (default off)
The EN/UVLO pin is driven by a VBAT divider (49.9 kΩ / 33.2 kΩ). This gives hardware UVLO at 3.08 V on and
2.83 V off, using the pin's 1.23 V comparator and 5 µA hysteresis current. Three open-drain pull-downs act
as a wired AND:
- **Q_EN (DMG1012T):** gate pulled up to VMCU, so it is ON by default and the converter is OFF. Firmware must
  actively drive PA1 low to enable. A reset, a crash with the watchdog, or a missing MCU leaves the laser off.
- **Q_IL (DMG1012T):** gate pulled up by the interlock pad. An open external interlock loop holds EN low
  regardless of firmware.
- **Q_OV:** the Zener backstop (DD-05).

## DD-07 Microcontroller: ATtiny1616-MNR
- VQFN-20 3 × 3 mm, 1.8–5.5 V, two ADCs, three analog comparators, DAC, 1-wire UPDI.
- Supplied from VBAT through a Schottky (D2, RB521S30 in SOD-523 since DD-17) into 10 µF (C16). While the MCU
  sleeps, this hold-up keeps RAM and the RTC alive through short power interruptions, which is how a clicky
  tail switch changes mode.
- Pin map (verified against Table 5-1 of the datasheet):

| Pin | Port | Function |
|---|---|---|
| 19 | PA0 | UPDI programming |
| 20 | PA1 | LASER_EN_N (low = enable) |
| 1 | PA2 | INTLK_N sense through 47 kΩ (async pin) |
| 2 | PA3 | SW e-switch |
| 5 | PA4 | NTC_PWR: bias supply for both NTC dividers, on only while measuring |
| 6 | PA5 | NTC board (ADC0 AIN5) |
| 7 | PA6 | CS_OUT current monitor (ADC0 AIN6, as read by the firmware) |
| 8 | PA7 | VOUT_SENSE (ADC1 AIN3, AC0 AINP0) |
| 9 | PB5 | VBAT_SENSE (ADC0 AIN8, AC2 AINP2: instant power-loss detection) |
| 14 | PB0 | PG (TPS552882 power good; internal pull-up) |
| 13 | PB1 | CC (TPS552882 backup limit active; internal pull-up) |
| 12 | PB2 | IND indicator output (plain GPIO; TCA0 WO2 would allow PWM later) |
| 10 | PB4 | NTC_LD external thermistor (ADC0 AIN9) |

  Unused: PB3, PC0–PC3.

- **Hold-up budget:** only the MCU itself runs from VMCU during an interruption (standby with AC2, about
  a few µA).
- **Kept off VMCU:** the INA186 is supplied from VBAT; the interlock pull-up goes to VBAT; the NTC dividers
  are biased from PA4. That way none of them drains the 10 µF.
- **Before sleeping, firmware disables** the PG/CC pull-ups.

## DD-08 Operating modes and user interface
- Continuous and flash, with flash at 2 Hz / 50 % by default (REQ-MODE-03, assumption).
- Mode advances on a short power interruption (< 0.5 s) or a press of the optional e-switch pad.
- Each turn-on enforces a 2 s emission delay with the indicator active, and requires the interlock to be closed.
- Low-voltage behaviour: warn at 3.1 V loaded (indicator blinks 4 Hz), latch off at 2.9 V for 200 ms, and refuse
  to start below 3.2 V resting. *Correction (firmware design):* the earlier "step down" is not possible. The
  current is set in hardware, and toggling EN restarts the 4 ms soft start, so firmware can only warn and
  cut off.

## DD-09 Converter configuration
- MODE → AGND: internal VCC, FPWM. FPWM keeps loop dynamics fixed and lets the converter pull energy back during
  current reductions.
- DITH/SYNC → AGND: no dithering.
- R_FSW 33.2 kΩ: 595 kHz.
- R_ILIM 27.4 kΩ: 12.0 A typ, 10.2 A min average inductor current; worst case needs 8.9 A including a 20 % margin.
- Compensation 1.2 kΩ + 56 nF, Cp 680 pF: phase margin ≥ 111° and gain margin ≥ 12 dB over 12 corners
  (battery 2.83–3.7 V × diode corner × dynamic resistance 0.7–1.5×).

## DD-10 Magnetics and capacitors
- L1 XGL5030-102MEC: 1.0 µH, 4.8/5.8 mΩ, Isat 10.2 A at 20 % and 14 A at 30 %. The worst operating peak is 8.5 A.
- Input: 3 × 22 µF 16 V X5R 0805 plus 100 nF.
- Output: 4 × 22 µF 16 V X5R 0805 plus 100 nF, giving a laser ripple estimate of 8.9 % p-p at the empty-cell corner.
- DC-bias retention is assumed at 50–55 % (UNKNOWN from vendors; to be measured).

## DD-11 Laser output
LD+ comes from the shunt and LD− is ground. A PMEG4010CEJ Schottky sits across the output
(cathode LD+) to clamp reverse voltage and ESD; the NUBM44 reverse rating is UNKNOWN.
The diode must never be hot-plugged. The 4.7 kΩ bleeder doubles as the static bleed for the diode terminals.

## DD-12 Battery polarity interpretation
Centre spring = B+, perimeter ring = B− (via the host body), labelled B+/B− everywhere and never
"cathode/anode". This is about 90 % confidence from host conventions. Reverse-polarity protection limits a
wrong guess to "does not work".

**Owner decision (2026-10-25):** polarity does not matter to the owner, provided the board marks it clearly;
the owner adapts the host. The definition above therefore stands. Both boards carry it on the silkscreen:
- compact: "B+" beside the centre spring pad and "B-" beside the ring on the bottom (battery) side, plus
  "B-" beside the ring on the top;
- evaluation: "B+ INPUT" and "B- INPUT" beside the wire pads.

All labels meet PCBWay's legend limits (MFG-01). The 22 mm board has no room for longer words. REQ-BAT-04
is no longer blocked. T3.3 still checks the host before first power.

## DD-13 Laser current setpoint
The default build is 4.0 A as specified. 4.0 A exceeds the NUBM44's typical 3.0 A operating current, and most
units exceed the 6.0 W optical maximum there. 3.5 A and 3.0 A builds need only R_FB_TOP changed.
Recommendation to the owner: consider 3.5 A for diode life.

**Owner decision (2026-10-25):** keep 4.0 A. The owner accepts the diode-life risk. The 3.5 A and 3.0 A
builds stay available through R_FB_TOP alone.

**Superseded 2026-10-29 by DD-36:** the owner set 4.5 A for the A/B boards too.

## DD-14 PCB stack-up
4 layers, 1.6 mm, 1 oz on all layers, ENIG finish (PCBWay standard 4-layer: 7628 prepreg 0.1855 mm, 1.03 mm core).
- **Why not 2 layers:** about 50 parts (VQFN-HR-26 and VQFN-20 included) on a 22 mm disc need inner planes for
  routing and a solid ground reference. A 2-layer board would also force the 8 A input path and the switching
  loops onto shared outer copper.
- **Why 1 oz outer:** the 0.25 mm pads at 0.5 mm pitch on the RPM0026A package etch better at 1 oz.
- **Currents:** the high-current paths are short pours on several layers.

## DD-15 Thermal approach
About 1.0–1.6 W is dissipated on a 22 mm board. Convection alone cannot remove it, so the board must be clamped
in a metal pill, with the GND perimeter ring as the heat path. Planes and vias connect hot parts to that ring.
- An on-board NTC feeds firmware derating.
- An optional external NTC pad monitors the laser module (case limit 65 °C).
- Thermal performance is NEEDS-TEST (Gate G).

## DD-16 TPS552882 centre pads: bridged to edge pins instead of via-in-pad
TI recommends thermal vias in the RPM0026A centre pads (24 PGND, 25 SW2, 26 VOUT). Those pads are 0.375 mm wide,
and PCBWay requires a 0.15 mm annular ring for vias in pads. That leaves no room for a drill, so via-in-pad is
not manufacturable without HDI microvias. The land pattern places each centre pad directly beside an edge pin of
the same net (24↔9, 25↔21, 26↔11), so each pair is joined by a short bridge track: 0.25–0.30 mm wide with
≥ 0.22 mm clearance to neighbours. Vias go outside the package.
**Consequences:**
- Higher IC junction temperature than TI's EVM, and the full SW2 current passes through the pin-21/pad-25 bridge.
- This is a Gate G thermal test item.
- For production, quote HDI (laser microvia) via-in-pad as an option.

## DD-17 Variant A density measures (22 mm)
Measured courtyard occupancy with 0402 passives was 73 % (top) / 67 % (bottom), which is the practical packing
limit. The following were applied to the compact variant only, unless stated:
- 0201 for non-precision resistors and small capacitors. The FB divider stays 0402 / 0.1 %.
- Ring contact 0.8 mm wide (was 1.0).
- Spring pad Ø 5.0 mm (was 6.0).
- CS / FB / EN test pads only on the evaluation board.
- SOD-523 diodes for D2 and D3 (both variants).

No protection function was removed. Variant B keeps 0402 parts and the full set of test pads.

## DD-18 Stack-up roles and power distribution
- **F.Cu:** power pours (VBAT input, SW1, SW2, VOUT, LD+) and signals.
- **In1.Cu:** solid GND plane.
- **In2.Cu:** VBAT pour on the left (Q1 → C1–C3/Q2 current path) and a GND fill elsewhere, leaving the
  remainder of the layer free for routing. The compact variant has no In2 VBAT pour since DD-25.
- **B.Cu:** BAT_SPRING (spring → Q1), local VBAT and SW1 pours, and signals.
- **Vias:** the battery current crosses layers through automatically placed via fields; vias are never in pads.
- **Kelvin sensing:** sense nets ISP_K and ISN_K are separate nets that start at net-tie sense pads in the
  shunt footprint.

## DD-19 Segmented ring contact
The perimeter contact is 20 tangential pads per side with a stitching via in each gap, plus a continuous
solder-mask opening. A single annular pad cannot be represented in Specctra DSN: FreeRouting saw a solid GND disc
covering both outer layers and reported 182 pre-existing clearance violations. The GND pour fills the gaps
after routing, so the exposed contact ring is continuous copper.


## DD-20 DRC omissions and footprint graphics
The shared generator removes footprint silkscreen graphics for density while retaining the library copper,
mask, paste and fabrication geometry. This intentionally differs from the library footprint. The
`lib_footprint_mismatch` rule is omitted for this generated-board workflow; source footprint loading,
schematic parity and actual copper DRC remain required. Independent footprint geometry review is still
required before release; this omission does not certify an arbitrary edited footprint.

`tuning_profile_track_geometries` is also omitted: this design has no length-tuning profiles or tuned
length requirements. Other previously implicit KiCad omissions (`missing_courtyard`,
`track_not_centered_on_via`, `footprint_filters_mismatch`, `footprint_type_mismatch`) are restored as
warnings. Validation lists the two documented omissions and rejects unknown omitted rules. Copper,
clearance, routing and parity findings are not waived.

## DD-21 Ring edge margin and reproducible bottom placement
The original 10.25 mm ring centre radius with 0.80 mm-wide tangential rounded segments reaches about
10.703 mm at segment corners; allowing the 0.025 mm half-stroke of Edge.Cuts leaves only about
0.272 mm to the nominal 11 mm board radius, below the 0.30 mm design rule. Move the ring centre
radius inward to 10.20 mm while retaining its width, segment count and plated stitching holes.
These engineering geometry choices now live under `pcb` in parameters.yaml and drive the footprint
generator. KiCad DRC must verify the actual generated result.

Both variants retain fabrication-layer references; the evaluation board adds explicit probe and polarity labels from its placement source.

The placement transform now starts from the native footprint side on every call. This prevents
automatic bottom-side searches from changing orientation between a trial and final placement.
Paste-only pads do not obstruct copper fanout; trace collision checks use their source layer, while
through vias still clear copper on every layer. Real pcbnew regression checks cover these behaviors.


## DD-22 Router constraints and review-only outputs
FreeRouting's automatic neckdown and fanout stages can create tracks below the board's 0.15 mm
minimum. Disable automatic neckdown and the fanout pre-pass in new runs, reserve In1.Cu for the GND
plane, and retain the source-defined GND escapes. Restore any imported subminimum track to the
configured minimum in the finish stage, then run full KiCad DRC. Widening is a geometry repair;
its resulting clearance or connection findings remain failures, with no automatic waiver.
Explicit finishing tracks and vias are recorded as tracks_post/vias_post in placement.yaml.

Routing sessions are bound to the exact DSN and SES hashes. DRC evidence is bound to the final saved
PCB, schematic, project rules and report hashes. Export evidence includes source and artifact hashes,
required output inventory and independent BOM/centroid checks. Failed exports retain a separate draft
for inspection. A successful export check establishes internal package consistency, not Gate F release.


## DD-23 Power-layout review from the routed copper
Layout priorities (REQ-PCB-01, SLVSFC5 §10.1) are reviewed from the routed copper, not by eye.
`automation/review/power_layout.py` solves the DC current flow through every power net at the calculated
operating points, measures the guideline geometry and writes a report per variant. The validator only
checks that the report is current for the board; dispositions live in `engineering/layout-review.md`.
- **Evaluation board:** the SW1 pour now meets the Q2 source pins along their full height (1.91 → 0.98 mΩ).
  An In2 finger parallels U1's output column (VOUT 3.01 → 2.27 mΩ) and the LD_P pour is larger. These are
  source pours re-applied to the archived router session, so routing, post-route corrections and DRC are
  unchanged.
- **Not changed:** moving C7 (VCC) or C6 (BOOT2) trades one top-right-corner loop for the other because L1
  and U1 courtyards are 0.12 mm apart. Pairing U1's ISP/ISN on one layer needs a new router session for
  FB and the sense nets. Both are documented with bench checks instead.
- **Package limit (reinforces DD-16):** without via-in-pad, PGND, VOUT and SW2 each leave U1 through one
  0.25 mm pin. AGND (pin 10) sits between PGND and VOUT, so it cannot join PGND only at the VCC capacitor
  while C14 closes the boost loop. The measured consequences are a 0.75 mm SW2 equivalent width and a
  DC ground offset of +0.28 % on the current setpoint at the worst point. HDI via-in-pad remains the
  production remedy.
- **Efficiency:** routed copper adds about 96 mW over the loss model at 4.0 V (estimate 94.1 %). The
  calculation keeps its copper allowances (`model_copper_*`) rather than being silently re-based. The owner
  later accepted a ≥ 94 % target (DD-26).

## DD-24 Compact re-floorplan around the spring-pad via keep-out
The centre spring pad forbids through vias within 2.95 mm of the board centre. The previous compact draft
had U1 directly above it.
- **Power column:** L1 now covers the spring pad (its pads need no vias) and U1 is 2 mm below. Every U1
  pin has a source-defined escape. Non-crossing BOOT1/SW1 lanes go to C5, BOOT2 goes above C7 to C6, and
  VCC reaches C7 in 0.6 mm.
- **Laser pads:** this needs J3 at 3.5 mm pitch on the compact variant only. The 2.2 mm pads leave a
  1.3 mm gap for the 20 AWG leads, and the evaluation board keeps 4.0 mm.
- **Bottom power stage:** Q1 is under Q2 with an 8-via VBAT field. Q3 moved right so SW1 vias fit between
  the drains.
- **MCU block:** moved to the bottom lower left with its harness pads and enable chain (superseded by DD-25,
  which moved the MCU below C1-C3 and the enable FETs to the top right).
- **Router keep-outs:** temporary rule areas, removed at finish, protect the power pours from the
  autorouter.
- **Small-part placement:** comes from `place_opt.py`, written as explicit positions.

Result: 31 unconnected instead of 43, 0 DRC errors, and every power path connected (VBAT previously
crossed one via and VOUT was open). The variant stays a routing draft; `engineering/compact-feasibility.md`
lists the remaining work.

## DD-25 Grid router, MCU relocation and signal-only In2 on the compact board
FreeRouting stalled at about 45 open connections on the compact board. The MCU and the long cross-board
signals failed every time.
- **Grid router** (`automation/placement/grid_route.py`):
  - Routes on a 0.05 mm grid over F.Cu, In2.Cu and B.Cu with through vias, against the exact copper of the
    placed board.
  - Negotiates congestion between nets (PathFinder), and an exact segment check closes every run.
  - Writes explicit `grid_routes` copper into `placement.yaml`. The build adds it after the via fields and
    before the GND fanout, so FreeRouting treats it as fixed wiring.
  - When negotiation cannot converge, `--partial` keeps the conflict-free nets and leaves the clashing
    ones to FreeRouting.
- **No In2 VBAT pour.** The battery current runs B pour → via field → F pour; inner copper on those vias is
  only a side branch, and In2 is the one layer that can cross the board centre. One field via that
  reached only the B pour now also lands in the extended F pour.
- **MCU:** moved below C1-C3 to (-6.35, 1.2) and rotated 0°, so its blocked top edge holds the unused
  PC1-PC3, UPDI and LASER_EN, and the analog pins face the via sites below. A 0.8 mm escape ring is kept
  free of parts on both sides. The over-voltage FET block (Q6, D3, R20) joined the other EN pull-downs.
- **Placement and fanout rules:**
  - `place_opt.py` charges `side_penalty` for a net that needs a via to change side.
  - Router keep-outs are cut back around vias of other routed nets.
  - GND fanout vias stay out of other nets' source pours. One had narrowed the LD_P pour to half its
    width.

Result: 20 unconnected instead of 31, 0 errors.
- The power paths are equal or better: VOUT 1.46 mΩ, LD_P 0.47 mΩ.
- Copper loss above the model is +44 mW (was +56 mW).
- The ground-offset setpoint shift is +0.75 % (was +1.14 %).

The remaining opens are a capacity limit: via sites near the MCU (`engineering/compact-feasibility.md`).

## DD-26 Efficiency target relaxed to 94 % (owner deviation)
The brief asks for more than 95 % at 4.0 V input and 4 A output. The loss model gives 94.6 %. Substituting the
routed copper gives about 94.1 % on the evaluation board and 94.4 % on the compact board. Its largest
losses are the TPS552882's internal boost high-side switch, the input path and the 10 mΩ shunt; the shunt
sets the 5 A backup limit.

**Owner decision (2026-10-25):** accept the deviation. REQ-PWR-02 becomes ≥ 94 %
(`parameters.yaml` `current.efficiency_target_pct`), which the calculation checks. The bench measurement
(test plan T1.7) remains the evidence of record.

**Superseded 2026-10-29 by DD-37:** the target is now ≥ 93 % at 4.5 A.

## DD-27 Evaluation board first; compact board parked
The compact board ends at 20 open signal connections. The grid router and simulations show a routing-capacity
limit near the MCU, not a net-order problem: an MCU pin swap and finer inner-layer rules do not finish it
(`engineering/compact-feasibility.md`). Completing it needs HDI, a placement re-architecture or fewer parts,
each with cost or scope consequences that bench data should inform.

**Owner decision (2026-10-25):** prototype the evaluation board first; it carries the same circuit and is
complete in CAD.
- The compact board stays a routing draft, and its Gates D/E/F stay open.
- Revisit it after the evaluation prototype has produced bench data (efficiency, temperatures, waveforms).

## DD-28 Firmware supervision and measurement chain (audit 2026-10-26)
The independent audit (`reports/comprehensive-project-audit.md`, AUD-FW-01…20) found firmware defects that weakened
supervision without touching any protection threshold. The corrections keep every DD-06/DD-08 threshold, the
4.0 A setpoint and the hardware enable chain unchanged; they only add checks or make existing ones work.
- **Measurement chain.** The 2.5 V internal reference is specified for VDD ≥ 2.9 V (DS40001997C Table 37-22) and
  VMCU sits one D2 drop below VBAT. ADC0 now uses VDD as its reference for every channel and measures the 1.1 V
  reference each tick (ratiometric VBAT and current); ADC1, DAC0 and DAC2 use the 1.5 V reference. The DAC2/AC2
  reference is written to `VREF.CTRLD`; the previous code wrote it to `CTRLC`, leaving the power-loss comparator on
  the 0.55 V reset reference (trip near VBAT 0.57 V), so the short-click mode change could not work. DAC2 now runs
  in standby.
- **Sensors.** The board NTC is mandatory: open or short for 50 ms latches FAULT_SENSOR_BOARD (previously the
  limit was silently skipped). The laser NTC stays optional: open at power-up means not fitted for that session;
  a short, or a loss after being present, latches FAULT_SENSOR_LASER.
- **Supervision.** The watchdog is cleared only after a complete sample → state machine → output cycle; a watchdog
  or unexpected software reset latches FAULT_INTERNAL instead of re-arming; pending ticks are counted (an overrun
  latches a fault); the over-voltage event is latched in every state; current above 200 mA while the firmware holds
  the converter off latches FAULT_OUTPUT_WHILE_OFF; fuses are checked at start-up (FAULT_CONFIG).
- **Start voltage.** The 3.2 V resting check now runs at the end of every arming period as well as at power-up.
- **User interface.** The switch is debounced (20 ms, one press per release, 250 ms lockout, a switch held at
  power-up is ignored). Power gaps are classified after the supply has been back for 20 ms: below 30 ms a glitch
  (same mode, a latched fault is kept, because a glitch is not a deliberate power cycle), up to 0.5 s a click (next
  mode), longer a fresh start. Fault codes 1–15 blink with a 1.5 s pause.
- **Pull-ups into the converter.** The TPS552882 limits CC and PG to VCC + 0.3 V (SLVSFC5 §6.1) and VCC is off in
  shutdown. PG (never read) has no pull-up; the CC pull-up is on only while the converter runs, from its second
  enabled millisecond, and CC is evaluated from the third.
- **Structure.** `hal_avr.c` (registers only), `fw.c` (cycle and hold-up), `app.c`, `conv.c`, `holdup.c`; host tests
  cover each layer, including `hal_avr.c` against a register model, and a mutation check proves the tests catch
  each audited defect.

Bench confirmation remains Gate G: fuses (T0.4), hold-up and gap classification (T1.8/T1.9), CC polarity (T1.10),
measurement chain (T1.11) and sensor-fault response (T2.13).

## DD-29 Separate budget-driver planning scope (owner, 2026-10-28)

The owner requested a budget driver with similar specifications and no size constraint, then confirmed that
**two Li-ion cells in series are acceptable** and specified **£60 per driver**. Initial quantity was not
specified; the plan compares three and five working units. The question defining the price excluded the
laser diode and battery; additional scope assumptions are explicit in the plan.

[Budget-driver plan](budget-driver-plan.md) consolidates the pre-order audit, quote/GBP/UK sourcing reviews
and Project 450 ideas. It proposes a separate 2S synchronous buck, larger components, genuine sourcing and
independent hardware protection. TPS54821, SRP1265A-4R7M, INA300 and SOIC ATtiny1616 are a shortlist, not
owner-approved component selections. Operating range, thresholds, budget allocations and efficiency targets
are proposals pending circuit qualification and a complete quote.

The £60 ceiling is not a verified cost. Current complete delivered pricing is UNKNOWN. Compare a repriced
original evaluation-board quote before committing money to a redesign. Existing A/B sources, decisions,
review dispositions and release gates remain scoped to their existing 1S circuit. No CAD, firmware or
manufacturing change is authorised by a parts shortlist alone; adopted implementation needs a further DD,
variant-specific authoritative sources and the full regeneration/review chain. Budget requirements are
registered separately as REQ-BUD-01…09, all OPEN; no existing PASS verifies this new design.

## DD-30 Start separate budget electrical qualification (owner, 2026-10-29)

The owner instructed implementation towards prototype manufacturing and requested current Markdown/GitHub
handover at every checkpoint. This authorises development within DD-29's two-cell, unrestricted-size, £60
scope. Initial batch size remains undecided; compare three and five working units. No order is authorised.

Created independent numeric sources in `engineering/design/budget-2s/parameters.yaml`, variant source
resolution, executable electrical screens and a preliminary ngspice current-loop model. Current candidates
include TPS54821, SRP1265A-4R7M, INA186A2, INA300, a four-terminal WSK2512 shunt, separate physical UV/OV
monitoring, supervised hardware fault latch and SOIC ATtiny1616. The output disconnect and default-off
buffer are not selected or fully qualified. BUD-15…22 extend the manufacturer evidence; no price, stock,
complete BOM, fixed circuit or footprint approval is inferred.

The implementation handover and issue register are [budget-2s-design.md](budget-2s-design.md). Calculated
current/trip windows remain conditional on procurement and thermal assumptions. Loss screens expose risk
to the proposed 94% target; the proposed UV cutoff conflicts with guaranteed 6.0 V operation. A 180 Ω
compensation candidate passes the preliminary 243-case sensitivity screen after a 330 Ω candidate failed
19 cases. This is an assumed incremental model, not a switching/fault or bench qualification.

Keep budget circuit connectivity and layout pending resolution of the power, UV, default-off and
fault-energy issues. Then create its separate connectivity/placement/library sources and extend every
affected generator, firmware profile, review and release gate. Do not modify the original A/B electrical
sources or inherit their PASS results. All nine budget requirements and physical qualification remain
OPEN; the new tools report unresolved prerequisites explicitly. Commit each milestone with PROGRESS and
actual checks, then push `main` so another agent can continue from GitHub.

## DD-31 Budget output disconnect, UV backstop and operating-point model (engineering, 2026-10-29)

Engineering choice by Claude Code (AI agent) within the DD-30 development authority; the owner may override.
It addresses BUD-ISS-01/02 of [budget-2s-design.md](budget-2s-design.md). Generated numbers are in
`reports/budget-2s/qualification.md`.

**One output P-FET instead of a back-to-back pair.** With its source at VBUCK, the P-FET's body diode
(drain → source) already blocks VBUCK → laser when the gate is released. The second FET of a common-source
pair only blocks laser → VBUCK, a path a passive diode load cannot drive. It adds no forward-blocking
redundancy either: if the forward-blocking FET fails short, the other FET's body diode conducts forward. The
pair therefore doubled disconnect loss without adding protection. A shorted output FET remains a single fault
handled by the buck EN path, the independent OC latch and the fuse. It is not handled by a second FET.

**DMP2005UFG-7 selected for development** (BUD-16). It loses less than DMP2022LSS-13 at every generated
operating point. Its ±10 V gate rating exceeds the 8.4 V buck-switch-short fault, but a gate clamp for plug and
switching transients is still to be designed. Its exposed-drain land, paste and X-ray inspection need the same
review as U1's exposed pad. The reverse-input FET stays DMP2022LSS-13 (±12 V gate).

**UV divider 147 kΩ → 130 kΩ.** The hardware UV comparator becomes a backstop below the loaded 6.0 V operating
floor (falling window about 5.40–5.62 V, i.e. 2.70–2.81 V per cell). The normal stop is a firmware policy that
is still to be written. It must stop emission before dropout and refuse arming on a low resting pack. The
`pack_cutoff_floor_v` assumption needs cells rated for a 2.5 V/cell discharge cutoff. The exact pack and
BMS remain REQ-BUD-05.

**Operating-point model** (`automation/budget/power.py`) replaces the resistance-only screen. It solves the
averaged steady state with energy balance, using datasheet limits, labelled efficiency `estimates` and
`power_model` allocations. The allocations are limits the BOM and layout must meet: 15 mΩ connector + fuse +
input copper, 3 mΩ output copper. TPS54821 specifies a 0 ns minimum off-time (BOOT-PH ≥ 3 V), so dropout is
set by series resistance, not a duty limit. Results: regulation at 5.2 V / maximum setpoint down to about
5.78 V input at the maximum-resistance corner; UV and OVP margins each about 0.21 V. Its converter terms agree
with TI's typical curve to about half a point (slightly pessimistic).

**Finding for the owner: the 94% target is not met by estimate.** At 7.4 V input, 4.5 V diode, 4 A and the
typical corner, the estimate is about 93.4%. The comparable A/B definition (REQ-PWR-02) is typical diode,
including the shunt. The gap is the system losses that the converter curve leaves out: shunt, protection FETs,
input path and control load. No REQ-BUD-07 change is made. The owner chooses:
(a) accept a lower budget target at 7.4 V / typical diode / 4 A, judged by bench measurement; or
(b) keep 94% and change the architecture (e.g. an external-FET controller or lower-resistance converter, at
added cost and complexity). The 10 mΩ shunt sets the backup-trip accuracy and should not be reduced alone.
Recommendation: (a). About 0.1 W of extra loss is thermally negligible on an unrestricted board and costs well
under 1% of runtime.

**Owner decision (2026-10-29): option (a).** The budget target becomes ≥ 93% at 7.4 V input, typical diode
(4.5 V point) and 4 A, judged by bench measurement (`targets.efficiency_fraction`). The 93% value was proposed by
Claude Code because the owner chose (a) without a figure; the owner may change it. All corners stay reported.
The estimate's margin is small (about 0.4 points at the typical corner; the maximum-resistance corner is near
90.6%), so a prototype built with near-maximum parts may measure below target.

## DD-32 Budget default-off interface (engineering, 2026-10-29)

Engineering proposal by Claude Code within DD-30; it addresses BUD-ISS-03 of [budget-2s-design.md](budget-2s-design.md).
Margins are generated in `reports/budget-2s/qualification.md` by `automation/budget/interface.py`.

**Problem.** The SN74HCS74 latch guarantees its output levels only at |IO| ≤ 20 µA and is specified only for
VCC ≥ 2 V. TPS54821 EN has an internal pull-up whose current is given only as typical (an open EN enables
the converter). Driving EN and the output-FET driver from the latch alone would make default-off depend on an
unspecified supply window, a typical-only current and the latch never sticking high.

**Interface.**
- **nFAULT** is the wired-AND fault line and the latch CLR. Its sources are the TLV803 reset, TLV6700 UV/OV,
  INA300 alert and N5. It is pulled up from VCTRL through the external interlock loop, split 1.0 kΩ / 9.1 kΩ
  around the connector, with a 47 kΩ pulldown, so an open loop is a fault.
- **Latch:** D and PRE are tied high. The MCU's arm edge drives CLK, and Q (ARM_Q) feeds only two 10 kΩ /
  1 MΩ gate networks.
- **Output disconnect:** N1 (gate ARM_Q) in series with N2 (gate nFAULT) pulls the output P-FET gate against
  its 2.2 kΩ pull-up to VBUCK.
- **Buck enable:** N3 (ARM_Q) in series with N4 (nFAULT) pulls the gate of P1 (DMG1013T-7, source at VCTRL,
  10 kΩ gate pull-up). P1 drives EN through 10 kΩ, with 10 kΩ from EN to ground. The pulldown tolerates
  roughly 87× the typical EN pull-up. EN can never exceed half of VCTRL plus a small pull-up drop, so it stays
  below the guaranteed disable level while VCTRL < 1.7 V, the lowest supply at which the supervisor output is specified. This holds
  whatever state the logic is in.
- **N5** (firmware permit) holds nFAULT low through a 100 kΩ gate pull-up. The MCU must drive its pin low to
  permit emission, so MCU reset, a tristated pin or a watchdog reset clears the latch. Re-arming then needs a
  new arm edge.
- **Parts and bleed:** N1–N5 are DMG1012T-7 (RDS specified at 1.8 V). A 15 kΩ VCTRL bleed bounds back-powering.

Every asserted fault turns both outputs off through the series pairs, independent of the latch. A latch stuck
high leaves fault, interlock and firmware-inhibit shutdown intact; only arming loses its second condition. The
34 static checks pass, conditional on these assumptions:
- latch thresholds interpolated between TI's 2 V and 4.5 V rows;
- open-drain VOL/VOH scaled linearly from their test currents;
- leakage allocations covering 25 °C datasheet maxima;
- typical-only EN pull-up and MCU pin leakage;
- allocations for the interlock loop and back-power injection.

The smallest voltage margin is the supervisor release threshold against the conservative rail screen (about
13 mV beyond its 30 mV allocation). Timing, fault energy, single and latent faults (a power-on self-test of the
series pairs) and interlock cable faults remain BUD-SAFE-01 / BUD-ISS-04.

## DD-33 Budget main setpoint 4.5 A and owner V–I points (owner, 2026-10-29)

**Owner instruction.** The owner accepted the DD-31/32 targets and set the budget driver's main target to
**4.5 A at 4.72 V**, which the owner expects to give about 7.3 W optical. The owner supplied these NUBM44
operating points: 3.0 A at 4.40 V, 3.5 A at 4.52 V, 4.0 A at 4.62 V, 4.5 A at 4.72 V (OWNER-VI-01). This
applies to budget-2s only. The A/B boards keep 4.0 A (DD-13) unless the owner extends the decision to them.

**Diode-rating risk.** 4.5 A is above the 4.2 A maximum operating current given by LD-05, the only (secondary)
source for that limit, and 50% above the 3.0 A typical current. About 7 W optical exceeds LD-05's 6.0 W
absolute-maximum optical output. Community measurements are consistent with the owner's points: about 4.7 V
and 6.8–7.5 W at 4.5 A (LD-13, LD-14, LD-27). As with DD-13, this is recorded as an owner-accepted
diode-life risk. The diode must shed roughly 14 W of heat at 4.5 A, so its heatsink sizing matters more
than at 4.0 A.

**Implementation (engineering, Claude Code).**
- Feedback divider top 23.2 kΩ → 27.4 kΩ (E96), giving 4.488 A nominal.
- Normal transient ceiling 4.4 A → 4.95 A, keeping the 1.1× ratio of REQ-OUT-05.
- INA300 limit resistor 2.52 kΩ → 2.67 kΩ (E96), giving about 5.29 A nominal inside a 5.0–5.6 A trip window.
  The trip window must stay above the transient ceiling; the tools now refuse any other ordering.
- Efficiency condition becomes 7.4 V / 4.5 A / 4.72 V. The 93% target (DD-31) is kept.
- The other owner points are one-resistor builds (15.0 k, 19.1 k, 23.2 k). The backup trip stays sized for
  4.5 A, so it guards lower builds less closely; retune the limit resistor too if one becomes the default.

**Results (generated).** The setpoint envelope stays within ±5% for every owner point. Dropout at
5.2 V / maximum setpoint is about 5.86 V (0.14 V margin). UV and OVP margins are about 0.19 and 0.18 V.
The loop study still passes all 243 cases. The efficiency estimate at the main point is about 93.05%: it
meets 93% by only about 0.05 points, while the maximum-resistance corner is about 90%. A bench measurement
below 93% at 4.5 A is plausible. If that happens, the owner chooses between accepting it, running a lower
setpoint, or reducing losses (input path, switching frequency, converter).

## DD-34 Budget sourcing directive and part swaps (owner + engineering, 2026-10-29)

**Owner instruction.** Design the budget board around easy-to-source, cheap parts that are readily available in
the UK or from AliExpress with fast shipping.

**Policy (proposed by Claude Code; owner may adjust).**
- Every BOM line needs a current offer from a UK-serving distributor (DigiKey UK, Mouser UK, Farnell/CPC, RS,
  TME) or a fast China channel.
- For semiconductors where precision or safety matters, the China channel is LCSC (a genuine distributor,
  also JLCPCB's assembly stock), not AliExpress marketplace sellers. Counterfeit TI analog parts are common
  there, and no AliExpress listing was found for the TI parts searched.
- Passives, connectors and fuses may come from AliExpress.
- Prefer parts with stock KiCad footprints.
- Prices and stock stay UNKNOWN until a dated offer is fetched; search snapshots (BUD-25) only steer choices.

**Swaps.**
- DMP2005UFG-7 (DD-31) is dropped: DigiKey lists it as not normally stocked with a 40-week lead time. The output
  disconnect becomes **SiSS23DN-T1-GE3**. That is the A/B board's Q1 part, UK stocked, with a stock KiCad
  footprint, and its resistance matches (4.5/6.3 mΩ max at −4.5/−2.5 V). Its ±8 V gate needs protection
  against the 8.4 V switch-short case:
  - a 100 Ω series resistor to the N1/N2 pull-down;
  - a BZX585-C6V2 zener from source to gate (VZ 5.89–6.51 V, already sourced for A/B).

  |Vgs| is then about 0.957 × VBUCK, which keeps the −4.5 V resistance figure at the main point. A 470 Ω
  resistor would cut the efficiency estimate below 93%, and a test now catches that.
- WSK2512R0100FEA (four-terminal) is replaced by **WSL2512R0100FEA** (LCSC C844901; Vishay doc 30100, BUD-24):
  1 W, ±1%, ±75 ppm/°C, on the stock 2512 land with Kelvin traces from the pad edges. Every setpoint option
  stays within ±5%.

**Results (generated).**
- Efficiency estimate 93.05% at the main point (unchanged).
- Dropout margin 0.14 V; OVP margin 0.18 V.
- 37/37 interface checks, including the clamp-off and clamped-fault gate checks.

**Still to verify:**
- TPS54821RHLT/R: LCSC stock, 12-week DigiKey lead time, and no stock KiCad footprint for its 14-pin RHL
  package, so it needs a project footprint and review. Nothing ubiquitous on AliExpress meets 93% efficiency
  with near-100% duty: the common XL4016/LM2596-class modules are asynchronous.
- SRP1265A: no stock KiCad footprint.
- INA300, SN74HCS74 (TI showed it out of stock), DMG1012T/1013T and DMP2022LSS: UK stock unverified.

## DD-35 Budget KiCad schematic started (engineering, 2026-10-29)

Owner instruction: start getting the budget board out with KiCad. Engineering choices by Claude Code; the owner may
change any of them.

**Tooling (separate from A/B).**
- `engineering/design/budget-2s/connectivity.yaml` is the budget's connectivity source.
- `hardware/budget-2s/lib` holds the `budget2s` library (YAML symbols, plus MOSFET symbols renumbered for SOT-523,
  SO-8 and PowerPAK 1212).
- `automation/budget/build_schematic.py` reuses the A/B block-layout and labelling helpers unchanged. It wraps
  wide blocks into rows of four multi-pin parts, and writes its own project, ERC, netlist comparison and hash
  manifest.
- `nubm44.kicad_lib` gained a `budget2s` library location. No A/B evidence hashes that module, and the A/B library
  and builders are untouched.

**Schematic content.**
- **Connectors and fuse:** XT30 PCB male battery input (AMASS XT30PW-M); 10 A mini-blade fuse in a Keystone 3568
  holder (car-accessory fuses are easy to buy in the UK); MaiXu MX126 5 mm screw terminal for the laser; JST-PH
  for the interlock and laser NTC; 3-pin UPDI header.
- **Clamps:** reverse FET Q1 gets a BZX585-C10 gate clamp; a bidirectional 10 V TVS sits on VBAT_P.
- **Output capacitors:** six 22 µF 16 V 1206.
- **ADC dividers:** the pack and VBUCK monitors use 1 MΩ / 270 kΩ with 100 nF, so their worst-case back-power
  injection (about 2 × 8.4 µA) fits the 20 µA DD-32 allocation.
- **MCU pins:**

  | Function | Pin |
  |---|---|
  | Permit (N5 gate) | PA1 |
  | Arm clock | PC0 |
  | nFAULT monitor | PB1 |
  | PWRGD | PB0 |
  | Interlock state | PA2 |
  | Button | PA3 |
  | LED | PB2 |
  | NTC excitation | PA4 |
  | Board NTC | PA5 |
  | Laser NTC | PB4 |
  | Current | PA6 |
  | VBUCK | PA7 |
  | Pack | PB5 |
  | Spare | PB3, PC1–PC3 |

**Result (generated).** ERC 0 errors and 2 warnings, both for the not-yet-generated footprints. The netlist matches
the connectivity exactly: 104 parts, 56 nets. `qualify.py` reports this in BUD-CAD-01, which stays OPEN.

**OPEN.**
- Project footprints for the TPS54821 RHL VQFN-14 (from TI's drawing, with a footprint review) and the SRP1265A
  (check the Bourns land against KiCad's SRP1245A).
- XT30 pad-to-polarity mapping and B+/B− silkscreen.
- Sourced MPNs for generic passives, TVS, fuse and LED.
- Whether any other pin injects into an unpowered VCTRL (TLV6700/INA inputs).
- Placement, PCB, DRC, layout review and the firmware pin profile.

## DD-36 A/B boards at 4.5 A (owner, 2026-10-29)

**Owner instruction.** Change the original boards to 4.5 A as well, matching DD-33. Two calculation margins failed
at 4.5 A. The owner accepted both recommended dispositions ("Accept a and b"):

- **(a) Backup current limit.** The TPS552882's ISP/ISN limit is fixed at 48–52 mV, which is 4.8–5.2 A with the
  10 mΩ MCS1632 shunt (the series has no lower value in that land). The no-interference check now uses
  `current.backup_margin_factor: 1.0` (was 1.05): the backup only has to clear the worst-case setpoint
  (4.66 A). It becomes a close, slow average-current clamp that trims transients above about 4.8 A.
- **(b) Reverse-FET dissipation.** Q1 (SiSS23DN) dissipates 0.68 W at the worst point. The limit becomes
  `components.q_reverse.p_max_w: 0.7` (was a 0.6 W estimate, about 40 K rise at ~60 K/W). The bench thermal
  test decides.

**Engineering changes (Claude Code).**
- R8 6.65k → **8.66k** (RT0402BRD078K66L, 4.478 A nominal, −0.48%).
- R3 27.4k → **24.9k** (RC0201FR-0724K9L / RC0402FR-0724K9L), giving ILIM 13.25 A typical, which fixes the
  inductor-current margin.
- Firmware `APP_I_SET_MA` 4000 → 4500 (±15% regulation window) and its host tests.
- Simulation criteria now read the setpoint from parameters (REQ-OUT-05 peak = 1.1 × setpoint) instead of
  literal 4.0/4.4 A.
- Bench criteria are now 4.275–4.725 A regulation, ≤ 4.95 A peak and a 4.5 A thermal test.
- The PCB `finish` stage now syncs schematic values and fields onto placed footprints. The archived router
  sessions were restored and re-finished, and `source_revisions` entries were appended. A KiCad-Python comparison
  of the evaluation board with the previous commit found all 490 tracks/vias and 186 pads identical; only the R3/R8
  values changed. Pours were re-filled (largest fill-area change 0.05%, on SW2), so the copper Gerbers differ in
  item order and fill detail only.

**Results (generated).**
- Calculations 21/21 PASS.
- Simulations 12/12 PASS. SIM-12 now passes 11/11 (minimum PM 106°), so AUD-SIM-04 / VAL-SIM-12 is resolved:
  the lower loop gain fixed it.
- Firmware host tests, target build and mutation check PASS.
- ERC 0/0 and exact netlists. Evaluation DRC 0/0/0/0; compact DRC is the unchanged parked state.
- PCBWay/JLCPCB packages regenerated.
- Full validator exit 0, with only the 2 accepted compact items left; evaluation readiness is back to its 2
  footprint-review blockers.

**Finding for the owner.** The evaluation board's routed-copper efficiency estimate at 4.0 V input is **93.56%**,
below the 94% target (DD-26/REQ-PWR-02). The loss model alone gives 94.10%. The owner chooses: accept a lower A/B
target (as for the budget board) or wait for the bench measurement (T1.7).

**Diode risk.** Same as DD-33: 4.5 A exceeds LD-05's 4.2 A maximum operating current; risk R-01 is raised.
Lower-current builds (R8 2.49/4.53/6.65 kΩ) raise the loop gain, so rerun SIM-12 before fitting one.

## DD-37 A/B efficiency target 93 % at 4.5 A (owner, 2026-10-29)

At 4.5 A (DD-36) the loss model gives 94.10 % at 4.0 V input. With the evaluation board's routed copper (switch-node
copper the model omits), the estimate is 93.56 %, below the 94 % DD-26 target. The owner chose to **accept a lower
target**. REQ-PWR-02 becomes **≥ 93 % at 4.0 V input and 4.5 A, judged by bench measurement (T1.7)**, the same
figure as the budget board (DD-31). The 93 % value follows the budget precedent. `current.efficiency_target_pct`,
the T1.7 bench limit and the requirement text were changed; the 3.0 V target (≥ 86 %, REQ-PWR-03) is unchanged.
The routed estimate keeps 0.56 points of margin; the bench result decides.

## DD-38 Budget PCB and prototype manufacturing package (engineering, 2026-10-29)

Owner instruction: "Do everything on your own to complete the budget board ready for fabrication". The engineering
choices below are Claude Code's (AI); the owner may change any of them. No order is placed, and Gate G stays open.

**Board.** 90 × 60 mm, 4 layers, 1.6 mm, 1 oz on all layers, four M3 holes, all parts on the top side.
- **Layers:** In1 is a solid GND plane; In2 and B.Cu are GND pours carrying a few signal tracks.
- **Rules:** 0.15 mm clearance on all net classes; tracks 0.3 mm (Power), 0.25 mm (Ground), 0.15 mm (Sense).
- **Power path:** F.Cu pours: XT30 → fuse holder → reverse FET Q1 → C2/C3 and U1 → L1 → output capacitors →
  RS1 → Q2 → J2. The LASER_P strip from Q2 to J2 is repeated on In2 and B.Cu and stitched with six vias.
- **Router protection:** rule areas keep the router off every power pour, the VBUCK neck to RS1 and the area
  under L1's body.
- **Silkscreen:** B+/B− beside the XT30 pads, LD+/LD−, INTLK, UPDI, MODE, LD NTC, FUSE 10A and a
  "CLASS 4 LASER – DUMMY LOAD FIRST" legend.

**Footprints.**
- **U1 (TPS54821, RHL0014A):** project footprint from TI drawing 4228405/A (SLVSB14B pp.39–41). Five 0.3/0.6 mm
  thermal vias at TI's positions (TI shows 0.2 mm drills), connected solid to every pour and tented on the bottom.
  TI's 0.92 mm corner paste squares would overlap our larger drills, so they are 0.82 mm squares at ±0.61 mm,
  0.2 mm clear of every via (about 64 % of TI's corner area). KiCad types the part through-hole because of the
  plated vias; the export lists only parts with masked plated leads as hand-soldered.
- **L1 (SRP1265A):** stock `Inductor_SMD:L_Bourns_SRP1245A`; the land is identical.
- **J2:** symbol changed to `Connector:Screw_Terminal_01x02`. The generic connector's footprint filter did not
  match the terminal block, which caused a DRC parity warning.
- **J1 (XT30):** pins swapped to 1 = GND, 2 = VBAT_IN, because KiCad's footprint marks "+" beside pad 2. The
  AMASS scan (BUD-26) shows no marks, so check the moulding against the silkscreen before first power. Q1
  blocks a reversed pack.

**Layout choices.**
- **Kelvin sensing:** separate trace pairs run from RS1's inner pad edges to U2 (INA186) and U3 (INA300). U2's
  VBUCK leg crosses on B.Cu so that U2's supply and ground pins are not enclosed.
- **Q2 gate network:** R8 (pull-up) and D3 (clamp) tie into the VSH pour, so their about 2 mA does not flow in
  a Kelvin trace.
- **Input loop:** C2/C3 GND pads reach U1's GND pins 2–3 and exposed pad through 1.0 mm and 0.4 mm tracks, not
  pour spokes. A solid same-net pour was tried first; it produced 0.10 mm connection necks against the main GND
  pour.
- **U1 cluster:** the feedback, compensation and soft-start parts (R5, R6, R3, C8, C9, C6) are hand-placed
  under U1 with fixed short tracks. EN, CS_OUT and PWRGD escape through their own vias.
- **OV divider:** the top resistor R16 sits at U5, so only the low-impedance VBUCK end runs far.

**Builder workaround.** In KiCad 10.0.6, garbage-collecting the proxies of removed silkscreen items breaks the
SWIG type table after `SetFPID`. `automation/budget/pcb_builder_budget.py` runs the unchanged shared builder
with the proxies kept alive. The A/B builders are not edited.

**Routing reproducibility.** KiCad's Specctra export orders pours and keep-outs by UUID, so every `place` gives
FreeRouting a different order and a different result. The accepted session is archived in
`hardware/budget-2s/routing/` with source hashes, and `build_pcb.py --stage restore` re-applies it without
re-routing.

**Results (generated).**
- **Schematic:** ERC 0/0, 108 parts, 56 nets, exact netlist.
- **DRC:** 0 errors, 0 warnings, 0 unconnected, 0 parity, with all severities and schematic parity on.
- **Copper check:** new `automation/budget/layout_review.py`, which reuses the A/B extractor and DC solver.
  - Output loop: 2.84 mΩ hot against the 3 mΩ `output_copper_ohm_allocation`. With LASER_P on F.Cu only it
    was 4.29 mΩ, so the extra layers were added.
  - Input copper: 2.29 mΩ hot. Adding the two XT30 contacts (1.6 mΩ) leaves 11.1 mΩ hot for the fuse and
    holder within the 15 mΩ input allocation.
  - Neck: the PH neck at U1's pins is flagged for review (0.90 mm equivalent width against a 1.58 mm
    long-trace screen). Widening it made FreeRouting fail VCTRL, so it was left.
- **Package:** `manufacturing/budget-2s/` holds the Gerber/drill ZIP, a BOM of 61 lines / 99 parts (40 lines to
  select at order, MPN UNKNOWN with the requirement stated), a CPL of 99 placements, PDFs, renders and
  `ORDERING.md`. BOM lines without an MPN are grouped by value, footprint, symbol and stated tolerance, TCR,
  rating and dielectric, so 0.1 % and 1 % parts are never merged.
- **Qualification:** `qualify.py` reports BUD-CAD-01 and BUD-MFG-01 CONDITIONAL from the hash-checked DRC and
  export evidence.

**OPEN.**
- **Reviews:** U1 land and stencil; Q2 PowerPAK land (shared FP-POWERPAK); XT30 marks; J2 wire-entry side.
- **Margins:** the output-copper margin is only about 0.16 mΩ. The fuse and holder must be at most 11.1 mΩ hot
  (resistance UNKNOWN).
- **Purchasing:** the 40 BOM selections, with genuine 0.1 % / 25 ppm divider resistors.
- **Firmware:** the budget pin profile.
- **Analysis:** BUD-ISS-04 fault timing and energy.
- **Ordering:** assembly quote and DFM.
- **Gate G:** dummy-load bench data.

## DD-39 Budget BOM sourced: part numbers for the 40 open lines (engineering, 2026-10-29)

Owner request: "Find 40 open BOM lines for me." The selections below are Claude Code's (AI); the owner may
change any of them. Every MPN was checked against a distributor or manufacturer listing (BUD-27 pages read
directly, BUD-28 search snapshots). `engineering/design/budget-2s/connectivity.yaml` holds the MPNs, and
`engineering/design/budget-2s/sourcing.yaml` the order codes and evidence. Stock and prices are not used for
costing and stay UNKNOWN until quoted.

**Policy.**
- Cheap genuine parts that LCSC/JLCPCB stock (JLC Basic where available), so an assembled build avoids
  extended-part fees.
- Precision parts from UK distributors (RS, Farnell, DigiKey UK), where LCSC's 0.1 % stock is unreliable.
- One part number per value wherever ratings allow. A higher voltage rating than stated (for example 50 V
  where 25 V or 16 V was asked) meets the requirement.

**Selections.**
- **1 % resistors:** UNI-ROYAL 0603WAF series (±1 %, 100 mW, ±100 ppm/°C), 0805W8F1001T5E for R4 (125 mW),
  and Yageo RC0603FR-079K1L for 9.1 k (no UNI-ROYAL listing found).
- **0.1 % / ≤ 25 ppm/°C resistors:**
  - R5 27.4 k: Panasonic ERA-3AEB2742V.
  - R6/R15/R17 10.0 k: ERA-3AEB103V.
  - R14 130 k: ERA-3AEB134V.
  - R16 133 k: Yageo RT0603BRD07133KL.
  - R7 2.67 k: Vishay TNPW06032K67BEEA; alternate ERA-3AEB2671V.
  - Yageo RT…BRE parts are ±50 ppm/°C and were rejected.
- **Capacitors:**
  - 100 nF ×14: Yageo CC0603KRX7R9BB104 (50 V X7R).
  - 10 nF: FH 0603B103K500NT. 22 nF: Samsung CL10B223KB8NNNC.
  - 1 nF and 4.7 nF C0G: FH 0603CG102J500NT and Yageo CC0603JRNPO9BN472.
  - 1 µF: Samsung CL10A105KB8NNNC (50 V X5R), and CL10B105KA8NNNC (X7R) for the compensation capacitor C8.
  - 4.7 µF: Samsung CL10A475KO8NNNC (16 V).
  - 22 µF ×8: Samsung CL31A226KAHNNNE (25 V X5R), also for the six output capacitors. The higher rating loses
    less capacitance under bias, and the 16 V minimum and the 50–220 µF loop-model range still hold; effective C
    is still to be measured.
- **C1:** Nippon Chemi-Con EMVL160ARA101MF80G, 100 µF 16 V, 6.3 × 7.7 mm aluminium electrolytic. Its ESR helps
  damp the input cable; it matches the CP_Elec_6.3x7.7 land.
- **D2:** Littelfuse SMAJ10CA. 10 V standoff above the 8.4 V pack, 17 V clamp. The tightest limit on the
  protected rail is the MCP1703A's +18 V (BUD-21 p.3), not the TPS54821's 20 V (BUD-01 p.4), so the clamp
  margin is about 1 V at full rated pulse.
- **TH1:** Murata NCP18XH103F03RB, 10 kΩ ±1 %, B25/50 3380 K ±1 %. Firmware must use this B value. DigiKey marks
  the part Not For New Designs; LCSC stock is large.
- **D4:** KENTO KT-0805Y (yellow, VF 1.8–2.4 V, about 0.9–1.5 mA through R36 from 3.3 V). The green KT-0805G
  (VF up to 3.1 V) would be too dim.
- **SW1:** E-Switch TL3342F160QG/TR. The non-/TR order code shows obsolete/no stock.
- **J4:** BOOMELE 2.54-1*3P header.

**Design change: R16 134 k → 133 k.** 134 k is neither an E96 nor an E192 value, so it cannot be bought as a
0.1 % part. `qualify.py` was run with both neighbours:
- 133 k: OV trip 5.6437–5.7967 V; 0.136 V margin over the highest normal VBUCK (0.10 V required); Q2 |Vgs| at OV
  maximum 5.545 V against the 5.89 V clamp minimum.
- 137 k: passes too, but raises the trip to 5.80–5.96 V, which protects the laser less.

133 k is chosen and `voltage_monitor.ov_top_ohm` changed with it. The procurement fields `fb_resistor_mpns`,
`backup.resistor_mpn` and `output_energy.bulk_cap_mpn` now name the chosen parts.

**Tooling.**
- `export.py` reads `sourcing.yaml` (LCSC and UK-distributor columns), so no code is guessed into a BOM. It
  lists the 21 lines without an LCSC code: the earlier ICs, transistors, connectors, inductor and four of the
  precision resistors. These are matched by MPN in the assembler's tool, consigned, or fitted by hand.
- The routing checkpoint now hashes only the routing-relevant connectivity (refs, footprints, pin nets), so an
  MPN or value edit no longer forces re-routing. The board was rebuilt from the archived session with
  `--stage restore`.

**Results (generated).**
- ERC 0/0 with an exact netlist. DRC 0/0/0/0 after `restore`.
- Copper check unchanged: 2.836 mΩ hot output loop; 11.1 mΩ fuse budget.
- Export: "every BOM line has a sourced MPN"; 55 lines / 99 parts; 0 to select; 21 without an LCSC code.
- BUD-OV-01 margin 0.136 V. Loop model 243/243.

**OPEN.**
- Live stock and landed GBP quotes.
- The fuse and holder resistance against the 11.1 mΩ budget.
- The thermistor's B value in firmware.
- LCSC codes for the 21 lines if JLCPCB assembly is used.
- Effective output capacitance under bias.
