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
  kept 4.0 A and accepts the diode-life risk (REQ-OUT-01/DD-13). An alternate setpoint needs the documented
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
3. Regenerate the package with scripts/export-pcbway.ps1 for the chosen variant. Review the actual BOM,
   signed centroid positions, rotations, assembly PDFs, drill maps, stack-up and iBOM. Stock, prices and
   unverified substitutions remain UNKNOWN; confirm them with the assembler before any order.
4. Treat placeholder 3D bodies as mechanical illustrations. The custom TPS552882 body is generated,
   not a supplier-certified package model.

## Assembly

Use the CAD-derived assembly drawings and iBOM with the exact revision being assembled. Verify IC pin 1,
MOSFET gate/source/drain orientation, diode polarity, shunt sense pads and the TPS552882 centre-pad
bridges. Do not substitute a device whose footprint, pin mapping or ratings have not been reviewed.
The battery spring is hand-fitted after assembly; its final part and host dimensions are UNKNOWN.
Keep the laser diode disconnected during inspection and electrical bring-up.

## Bring-up and evidence

Follow documentation/testing/test-plan.md in order, starting with unpowered inspection and a current-limited
supply. Use a thermally rated dummy load for the electrical and fault tests. Record the board revision,
BOM, firmware, instruments, conditions and waveforms under documentation/testing/results/.
Advance to laser testing only after the dummy-load tests and the plan's controlled-area arrangements
are satisfied. Gate G remains open until the required measured results have been reviewed.
