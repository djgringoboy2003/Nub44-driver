# Power architecture comparison and selection

Status: **decision made: Architecture A (TI TPS552882 4-switch buck-boost)**, 2026-10-24.
Evidence: `research/converter-ic-research.md` (datasheets PWR-xx), `research/nubm44-research.md` (LD-xx),
`research/battery-and-mechanics.md` (BAT-xx), `research/component-research.md` (CMP-xx), and the loss models in
`automation/nubm44/calc/`. Efficiency numbers are model estimates at the board input terminals, not measurements.

## 1. What the requirements force

| Fact | Value | Source | Consequence |
|---|---|---|---|
| Battery voltage at the board, loaded | 2.83–4.20 V | BAT research, UVLO design | Converter input range |
| NUBM44 Vf at 4 A, 25 °C | 4.26–4.62 V (community data) | LD research | Output is usually above the input… |
| NUBM44 Vf at 3 A (spec-style table) | 3.6–4.8 V | LD research (LIVE Lasersysteme table) | …but can be **below** a full cell |
| Vf temperature coefficient | ≈ −3.8 mV/K | LD research | Hot diode at 65 °C case: −0.15 V |
| Design compliance window | 3.8–5.2 V at the diode | LD research | Input and output ranges **overlap** |
| A plain boost when not switching | Passes Vbat − Vdiode to the load | PWR research §1.1 | Laser can emit while "off" |

Because the input and output voltage ranges overlap, a boost-only converter **cannot** guarantee constant
current at every corner (full cell, hot or low-Vf diode, reduced current setting). At those points current is
limited only by the diode I–V curve. That violates REQ-OUT-02 ("true constant-current control") and
REQ-SAFE-03 ("no emission until enabled").

## 2. Candidates

| ID | Architecture | Lead IC | How constant current is achieved | Disconnect when off |
|---|---|---|---|---|
| A | 4-switch synchronous buck-boost, boost leg integrated, external buck-leg FETs | TPS552882 | High-side shunt → INA186 → FB (primary). TPS552882 ISP/ISN loop is an independent backup limit. | Yes, buck high-side FET off |
| B | Synchronous boost + series linear clamp FET + current-sense loop | TPS61288 | CSA into FB; the clamp FET limits current when Vf < Vin, dissipating the difference | Clamp FET (low-side) |
| C | Fully integrated 4-switch buck-boost | TPS552892 | Built-in CC loop (50 mV) or CSA into FB | Yes |
| D | Asynchronous boost (earlier concept) | XL6009 | LM358 loop into FB | No |

## 3. Comparison matrix (numerical)

Common assumptions: 4.0 A out; typical diode (Vf 4.43 V at 4 A); high-side reverse-polarity P-FET SiSS23DN
(Rds × 1.3 for temperature); XGL5030-102 inductor (DCR × 1.2); board-input efficiency.

| Criterion | A: TPS552882 | B: TPS61288 + clamp | C: TPS552892 | D: XL6009 |
|---|---|---|---|---|
| Input range (datasheet) | 2.7–36 V (start ≥ 3.0 V max) | 2.0–18 V | 3.0–36 V | **5–32 V: fails** |
| Converter current limit vs need (7.6–8.9 A avg worst case) | 14 A min avg at 20 kΩ; set to 10.2 A min (12.0 typ) | 12 A min peak (fixed 12–17.1 A) | **7 A min avg: fails** | **4 A typ: fails** |
| Regulates when Vf < Vbat | **Yes** (buck mode) | Only by burning (Vbat − Vf) × I in the clamp (≤ 1.5 W) | Yes | No |
| Off-state isolation | **Yes**, inherent | Yes, via clamp FET | Yes | No |
| Output short-circuit | **Hiccup** (Vout < 0.8 V at limit → 76 ms off) | Clamp limits current; firmware/HW must shut down within ms (≈ 15 W in the clamp) | Hiccup | None |
| Estimated η at 4.0 V | **94.6 %** | 94.8 % | 90.4 % | ≈ 75 % or worse |
| Estimated η at 3.0 V (worst diode) | **91.3 %** | 91.8 % | **81.9 %: fails 86 %** | n/a |
| Current-sense polarity | High-side; laser cathode = GND = host | Low-side clamp; cathode floats above GND | High-side | Low-side |
| Fault tolerance of current control | Two independent limits (CSA loop + ISP/ISN 5 A) | One loop + clamp (both via the CSA) | One or two | One |
| Extra parts vs bare IC | 2 FETs | Clamp FET, op-amp, OV clamp, interlock logic | none | n/a |
| Control-loop complexity | Single CC loop (Type II); RHPZ only in boost mode | Two interacting loops (boost CC + clamp) | Single loop | — |
| Soft start | 4 ms internal reference ramp → current ramp | 3 ms internal; clamp needs its own ramp | Internal | — |
| IC package | VQFN-HR 4.0 × 3.5 mm (+2 × 3.3 × 3.3 FETs) | VQFN-HR 2.5 × 3.0 mm (+ clamp FET 3.3 × 3.3, op-amp) | 3.0 × 5.0 mm | TO-263 (≈ 10 × 15 mm): fails |
| Inductor | 1.0 µH, 5.3 × 5.5 mm (limit set by RILIM) | ≥ 12–17 A Isat needed by the fixed limit (TI examples ≥ 10 × 11 mm) | 1.0 µH | 33 µH |
| SPICE model | None published (behavioural model built here) | PSpice, encryption unknown | Encrypted | None |
| Sourcing (retrieved 2026-10-24) | TI store 2,950 pcs; LCSC UNKNOWN | UNKNOWN | UNKNOWN | — |

