# Assembly and bring-up instructions

This is an engineering review design. Use reports/validation-register.md for the actual release state.
Gate F remains open until PCB routing, electrical checks, complete exports and the owner polarity
confirmation all pass. Gate G requires measured prototype results. No manufacturing order is automated.

## Select and review the variant

- Variant A is the 22 mm round, double-sided compact board. Its small passives and centre-pad bridges
  need assembly review (DD-16/DD-17); the spring and host contact are owner-specific.
- Variant B is the larger four-layer evaluation board with separate battery wire pads and the full set
  of test points. Use it for accessible measurements after the CAD release checks pass.
- The circuit setpoint is the source value in engineering/design/parameters.yaml. The default 4 A
  remains an owner risk decision (REQ-OUT-01/DD-13). Alternate setpoints require the documented divider
  change and regenerated calculation/schematic evidence.

## Before fabrication or assembly

1. Confirm the battery contact polarity (REQ-BAT-04/DD-12). The current source interpretation is
   centre spring B+, perimeter ring B-. The evaluation input pads retain those electrical net names.
2. Resolve routing, DRC and schematic-parity findings in the validation register. Inspect the gate-drive,
   bootstrap, switching-current loops, Kelvin sense paths and thermal connections against the cited
   converter and amplifier datasheets. Automated route completion alone does not close REQ-PCB-01.
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
