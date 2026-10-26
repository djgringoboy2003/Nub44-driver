# Power-layout review

Status: evaluation board reviewed and corrected where the routed session allowed; compact board reviewed as a
parked routing draft (DD-27). Physical behaviour (switching waveforms, temperatures, loop inductance) remains a
Gate G item.

The numbers come from `automation/review/power_layout.py`, which reads the routed KiCad copper and writes
`reports/layout-review-<variant>.md/.json` plus figures in `reports/layout-review/<variant>/`. The validator
(`VAL-LAYOUT-<variant>`) only checks that each report was generated from the current board, parameters and
calculations. The dispositions below are engineering judgement recorded for each screening result.
Screening results never open or close a gate.

## Method

- **Copper model.** KiCad's Python exports every copper item of the routed board (filled zones, tracks, pads,
  vias) per net and layer (`layout_extract.py`). The copper is rasterised on a 0.05 mm grid (0.1 mm for the
  ground solve) by an exact cell-centre test (`raster.py`).
- **DC current flow** (`dcflow.py`). This is a resistor grid over each net's copper. Via barrels and plated
  holes join the layers. Each component terminal is an equipotential pad group (for example U1 pins 11 + 26).
  Currents are the boost-mode operating points of `engineering/calculations/power-stage-results.json`: the
  worst input-current point (2.83 V, cold high-Vf diode, 7.39 A) and the 4.0 V typical point. The model
  returns path resistance, I²R loss, current per unit width and via currents. The ground solve also gives the
  DC offsets seen by the quiet references.
- **Geometry** of the TPS552882 layout guidelines (SLVSFC5 §10.1, source LEAD-01):
  - hot-loop legs and their top-layer closure;
  - gate-drive, bootstrap and VCC loop-area estimates;
  - ISP/ISN pair separation;
  - spacing of high-impedance nodes from switching copper;
  - vias near the power pins.
- **Assumptions.** 1 oz copper on all layers and the DD-14 layer spacing, both from `parameters.yaml`;
  finished thickness is UNKNOWN. Barrel plating is assumed to be 20 µm (UNKNOWN). Resistance is computed at
  25 °C and losses are quoted for 75 °C copper. Solver accuracy is checked against analytic cases in
  `tests/test_layout_review.py`: strip resistance, parallel layers, barrel formula, necks and open paths.
- **Screens.** These are heuristics, stated in each report:
  - a neck is flagged when current per width over the hottest 0.25 mm² exceeds the width an IPC-2221 long
    trace needs at 20 K rise;
  - a via barrel is flagged above 1 A;
  - a high-impedance node is flagged when it is within 0.5 mm of switching copper;
  - a ground-offset setpoint shift is flagged above 0.1 %.

## Evaluation board

### Corrections made

Only source pours changed (`hardware/evaluation-board/placement.yaml`). The archived router session
(`routing/nubm44_driver.dsn/.ses`) was reapplied unchanged. All 13 post-route correction selectors still
matched, and KiCad DRC remained 0 errors, 0 warnings, 0 unconnected and 0 parity findings.

| Path | Before | After | Change |
|---|---|---|---|
| SW1 (Q2 source → L1) | 1.91 mΩ, equivalent width 0.51 mm | 0.98 mΩ, 1.30 mm | Pour joined to the Q2 source pins along their height; the old 0.55 mm junction beside the DR1H via carried the whole inductor current |
| VOUT (U1 → shunt) | 3.01 mΩ, 0.68 mm | 2.27 mΩ, 1.16 mm | In2 VOUT finger under U1's output column, fed by the existing column via |
| LD_P (shunt → J3) | 1.28 mΩ | 0.88 mΩ | LD_P pour enlarged toward J3 |
| Copper loss above the efficiency model, 4.0 V | 142 mW | 96 mW | Estimate with CAD copper: 93.88 % → 94.11 % |

### Dispositions

