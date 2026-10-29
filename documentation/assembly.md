# Assembly and bring-up instructions

This is an engineering review design. Use reports/validation-register.md for the actual release state:
- Gate F passes its automated checks for the evaluation board and stays open for the compact board.
- Gate G requires measured prototype results.

No manufacturing order is automated; the owner places any order manually.

## Select and review the variant

- **Variant B** is the larger four-layer evaluation board, with separate battery wire pads and the full
  set of test points. Its CAD checks pass, and it is the first prototype (DD-27).
- **Variant A** is the 22 mm round, double-sided compact board, a parked routing draft (DD-27). Its small
  passives and centre-pad bridges need assembly review (DD-16/DD-17), and the spring and host contact are
  owner-specific.
- **Setpoint:** the circuit setpoint is the source value in engineering/design/parameters.yaml. The owner
  set 4.5 A (R8 8.66 kΩ, R3 24.9 kΩ) and accepts the diode-life risk (REQ-OUT-01/DD-36; was 4.0 A, DD-13).
  An alternate setpoint (3.0/3.5/4.0 A: R8 2.49/4.53/6.65 kΩ) needs the documented
  divider change and regenerated calculation and schematic evidence.

## Before fabrication or assembly

1. Battery contact polarity (REQ-BAT-04/DD-12): centre spring B+, perimeter ring B-. The owner accepts
   either orientation provided the board states it, and both boards do: "B+" beside the spring pad and
   "B-" beside the ring on the compact board, "B+ INPUT"/"B- INPUT" on the evaluation board. Check the host
   against these labels before first power (T3.3).
2. Confirm that the validation register shows no open routing, DRC or schematic-parity findings for the
   chosen variant (true for the evaluation board). Review the gate-drive, bootstrap and switching-current
   loops, the Kelvin sense paths and the thermal connections against the cited converter and amplifier
   datasheets; `engineering/layout-review.md` records the evaluation-board dispositions. Automated route
   completion alone does not close REQ-PCB-01.
3. Check reports/release-readiness.md: order a prototype only at the PROTOTYPE_CANDIDATE level, which needs the
   human footprint and orientation reviews recorded in engineering/release/design-reviews.yaml (FP-U1, FP-L1,
   FP-POWERPAK, FP-RS1, ORIENT). A package classed DRAFT_REVIEW_INCOMPLETE_BOARD (it carries DO_NOT_FABRICATE.txt in
   its fabrication ZIP) must never be ordered.
4. Regenerate the package with scripts/export-pcbway.ps1 for the chosen variant. Review the actual BOM,
   signed centroid positions, rotations, assembly PDFs, drill maps, stack-up and iBOM. Stock, prices and
   unverified substitutions remain UNKNOWN; confirm them with the assembler before any order.
5. Treat placeholder 3D bodies as mechanical illustrations. The custom TPS552882 body is generated,
   not a supplier-certified package model.

## Assembly

Use the CAD-derived assembly drawings and iBOM with the exact revision being assembled. Verify IC pin 1,
MOSFET gate/source/drain orientation, diode polarity, shunt sense pads and the TPS552882 centre-pad
bridges. Do not substitute a device whose footprint, pin mapping or ratings have not been reviewed.
The battery spring is hand-fitted after assembly; its final part and host dimensions are UNKNOWN.
Keep the laser diode disconnected during inspection and electrical bring-up.

## Bring-up and evidence

Follow documentation/testing/test-plan.md in order, starting with unpowered inspection and a current-limited
supply. Program the firmware and the fuses (firmware/README.md; the firmware refuses to run with other fuse values
and blinks fault 15), then read the fuses back (T0.4). Use a thermally rated dummy load for the electrical and
fault tests. Record each test with automation/bench/bench.py (board serial, revision, firmware hash, instruments,
conditions, raw data and captures) under documentation/testing/results/<serial>/; see the README there.
Advance to laser testing only after the dummy-load tests and the plan's controlled-area arrangements
are satisfied. Gate G remains open until the required measured results have been reviewed.
