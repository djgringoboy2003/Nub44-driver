# Compact 22 mm routing assessment

Status: routing draft; Gates D/E/F remain open. This reflects the present placement and automated routing,
not proof that the electrical design is impossible on a 22 mm board.

## Current state (2026-10-25 re-floorplan)

The compact board was re-floorplanned around its structural constraint (below) and routed again. These are
the KiCad counts and the layout-review results (`reports/layout-review-compact-22mm.md`).

| Measure | Previous draft | Re-floorplan |
|---|---|---|
| KiCad DRC errors / warnings | 0 / 3 | 0 / 6 (5 dangling vias, 1 connection width) |
| Unconnected items | 43 | 31 |
| VBAT, Q1 to Q2 | one via carrying 7.4 A | 0.50 mΩ; 8-via field, max 1.9 A per via |
| VOUT, U1 to shunt | not connected | 1.69 mΩ, equivalent width 0.81 mm |
| SW1, Q2 to L1 | 2.49 mm equivalent | 0.30 mΩ, 2.07 mm |
| SW2, L1 to U1 | 1.20 mm | 1.23 mΩ, 0.65 mm (package-limited, DD-16) |
| BAT_SPRING, LD_P | — | connected; 0.60 / 0.78 mΩ |

What remains open:

- 31 unconnected items, almost all low-speed signals: MCU, harness, enable chain and sense lines.
- One-item opens on DR1H, PG, CC_FLAG, FB, ISP_K and ISN_K, where a source via is not yet joined to its
  destination.
- Five dangling source vias.
- Weak PGND link: at the worst operating point, U1's PGND reaches the plane with a 15 mV drop. AGND shares
  that copper, so the review reports a +1.14 % shift of the current setpoint (+0.22 % at 4.0 V). Adding GND
  vias at the finish stage collided with routed copper. They must become source vias placed before
  routing.

The validation register therefore keeps `VAL-ROUTE`/`VAL-DRC` for this variant at FAIL.

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

1. Give U1's PGND pins source vias to the plane before routing, then confirm the setpoint shift in the
   review.
   - The bottom output capacitor C12 sits directly under pins 9/10. Its VOUT and GND pads block every
     via position there.
   - A 2026-10-25 attempt confirmed this, so C12 must move first, for example beside C13.
2. Close the one-item opens for DR1H, PG, CC_FLAG, FB and the U2 Kelvin pair with source routes, as was
   done for U1's escapes.
   - U2's Kelvin inputs have no via landing that is free on both sides, because L1's SW2 pad lies above U2's
     left pins.
   - Swapping U2 and D1 puts U2 nearer the shunt's Kelvin vias.
   - FB fits on B.Cu from R9 to R8 at y 4.15 under C9, then 3.85, which clears the ISN Kelvin via.
3. Reduce MCU-region congestion: group the programming pads and pull the enable FETs nearer the EN via.
   The bottom side is at its placement capacity, which is why the optimiser flips some small parts to the
   top.
4. Re-route. Accept the result only when DRC shows 0 unconnected and 0 errors, the current-flow report
   shows every power path connected, and no review screen has worsened without a recorded disposition.

Any relaxation of the 22 mm envelope, via technology or layer strategy needs a documented design decision
and renewed fabrication review. Assembly yield, power-path temperature rise and host heat transfer are
UNKNOWN until fabrication review and prototype measurements. Gate G remains open, REQ-BAT-04 still needs
owner confirmation, and no manufacturing order has been placed.