## 4. Decision

**Architecture A** is selected. The deciding evidence:

1. It is the only candidate that meets the current requirement at the empty-cell corner **and** keeps true
   constant-current regulation when the diode needs less voltage than the cell supplies.
2. It isolates the laser from the battery when disabled, with no extra series element, so "off" means off
   (REQ-SAFE-03, REQ-SAFE-11).
3. It has two independent current ceilings: the fast CSA loop, plus the TPS552882's own ISP/ISN loop at
   48–52 mV / 10 mΩ = 4.8–5.2 A. A failed amplifier or firmware cannot drive the diode to the converter's
   12 A limit.
4. Output shorts are handled by hiccup in hardware.
5. Architecture B's efficiency advantage is only 0.2–0.5 %. B is less safe: its laser cathode floats above the
   host ground, it needs two interacting loops, and it dissipates up to 1.5 W in the clamp at the overlap corner.

## 5. Efficiency targets: outcome

| Target | Result (estimate) | Status |
|---|---|---|
| > 95 % at 4.0 V (REQ-PWR-02 as briefed) | 94.6 % (typical diode) | **Not met**, likely infeasible with the required protection; see the outcome note below |
| ≥ 86 % at 3.0 V (REQ-PWR-03) | 91.3 % (worst diode) | Met by estimate; NEEDS-TEST |

At 4.0 V about 1.0 W is lost in total. The protection elements alone account for about 0.30 W (1.6 %):
the reverse-polarity P-FET (0.13 W) and the 10 mΩ shunt (0.16 W, needed so the backup limit sits at
5 A instead of 10 A). Removing them would buy roughly +1.5 %, but would remove reverse-polarity
robustness and the independent current ceiling. That trade is not acceptable for a Class 4 laser.

**Achievable alternative stated:** ≥ 94 % at 4.0 V and ≥ 90 % at 3.0 V (typical diode, 25 °C), to be
confirmed by measurement (documentation/testing/test-plan.md).

**Outcome (2026-10-25):** the owner accepted ≥ 94 % at 4.0 V as REQ-PWR-02 (DD-26). Bench test T1.7
measures it.

## 6. Rejected options (short)

- **XL6009:** 5–32 V input (not specified for Li-ion), 4 A typ switch, 110–120 mΩ switch, TO-263 package.
- **TPS552892 / TPS55289:** average current limit 7 A / 6.7 A min, below the 7.6–8.9 A worst case.
- **TPS61088 / TPS61089 / TPS61178 / TPS61378-Q1 / TPS61022 / TPS61236P:** insufficient minimum current
  limit, no disconnect, and/or pass-through hazards (PWR research §1.2).
- **LM5155x / LM5156x:** non-synchronous; Schottky loss alone is 7–9 % of output.
- **TPS55288** (I²C sibling of A): equivalent power stage. Not chosen because the converter would not switch until
  firmware sets the OE bit over I²C. The TPS552882 is configured entirely by resistors, so hardware alone defines
  the current ceiling.
