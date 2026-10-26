# Compact 22 mm routing assessment

**Status: parked routing draft (owner decision 2026-10-25, DD-27).** The evaluation board is prototyped
first. This board is revisited with bench data. Gates D/E/F stay open for this variant. The results reflect the
present placement and routing tools. They are not proof that the circuit cannot fit a 22 mm board.

## Current state

KiCad counts and layout-review results (`reports/layout-review-compact-22mm.md`) for each revision:

| Measure | First draft | Re-floorplan (DD-24) | Grid-routed, current (DD-25) |
|---|---|---|---|
| KiCad DRC errors / warnings | 0 / 3 | 0 / 6 | 0 / 3 (dangling vias of open nets) |
| Unconnected items | 43 | 31 | 20 |
| VBAT, Q1 to Q2 | one via carrying 7.4 A | 0.50 mΩ | 0.49 mΩ; 8-via field |
| VOUT, U1 to shunt | not connected | 1.69 mΩ | 1.46 mΩ |
| SW1 / SW2 | 2.49 / 1.20 mm equivalent | 0.30 / 1.23 mΩ | 0.30 / 1.23 mΩ (SW2 package-limited, DD-16) |
| BAT_SPRING, LD_P | — | 0.60 / 0.78 mΩ | 0.60 / 0.47 mΩ |
| Copper loss above the model, 4.0 V | — | +56 mW | +44 mW |
| Ground-offset setpoint shift, worst point | — | +1.14 % | +0.75 % |

The 20 open items:

- **MCU nets:** VMCU (4), NTC_PWR (2), VBAT_SENSE (2), SW_IN, PG, IND_OUT, LASER_EN_N and CS_OUT.
- **VBAT to its small loads:** R10, R18, TP1 and the U1 VIN feed (4).
- **U2's Kelvin inputs:** ISP_K and ISN_K (2).
- **One GND pad:** R1.2.

The validation register therefore keeps `VAL-ROUTE`/`VAL-DRC` for this variant at FAIL.

## Why the rest does not route

A through via needs free copper on F.Cu, In2.Cu and B.Cu at once. The grid router's legality map shows
about 15 mm² of the board where a signal via can go at all. The rest is taken by:
- the power pours, C1-C3 and L1;
- U1's escape vias;
- the harness pads.

The MCU sits below C1-C3, so none of those sites is next to its pins. Every MCU signal must first run on B.Cu
to a via site, and the nets compete for the same few corridors. In2 is the only layer that crosses the board
centre, and two things divide it:
- DR1H (Q2 gate to U1);
- the column of U1 escape vias.

With the negotiated router (DD-25), about 19 nets keep clashing at 0.15 mm track and space, however long
they negotiate. Two pins (U3 pins 2 and 4) are also unreachable, because the automatic ground vias of U3
pin 3 and C3 sit in front of them.

## Options evaluated

These simulations ran the grid router on a copy of the placed copper (2026-10-25); no project file changed.

| Option | Result |
|---|---|
| Move U3's and C3's ground fanout vias | Removes the two unreachable pins; needed in any case |
| MCU pin swap (the firmware polls every digital pin; only the ADC/comparator inputs and UPDI are fixed) | Still 19 nets clashing after 10 passes; would also change the evaluation board and firmware |
| In2 fine lines, 0.10 / 0.13 mm (PCBWay normal process for 1 oz inner copper, MFG-01) | Still 19 nets clashing |
| Pin swap and fine lines together | Still 19 nets clashing |

The board is short of routing capacity, not of a better net order. Directions that can finish it:

- **HDI blind vias and via-in-pad** (as DD-16 already proposes for U1). This removes the both-sides-free
  condition, at fabrication cost (UNKNOWN until quoted).
- **A placement re-architecture that creates via sites by the MCU.** Not yet simulated. Possible moves:
  - the MCU and harness pads on the top side;
  - plated wire pads for the harness, so each pad is a layer change for its own net;
  - fewer bottom test pads.
- **Fewer parts on the 22 mm variant.**

## Current layout

**Structural constraint.** The centre spring pad J1 (B.Cu, radius 2.50 mm) excludes through vias within
2.95 mm of the board centre: pad radius, plus 0.15 mm clearance, plus the 0.30 mm via radius. In the
first draft, U1 sat directly above it, and 23 of its 26 pads lay inside that radius.

**Power column (DD-24).**
- L1 sits over the spring pad: its pads are top-layer power copper and need no vias.
- U1 is 2 mm below L1. Every U1 pin has a source-defined escape (`fanout_skip: [U1]`):
  - BOOT1 and SW1 leave the top edge in parallel lanes to C5;
  - BOOT2 runs above C7 to C6;
  - VCC reaches C7 in 0.6 mm;
  - the left column fans out to staggered vias;
  - COMP, ILIM, FB and the MODE ground drop through vias to the bottom-side passives.
- J3's laser pads use a 3.5 mm pitch on this variant only; the evaluation board keeps 4.0 mm.
- U1's PGND has a plane via under C14. C12 sits away from U1's ground pins.

**Bottom power stage (DD-24).**
- Q1 sits directly under Q2, and VBAT changes layer through an 8-via field beside both.
- BAT_SPRING runs from Q1's drain straight to the spring pad.
- SW1 vias sit between the Q1 and Q3 drains.

**MCU and small parts (DD-25).**
- The MCU (U3) sits below C1-C3 at (-6.35, 1.2), rotated 0°. Its blocked top edge holds the unused PC1-PC3,
  UPDI and LASER_EN, and its analog pins face the via sites below.
- A 0.8 mm ring around it is kept free of parts on both sides.
- The enable FETs and the over-voltage block (Q4, Q5, Q6, D3, R20) sit at the top right.
- `place_opt.py` placed the small parts. Its hard rules match the build, and it charges for nets that change
  side.

**Layers and routing (DD-25).**
- In2 carries signals only, with GND fill elsewhere. There is no In2 VBAT pour; the battery current runs
  B pour → via field → F pour.
- Router keep-outs over the F.Cu and B.Cu power pours stop FreeRouting from cutting power copper. They are
  cut back around other nets' vias, and finish deletes them.
- `grid_route.py` writes the conflict-free routes (`grid_routes` in `placement.yaml`); FreeRouting tries the
  rest.

## Next steps (after the evaluation bench data)

1. Choose the direction: HDI, a placement re-architecture or fewer parts. Move U3's and C3's ground vias in
   any case.
2. Re-run `grid_route.py --variant compact-22mm --rebuild --partial --write`, then `place`, `route`,
   `finish`, `drc` and the layout review.
3. Accept the variant only when DRC shows 0 unconnected and 0 errors, every power path is connected in the
   current-flow report, and no review screen has worsened without a recorded disposition.

Any relaxation of the 22 mm envelope, via technology or layer strategy needs a documented design decision
and a renewed fabrication review. Assembly yield, power-path temperature rise and host heat transfer are
UNKNOWN until fabrication review and prototype measurements. Battery polarity is marked on the silkscreen:
"B+" beside the spring pad and "B-" beside the ring (REQ-BAT-04).
