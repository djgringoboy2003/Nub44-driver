# Compact 22 mm routing assessment

Status: routing draft; Gates D/E/F remain open. This reflects the present placement and automated routing,
not proof that the electrical design is impossible on a 22 mm board.

## Current state (2026-10-25, grid-routed revision)

These are the KiCad counts and the layout-review results (`reports/layout-review-compact-22mm.md`).

| Measure | First draft | Re-floorplan (DD-24) | Grid-routed (DD-25) |
|---|---|---|---|
| KiCad DRC errors / warnings | 0 / 3 | 0 / 6 | 0 / 3 (dangling vias of open nets) |
| Unconnected items | 43 | 31 | 20 |
| VBAT, Q1 to Q2 | one via carrying 7.4 A | 0.50 mΩ | 0.49 mΩ; 8-via field |
| VOUT, U1 to shunt | not connected | 1.69 mΩ | 1.46 mΩ |
| SW1 / SW2 | 2.49 / 1.20 mm equivalent | 0.30 / 1.23 mΩ | 0.30 / 1.23 mΩ (SW2 package-limited, DD-16) |
| BAT_SPRING, LD_P | — | 0.60 / 0.78 mΩ | 0.60 / 0.47 mΩ |
| Copper loss above the model, 4.0 V | — | +56 mW | +44 mW |
| Ground-offset setpoint shift, worst point | — | +1.14 % | +0.75 % |

What remains open (20 items):

- MCU nets: VMCU (4), NTC_PWR (2), VBAT_SENSE (2), SW_IN, PG, IND_OUT, LASER_EN_N and CS_OUT.
- VBAT to its small loads (R10, R18, TP1 and the U1 VIN feed): 4.
- U2's Kelvin inputs ISP_K and ISN_K: 2. One GND pad (R1.2).

The validation register therefore keeps `VAL-ROUTE`/`VAL-DRC` for this variant at FAIL.

## Why the rest does not route: via sites around the MCU

A through via needs free copper on F.Cu, In2.Cu and B.Cu at once. The power pours, C1-C3, L1, U1's escape
vias and the harness pads leave about 15 mm² of the board where a signal via can go at all
(`grid_route.py` legality map). The MCU sits below C1-C3, so none of those sites is next to its pins.
Every MCU signal must first run on B.Cu to a via site, and the
remaining nets compete for the same few corridors. In2 is the only layer that crosses the board centre,
and DR1H (Q2 gate to U1) plus the column of U1 escape vias divides it.

With the negotiated router (DD-25), about 19 nets keep clashing at 0.15 mm track and space no matter how
long they negotiate. This is a capacity limit, not a routing-order effect. Options, each needing an owner
decision or a documented design decision:

1. **Plated wire pads for the harness (TP9-TP13).** They are SMD pads today. Plated holes, as on the evaluation
   board, would make each pad a layer change for its own net next to the MCU, and give the wires
   better strain relief.
2. **MCU pin swap.** The firmware polls every digital MCU pin; only the ADC and comparator inputs and UPDI are
   fixed. Placing PG/CC, SW/INTLK and LASER_EN on the package side that faces their destinations removes
   most crossings. The pin map is shared with the evaluation board, so this needs either a re-route there
   or a variant-specific map and firmware build.
3. **Inner-layer fine lines.** PCBWay's normal process allows 4/5 mil on 1 oz inner copper against 5/6 mil
   outside (MFG-01). Rules of 0.10/0.13 mm on In2 would add about 30 % routing capacity where it is needed.
4. **HDI blind vias (DD-16 option).** These remove the both-sides-free condition, at fabrication cost.

## Structural constraint: spring-pad via keep-out

The centre spring pad J1 (B.Cu, radius 2.50 mm) excludes through vias within 2.95 mm of the board centre:
pad radius, plus 0.15 mm clearance, plus the 0.30 mm via radius. In the previous draft, U1 sat directly
above it, with 23 of its 26 pads inside that radius and 13 of them needing a layer change. The
autorouter's FSW trace then sealed U1's left pin column. Moving U1 away left only 7, 6, 4 or 2 such pads
for shifts of 1.0, 1.5, 2.0 or 2.5 mm.

## Re-floorplan (DD-24)

**Power column.** L1 now sits over the spring pad: its pads are top-layer power copper and need no vias.
U1 is 2 mm below it. Only pins 1 (DR1L) and 23 (SW1) remain inside the keep-out, and both escape on F.Cu.

**U1 escapes.** Every U1 pin has a source-defined escape (`fanout_skip: [U1]`):
- BOOT1 and SW1 leave the top edge in parallel lanes to C5 and never cross; SW1 climbs left of C5 to the
  SW1 pour.
- BOOT2 runs above C7 to C6, whose SW2 pad joins the SW2 pour.
- VCC reaches C7 in 0.6 mm on F.Cu. This needed J3's laser pads at 3.5 mm pitch on this variant (the
  evaluation board keeps 4.0 mm).
- The left column fans out to staggered vias.
- COMP, ILIM, FB and the MODE ground drop through vias right of U1 to bottom-side Cp, Rc/Cc, ILIM and FB
  resistors.

**Bottom power stage.**
- Q1 sits directly under Q2, so VBAT changes layer through an 8-via field beside both.
- BAT_SPRING runs from Q1's drain straight to the spring pad.
- Q3 moved right, so SW1 vias fit between the two bottom MOSFET drains.

**MCU and small parts.** The MCU moved to the bottom lower left, beside its harness pads, the enable
chain and the PG/CC vias. U2 and D1 form a column on the bottom right. `automation/placement/place_opt.py`
placed the remaining small parts (simulated annealing on net length, affinity to the pins they serve,
side flips allowed for listed parts). Its hard rules match the build: courtyards, radius, source vias and
tracks, power pours and keep-outs.

**Router keep-outs.** These temporary rule areas over the power pours, on F.Cu and B.Cu plus the In2
battery path, stop the router from cutting power copper. The Specctra export treats pours as conduction
planes that other nets may cross, and earlier runs did exactly that. Finish deletes the keep-outs.

## Next steps

1. Decide which of the options above to take. Options 1 and 2 are the most direct, and option 3 is a rule
   change only.
2. Re-run `grid_route.py --rebuild --partial --write`, then place, route, finish, DRC and the layout review.
3. Accept the variant only when DRC shows 0 unconnected and 0 errors, every power path is connected in the
   current-flow report, and no review screen has worsened without a recorded disposition.

Any relaxation of the 22 mm envelope, via technology or layer strategy needs a documented design decision
and renewed fabrication review. Assembly yield, power-path temperature rise and host heat transfer are
UNKNOWN until fabrication review and prototype measurements. Gate G remains open and no manufacturing
order has been placed. Battery polarity is marked on the silkscreen ("B+" beside the spring pad, "B-" beside
the ring; REQ-BAT-04).
