# Audit of the previous (conceptual) design

The previous files are not on this machine (`references/previous-design/README.md`). This audit covers the
concept as described in the project brief. Source IDs refer to `research/sources/*.md`.

## Summary

Every specific component proposed for the earlier concept fails a datasheet limit for this application. The
concept also had no current-control loop definition, no output disconnect, and a contradictory battery
polarity. None of it is carried forward.

## Component audit

| Item | Earlier proposal | Problem (datasheet numbers) | Source | Verdict | Replacement |
|---|---|---|---|---|---|
| Converter | XL6009 async boost | Input range **5–32 V**: not specified for a 2.8–4.2 V Li-ion cell. Switch current **4 A typ** vs ≈ 9 A peak needed. Switch 110–120 mΩ (≈ 3.3 W conduction at 3 V/4 A). External Schottky (≈ 1.6 W). Package **TO-263-5L** (≈ 10 × 15 mm) cannot fit a 22 mm board. | PWR-17 | **Reject** | TPS552882 buck-boost (see `research/architecture-comparison.md`) |
| Current shunt | 0.15 Ω, 0.5 W | P = I²R = 4² × 0.15 = **2.4 W**, 4.8× the rating. 0.6 V drop wastes 12 % of output power, so both efficiency targets fail on this alone. | brief, CMP research | **Reject** | 10 mΩ 1 W 1206 (MCS1632R010FER), 0.16 W at 4 A |
| Feedback amplifier | LM358 | Offset 7 mV max (3 mV A/B grade) = 17–35 % of a 20–40 mV shunt signal. Input common mode only to V+ − 1.5 V, so it cannot sense at the high side (4.3–5.2 V). Minimum supply 3 V, above the 2.8 V cell floor. | CMP-xx (LM358 datasheet) | **Reject** | INA186A2 zero-drift CSA (±50 µV, CM to 40 V, 1.7 V supply) |
| Feedback network | LM358 into FB plus a diode into the FB node | Never defined: polarity, gain, compensation, start-up behaviour and accuracy were unspecified. A diode OR into FB has a soft knee and −2 mV/K drift that disturb the current setpoint unless the clamp sits far above normal output. | brief; analysis in `engineering/design-decisions.md` DD-05 | **Reject** | CSA output → precision divider → FB, Type II compensation verified over 12 corners. No diode on FB. Open-load handled by a separate trip path. |
| MCU | ATtiny13 | Usable supply range, but no DAC or analog-comparator reference choice for fast hardware-assisted trips, and 6 programming pads (ISP). The 3 × 3 VDFN variant has negligible stock (7 pcs at LCSC). | CMP-35, CMP research | **Replace** | ATtiny1616 VQFN-20 3 × 3 mm: 2 ADCs, 3 comparators, DAC, 1-wire UPDI |
| Switching MOSFET | AO3400A (SOT-23) | 32 mΩ at 4.5 V, 48 mΩ at 2.5 V; rated 5.7 A against a 7.6–8.9 A input current. ≈ 0.87 W in SOT-23 gives a ~110 °C junction rise. | CMP-xx (AO3400A) | **Reject** for power path | Not needed: switches are integrated or SiSS80DN (1.15 mΩ). AO3400A-class parts are fine only as gate drivers. |
| Reverse-polarity MOSFET | AO4407A (SOIC-8, P-ch) | Vgs(th) up to −3.0 V and Rds(on) only specified at Vgs ≤ −6 V; it cannot be fully enhanced by a 2.8–4.2 V cell. SOIC-8 is also large. | CMP-xx (AO4407A) | **Reject** | SiSS23DN: 4.5/6.3 mΩ max at −4.5/−2.5 V, 3.3 × 3.3 mm |
| Boost inductor | 10 µH | A 4 × 4 mm 10 µH part has 69.5 mΩ DCR and 2.3 A Isat. Meeting ≥ 11 A at 10 µH needs ~23× the core volume. 10 µH is also far above what the duty/ripple needs. | CMP research (XGL4030 family) | **Reject** | 1.0 µH XGL5030-102: 4.8 mΩ, Isat 14 A (30 % drop) |

## Concept-level problems

| Problem | Why it matters | Resolution |
|---|---|---|
| PCB was a circular outline only | No circuit was ever placed or routed, so no electrical or thermal evidence existed | Real schematic, placed and routed PCB, ERC/DRC (Gates B–E) |
| Diagrams were illustrations | Pin numbers and connectivity were never verified | Native KiCad schematic; netlist compared pin-by-pin with `engineering/design/connectivity.yaml` |
| Battery polarity contradiction | Brief: "centre spring connected to the battery cathode"; earlier docs: spring = positive | In electrochemistry (IUPAC), the cathode of a discharging cell is its **positive** electrode, so both statements can mean "spring = B+". In diode terminology, "cathode" means negative. Interpretation adopted: **spring = B+, ring = B−** (standard host convention). The owner accepted it on 2026-10-25 provided the board marks it; both boards carry B+/B− silkscreen labels (REQ-BAT-04, DD-12). Reverse-polarity protection makes a wrong host non-destructive. |
| No output disconnect | A boost passes the cell voltage to the diode when not switching; research shows 0.5 to > 3 A could flow with the driver "off" | Buck-boost isolates the input when disabled |
| 4 A vs diode rating | 4 A is above the NUBM44's typical 3.0 A and above sister diodes' 3–4 A absolute maxima; most units exceed the 6.0 W optical limit at 4 A | Hardware sized for 4.0 A as specified; current set by one resistor with 3.0 / 3.5 A alternates. The owner kept 4.0 A and accepted the diode-life risk (DD-13). |
| Efficiency claims | > 95 % at 4 V was stated without evidence | Estimated 94.6 % with the protection the design needs (`research/architecture-comparison.md` §5). The owner accepted a ≥ 94 % target (DD-26); bench test T1.7 measures it. |
