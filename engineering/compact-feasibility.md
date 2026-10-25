# Compact 22 mm routing assessment

Status: routing draft; Gate D/E/F remain open. This is a limit of the present placement and automated
routing attempt, not proof that the electrical design is impossible on a 22 mm board.

## Evidence from the corrected pipeline

- 65 footprints are placed from connectivity.yaml and compact-22mm/placement.yaml.
- Board outline radius is source-defined as 11 mm, with four copper layers.
- Routed signal rules are 0.15 mm minimum width/clearance with 0.60/0.30 mm through vias.
- In1.Cu is reserved for GND; source-defined outer/inner pours carry the power nets.
- The 15-pass FreeRouting run completed in 590 s. Its final result was 54 unrouted connections.
  After importing, filling actual KiCad zones and cleaning dangling copper, KiCad reports 43
  unconnected items. These tools count incomplete connections differently; the KiCad report controls
  the CAD gate.
- Current errors/warnings and parity findings are in reports/drc-compact-22mm.json and the validation
  register. Zero geometric errors does not close routing or waive connection-width warnings.

The recovered earlier board had 33 unconnected items, 91 DRC errors, 44 warnings and six parity
warnings. Its apparent extra routing included undersized copper and incorrect bottom-side placement.
The corrected draft must not be ranked by unconnected count alone.

## What changed

Repeated bottom placement now preserves the native transform. Paste-only pads no longer obstruct
copper fanout, and source-layer traces ignore copper on the opposite side while through vias retain
all-layer clearance. The ring radius and C10/C11 spacing were corrected in source. Actual schematic
fields and native project symbol filters now agree with PCB parity checks. Imported subminimum widths
are restored before actual DRC; failures remain visible.

## Power-layout review of the draft

`automation/review/power_layout.py --variant compact-22mm` runs on the draft and reports missing copper
rather than estimating it (`reports/layout-review-compact-22mm.md`). At this revision:
- VOUT has no copper path from U1 to the shunt;
- the whole VBAT input current crosses one via;
- U1 pin 15 is isolated from ground;
- FSW and COMP_RC are 0.15 mm from switching copper;
- the ISP/ISN pair separates by up to 2.7 mm.

`engineering/layout-review.md` lists the placement priorities taken from the evaluation-board review. The
rework is accepted only when the current-flow report shows every power path connected with no
single-via transitions.

## Structural constraint: spring-pad via keep-out under U1

The centre spring pad J1 (B.Cu, radius 2.50 mm) excludes through vias within 2.95 mm of the board centre:
pad radius, plus 0.15 mm clearance, plus the 0.30 mm via radius. U1 sits directly above it at (0.6, 0.9).
At this revision 23 of its 26 pads lie inside that radius. Thirteen of them need a layer change:

- DR1L to Q3 on the bottom;
- PG, CC_FLAG and EN to bottom-side parts;
- VBAT;
- SW1;
- VOUT;
- five ground pins.

So every U1 escape must first travel on F.Cu past the ring of passives around U1. In the routed draft, the
autorouter's FSW trace wrapped around U1's left pin column and sealed it in, and most of the 43
unconnected items are U1 or U3 escapes. Rerunning the same autoroute cannot remove this constraint.

Moving U1 away from the spring pad reduces the via-needing pads inside the keep-out from 13 to 7, 6, 4
and 2 for shifts of 1.0, 1.5, 2.0 and 2.5 mm, measured from the extracted copper.

Options, in order of preference:

1. **Shift the L1/U1 power column 2–2.5 mm away from the spring pad.** L1 then sits partly over J1. Its
   two pads are top-layer power copper and need no vias there. The output-capacitor stack below U1 loses
   one 0805 position, so C11 moves beside U1 or to the bottom side with via-connected VOUT/GND, like C13.
2. **Put L1 entirely over the spring pad with U1 beside it.** This clears the keep-out completely. A
   courtyard check leaves room for only one 0805 output capacitor at the VOUT pins near the board edge.
3. **Use a smaller spring pad.** This is a mechanical choice tied to the spring part (MPN UNKNOWN), so it
   needs the owner's host details.
4. **Use HDI blind vias (F.Cu to In2).** These need the same fabrication quote as the DD-16 via-in-pad
   option.

Whichever option is chosen, U1 should get explicit source-defined escapes for every pin before
autorouting (`fanout_skip: [U1]` plus `tracks`/`vias`, as on the evaluation board). C7 (VCC), C14 (boost
HF) and C6 (BOOT2) get first claim on the U1 corners, and the review report decides acceptance.

## Remaining engineering work

Use the larger evaluation board to establish accessible measurement and fault-test coverage, then
return to the compact placement with the measured constraints. Prioritize the switching loops, gate
returns, quiet Kelvin/feedback routes and minimum power necks before general signal routing. Preserve
all protections and the hardware enable chain. Rework the placement and explicit fanouts rather than
repeatedly rerunning the same failed autoroute. Any proposed relaxation of the 22 mm envelope, via
technology or layer strategy needs a documented design decision and renewed fabrication review.

Assembly yield, power-path temperature rise and host heat transfer are UNKNOWN until fabrication
review and prototype measurements. Gate G remains open. REQ-BAT-04 still requires owner confirmation;
no manufacturing order has been placed.
