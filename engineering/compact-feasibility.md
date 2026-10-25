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
