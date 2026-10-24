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
- Supplied from VBAT through a BAT54WS Schottky into 10 µF. While the MCU sleeps, this hold-up keeps RAM and the
  RTC alive through short power interruptions, which is how a clicky tail switch changes mode.
- Pin map (verified against Table 5-1 of the datasheet):

| Pin | Port | Function |
|---|---|---|
| 19 | PA0 | UPDI programming |
| 20 | PA1 | LASER_EN_N (low = enable) |
| 1 | PA2 | INTLK_N sense through 47 kΩ (async pin) |
| 2 | PA3 | SW e-switch |
| 5 | PA4 | NTC_PWR: bias supply for both NTC dividers, on only while measuring |
| 6 | PA5 | NTC board (ADC0 AIN5) |
| 7 | PA6 | CS_OUT current monitor (ADC1 AIN2, AC1 AINP1) |
| 8 | PA7 | VOUT_SENSE (ADC1 AIN3, AC0 AINP0) |
| 9 | PB5 | VBAT_SENSE (ADC0 AIN8, AC2 AINP2: instant power-loss detection) |
| 14 | PB0 | PG (TPS552882 power good; internal pull-up) |
| 13 | PB1 | CC (TPS552882 backup limit active; internal pull-up) |
| 12 | PB2 | IND indicator output (TCA0 WO2) |
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
"cathode/anode". This is about 90 % confidence from host conventions; owner confirmation is required.
Gate F release is blocked until then. Reverse-polarity protection limits a wrong guess to "does not work".

## DD-13 Laser current setpoint
The default build is 4.0 A as specified. 4.0 A exceeds the NUBM44's typical 3.0 A operating current, and most
units exceed the 6.0 W optical maximum there. 3.5 A and 3.0 A builds need only R_FB_TOP changed.
Recommendation to the owner: consider 3.5 A for diode life.

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
  remainder of the layer free for routing.
- **B.Cu:** BAT_SPRING (spring → Q1), local VBAT and SW1 pours, and signals.
- **Vias:** the battery current crosses layers through automatically placed via fields; vias are never in pads.
- **Kelvin sensing:** sense nets ISP_K and ISN_K are separate nets that start at net-tie sense pads in the
  shunt footprint.

## DD-19 Segmented ring contact
The perimeter contact is 20 tangential pads per side with a stitching via in each gap, plus a continuous
solder-mask opening. A single annular pad cannot be represented in Specctra DSN: FreeRouting saw a solid GND disc
covering both outer layers and reported 182 pre-existing clearance violations. The GND pour fills the gaps
after routing, so the exposed contact ring is continuous copper.
