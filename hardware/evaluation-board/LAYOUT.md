# Evaluation board layout

The evaluation board uses the same electrical architecture and protection chain as the compact board,
with the larger passives and full set of thirteen test points selected by
`engineering/design/connectivity.yaml`. Placement, copper regions and probe labels are defined in
[`placement.yaml`](placement.yaml). The generated PCB must be rebuilt from that source.

## Arrangement

- J1 and J2 are the battery-input wire pads on the left; J3 is the laser/dummy-load connection on the right.
  Their top-side labels identify the electrical polarity.
- Components and probe pads are on the top side. UPDI, target supply and programming ground are grouped along
  the lower edge. External interlock, switch, signal ground, indicator and laser NTC connections use PTH pads.
- U1, Q2, Q3, L1 and the input/output capacitors form the power core. U2 and the shunt sense connections sit to
  the right; U3 and the independent shutdown pull-downs sit below the power stage.
- F.Cu carries localized power pours and signals. In1.Cu is the ground plane and is excluded from autorouting.
  In2.Cu carries localized VBAT and VOUT pours, with ground elsewhere. B.Cu provides signal-routing space.
- High-current input, switching, output and laser connections use explicit copper regions. Small branch
  tracks from the router are not a substitute for these regions. Vias transfer input/output current between
  layers outside component pads.
- U1 and U3 use explicit ground returns and selected signal escapes before autorouting. The MCU analogue/NTC
  pins fan out together; PG exits are reserved on both ICs. This prevents a neighbouring signal or ground
  via from trapping a fine-pitch pin. The U1 ground fanout also keeps the output-current neck open.

## Validation and remaining review

The floorplan checker reports no courtyard overlap or placement-boundary problems. CAD and routing results
are recorded in `reports/pcb-evaluation-board.json` and `reports/drc-evaluation-board.json`; use the current
reports rather than inferring a passing result from the presence of a PCB file.

The 2026-10-24 routed candidate has 68 footprints and thirteen labelled test points. Its full KiCad DRC
reported **0 errors, 0 warnings, 0 unconnected items and 0 schematic-parity findings**. Repeating the finish
stage preserved 490 tracks/vias and twelve zones; the repeated DRC result is recorded in the same report.
These results use the project's documented DRC omission policy in DD-20.

An initial autorouter experiment produced sub-minimum-width neckdowns and was rejected. The common routing
pipeline now disables automatic neckdown/fanout, restores any remaining imported sub-minimum track widths,
and reserves In1.Cu for ground. Every imported route must then pass full DRC; widening a track never implies
that its clearance is valid. The final DRC result must include clearance, minimum-width, connectivity and
schematic-parity checks.

Source-defined post-route corrections replace BOOT1's crossing of the SW2 current path, join ILIM, remove
an unused single-layer NTC via and centre an output branch on its via. They match the routed copper by exact
net/layer/geometry. A new autorouter session may have different geometry and must pass DRC again; a selector
matching no segment does not establish that the intended correction is unnecessary.

The power-layout review (`engineering/layout-review.md`, generated numbers in
`reports/layout-review-evaluation-board.md`) solved the DC current flow through the routed copper. It also
measured the SLVSFC5 §10.1 geometry: hot loops, gate/bootstrap/VCC loops, the Kelvin pair and the spacing
of the feedback nodes.

The review changed three source pours, re-applied to the same router session with DRC unchanged:
- The SW1 pour now joins the Q2 source pins along their height (1.91 → 0.98 mΩ).
- An In2 VOUT finger runs under U1's output column (3.01 → 2.27 mΩ).
- The LD_P pour is larger (1.28 → 0.88 mΩ).

The remaining items are dispositioned there, with bench checks T2.9–T2.12:
- the package-limited SW2 entry and AGND/PGND arrangement (DD-16);
- the buck-leg gate and bootstrap loops;
- C7's routing through In2;
- the U1 branch of the ISP/ISN pair.

DRC and DC current flow cannot establish transient performance or operating temperature. Loop inductance,
switching waveforms and operating temperatures remain `UNKNOWN`, and no bench measurements were generated
by this CAD work. Gate G requires bench measurements, beginning with a dummy load and the hardware interlock.
The repository's release blockers remain applicable; no manufacturing release
or order is implied by this evaluation layout.

## Rebuild

From the repository root:

```powershell
.venv\Scripts\python.exe automation\placement\build_pcb.py --variant evaluation-board --stage all
.venv\Scripts\python.exe automation\placement\floorplan.py --variant evaluation-board
```

The first command regenerates placement, reroutes, fills copper and runs DRC. Inspect its returned validation
status and current reports before using any regenerated board.