| Result | Disposition |
|---|---|
| NECK-SW2: 0.75 mm equivalent at U1 pin 21 | **Package limit (DD-16).** The inductor current enters U1 through pin 21 (0.25 mm) and the bridged centre pad 25. BOOT1 pin 22 and BOOT2 pin 20 bound the copper approach to about 0.65 mm. Measure the U1 top-edge temperature in T2.7 and T2.12. HDI via-in-pad (DD-16 production option) is the remedy. |
| NECK-SW1: 1.30 mm after correction | **Accepted for evaluation.** The remaining crowding sits beside Q2 pad 3 and the DR1H via. Widening further means moving that via, which needs a new router session. |
| NECK-VOUT: 1.16 mm; VIA-VOUT: the column via carries 1.68 A | **Accepted.** Corner crowding beside C14 remains. Barrel loss is about 3 mW (1.2 mΩ between F.Cu and In2). The 1 A screen is a conservative rule of thumb. C14 must stay where it is because it closes the boost hot loop. |
| NECK-VBAT 1.57 mm, NECK-BAT_SPRING 2.61 mm | **Accepted.** This is crowding at the Q1 source pins and the J1 wire pad, set by the part terminals. Q1 and J1 temperatures are covered in T2.7. |
| COPPER-LOSS: +96 mW | **Accepted (DD-26).** Routed copper, including switch-node copper that the model omits, lowers the 4.0 V estimate from 94.59 % to about 94.1 %. That meets the owner's ≥ 94 % deviation target with about 0.1 % margin. The calculation keeps the model allowances (`model_copper_*` in `parameters.yaml`); bench test T1.7 measures the real value. |
| GND-OFFSET: +11 mA (+0.28 %) at the worst point | **Accepted for evaluation; bench check T2.11.** AGND pin 10 shares copper with PGND pin 9, so it sits about 3.3 mV above the quiet references at 3.4 A of PGND current. SLVSFC5 asks for AGND to join PGND at the VCC capacitor. On this package, PGND, AGND and VOUT are adjacent pins (9/10/11). The HF output capacitor C14 must straddle pin 10 to close the boost loop, and DD-16 leaves pin 9 as PGND's only exit. The DC shift sits inside the 5 % budget (worst-case stack 3.58 % + 0.28 %). The AC effect is UNKNOWN. A production option is a separate AGND net with a net tie at C7, combined with HDI vias. |
| DRIVE-DR1H, DRIVE-DR1L, DRIVE-BOOT1 | **Accepted for evaluation; bench check T2.9.** These belong to the external buck leg, which switches only in the transition region (low-Vf hot diode at 4.0–4.2 V). In boost mode Q2 stays on. TI's layout example (SLVSFC5 Fig. 10-1) also takes the gate traces to the bottom layer. The BOOT1/DR1H loop (about 15 + 11 mm, loop-area estimates 18 and 12 mm²) is the largest drive loop on the board. |
| DRIVE-VCC5: C7 reached through In2 and two vias, 7.8 mm | **Accepted for evaluation; bench check T2.10.** VCC (pin 19) and BOOT2 (pin 20) share U1's top-right corner. L1's courtyard is 0.12 mm from U1's, so neither capacitor fits above the IC. A C7 to the right of pin 19 blocks the COMP/ILIM/FB escapes, and moving it costs BOOT2 loop area. The loop-area estimate against ground is 1.5 mm² because In2 lies over B.Cu ground. On the compact board C7 must have priority. |
| SPACE-COMP: 0.3 mm from BOOT2 | **Accepted; bench check T2.11.** COMP runs beside the BOOT2 trace for about 3 mm. C9 (680 pF) holds COMP to a low impedance at the switching frequency. |
| SPACE-EN_UVLO: 0.2 mm from the SW1 pour corner near Q3 | **Accepted; bench check T2.6.** SW1 is static in boost mode. EN has hysteresis, and the hardware enable FETs hold it low when emission is off. |
| KELVIN-ISP_K / ISN_K | **Accepted for evaluation.** The INA186 branch (primary regulation) is paired on F.Cu at 0.76 mm pitch over 2.3 mm. The U1 branch (the slow 4.8–5.2 A backup limit) runs ISP on In2 directly below ISN on F.Cu, 1.38 mm apart across the In1 plane, for about 6 mm. Loop area does not affect DC accuracy. Route the pair on one layer on the compact board. |
| LOOP-C1, C3, C11–C13 (INFO) | **Accepted.** These capacitors close their loops through vias into In1, which lies 0.22 mm below the top-layer forward path. The capacitors nearest each loop close on the top layer: C2 (buck input) and C10/C14 (boost output). |

## Compact board (routing draft)

In the grid-routed revision (DD-25, `engineering/compact-feasibility.md`), the review shows every power
path connected:

- VBAT: 0.49 mΩ through an 8-via field.
- VOUT: 1.46 mΩ.
- SW1: 0.30 mΩ.
- SW2: 1.23 mΩ (package-limited).
- BAT_SPRING: 0.60 mΩ.
- LD_P: 0.47 mΩ.

Copper loss above the model is +44 mW at 4.0 V (estimate 94.37 %).

Items still open:

- 20 unconnected items, mostly MCU signals.
- PGND now has a plane via under C14 and C12 has moved away from U1's ground pins. The worst-case
  setpoint shift from ground offsets fell from +1.14 % to +0.75 %. It is still above the evaluation
  board's +0.28 %.

The evaluation-board lessons still apply:

1. Give C7 (VCC) and C14 (boost HF) the U1 corner positions first, then C6 (BOOT2).
2. Join the Q2 source pins to the inductor pad along their full height. Keep switch-node copper away from
   FSW, COMP and EN.
3. Size every power transition for 8 A, using several vias per layer change. Confirm with the
   current-flow report rather than by eye.
4. Route ISP/ISN as one same-layer pair from the shunt sense pads.
5. Quote HDI via-in-pad for the RPM0026A centre pads (DD-16).

## Bench checks added

T2.9–T2.12 in `documentation/testing/test-plan.md`: switch-node and gate waveforms, VCC ripple, control-node
noise and current jitter, and a thermal image of U1's top edge.
