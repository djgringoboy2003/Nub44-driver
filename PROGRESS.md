# Progress

## Current state (handover)

_Last updated: 2026-10-26 (documentation audit; the design is unchanged since 2026-10-25)._

| Gate | Status | Evidence |
|---|---|---|
| A Research | PASS | Research/requirement documents; computed register |
| B Electrical design | PASS | Both schematics: ERC 0 errors / 0 warnings; exact connectivity comparison |
| C Simulation | PASS (model-level) | SIM-01 through SIM-11; behavioural averaged model, no vendor model |
| D Routing | Evaluation PASS; compact OPEN | Evaluation fully connected; compact has 20 unconnected items |
| E ERC/DRC | Evaluation PASS; compact OPEN | Evaluation 0 errors / 0 warnings / 0 unconnected / 0 parity; compact 0 / 3 / 20 / 0 |
| F Manufacturing files | Evaluation PASS (automated checks); compact OPEN | Both DRAFT review exports internally PASS; no manufacturing release or order |
| G Physical validation | OPEN | Requires assembled-prototype measurements; cannot be closed by software |

`scripts/validate.ps1` computes the gates into [reports/validation-register.md](reports/validation-register.md),
which the validator also mirrors into the requirement register.
- It exits 1 for two known reasons, compact routing and compact DRC, because the compact board is parked.
- No requirement is blocked or at risk.
- All 147 Python tests pass.
- The firmware passes its 26 host checks and its target build.
- All 21 calculation checks and all 11 simulations pass (model-level).

**Owner decisions (2026-10-25).**
- **Battery polarity:** either orientation is acceptable provided the board marks it. The definition stays
  centre spring = B+, ring = B− (DD-12). Both boards carry it on the silkscreen within PCBWay's legend limits:
  - compact: "B+" by the spring pad, "B-" by the ring;
  - evaluation: "B+ INPUT"/"B- INPUT".

  T3.3 checks the host before first power.
- **Setpoint:** 4.0 A is kept, and the owner accepts the diode-life risk (DD-13).
- **Efficiency:** the deviation is accepted; REQ-PWR-02 is ≥ 94 % at 4.0 V and 4 A (DD-26). Estimates: 94.6 %
  from the loss model, 94.1 % with the evaluation copper, 94.4 % with the compact copper. T1.7 measures it.
- **Evaluation board first:** the compact board stays a routing draft until the evaluation prototype has
  produced bench data.

**Evaluation board (Variant B: 45 × 40 mm, 68 footprints, 13 labelled test points).**
- **Routing:** KiCad DRC is 0/0/0/0. `hardware/evaluation-board/routing/` restores the exact router session.
- **Power-layout review** (`engineering/layout-review.md`, DD-23): the SW1, VOUT and LD_P pours were corrected
  (0.98 / 2.27 / 0.88 mΩ). The package-limited and drive-loop items are accepted with bench checks T2.9–T2.12.
- **Review package** (`manufacturing/pcbway/evaluation-board/`): Gerbers, drills, BOM, centroid, PDFs, iBOM
  and renders. Some supplier stock and prices are UNKNOWN.

**Compact board (Variant A: Ø 22 mm, 65 footprints): parked routing draft.**
- **DRC:** 0 errors, 3 warnings (dangling vias of open nets), 20 unconnected, 0 parity.
- **Power paths:** all connected. VBAT 0.49, VOUT 1.46, SW1 0.30, SW2 1.23, BAT_SPRING 0.60 and LD_P 0.47 mΩ.
  Copper loss is +44 mW above the model, and the ground-offset setpoint shift is +0.75 %.
- **Why 20 items stay open:** they are mostly MCU signals, blocked by a routing-capacity limit. No through-via
  site exists beside the MCU. Simulations show that an MCU pin swap and finer inner lines do not finish the
  board. The real directions are HDI, a placement re-architecture or fewer parts
  (`engineering/compact-feasibility.md`).
- **Tools:**
  - `automation/placement/grid_route.py`: negotiated-congestion grid router; writes the `grid_routes` section.
  - `automation/placement/place_opt.py`: small-part placement optimiser.
  - Router keep-outs.

**Open limitations.**
1. HDI via-in-pad for the RPM0026A centre pads (DD-16) is the remedy for the package-limited SW2, PGND and
   AGND items. It needs a fabrication quote and an owner decision.
2. Some supplier stock and prices are UNKNOWN (`sourcing/components.csv`). Confirm them at order time.
3. Waveforms, temperatures, efficiency and fault response are unmeasured until Gate G.
4. No Git remote is configured. Commits are local.

## Next actions (in order)

1. **Evaluation prototype (owner).**
   - **Optional, before ordering:** each change needs a new router session, DRC, the layout review and fresh
     post-route selectors.
     - Move the DR1H via off the SW1 junction.
     - Route U1's ISP/ISN as a same-layer pair.
     - Move C5 nearer U1.
   - Review `manufacturing/pcbway/evaluation-board/` and `reports/validation-register.md`, and confirm stock
     and prices.
   - Place the order manually; no tool places orders.
2. **Bench testing.** Assemble the prototype and run `documentation/testing/test-plan.md`, starting with a rated
   dummy load. Record results under `documentation/testing/results/<serial>/`; only bench evidence can close
   Gate G.
3. **Compact board.** With the bench data, decide its direction (`engineering/compact-feasibility.md`), then
   re-run the compact chain in this order:
   1. `grid_route.py --variant compact-22mm --rebuild --partial --write`;
   2. `place`, `route`, `finish` and `drc`;
   3. `power_layout.py`.

   Accept the board only with 0 unconnected, 0 DRC errors and every power path connected. `--stage place`
   overwrites the board; to return to the committed routed state, restore the checkpoint in
   `hardware/compact-22mm/routing/`.
4. **Sourcing.** Verify supplier stock, prices and alternatives; keep UNKNOWN until evidence is available.

**Commands and routing replay:**
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\doctor.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\validate.ps1
.venv\Scripts\python.exe automation\review\power_layout.py --variant evaluation-board
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\export-pcbway.ps1 -Variant evaluation-board
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\package.ps1
```

The per-process PowerShell flag is needed on this machine; no system policy was changed.
- After editing any source file, regenerate evidence in the order given in `AGENTS.md`: schematics, DRC,
  layout review, exports, validation.
- For exact route restoration, follow `hardware/<variant>/routing/README.md`.
- A new `build.ps1` or `build_pcb.py --stage all` run reroutes and may change geometry. Exact post-route
  selectors then need fresh DRC and power-path inspection.
- Successful exports and review ZIPs never place orders.

## Log

### 2026-10-26: documentation audit
- **Current state:** status and next actions rewritten so they describe only the present. Superseded blocks
  and the duplicated polarity text were removed (the log keeps the history).
- **Stale statements corrected:**
  - Owner decisions now recorded everywhere they are discussed, including efficiency (DD-26).
  - Evaluation-first status recorded.
  - Compact routing options updated to match the simulation results.
  - DD-07 corrected: MCU supply diode RB521S30, CS_OUT on ADC0 AIN6, IND as plain GPIO.
  - Render and requirement notes updated.
- **Routing checkpoints:** the manifests again keep their capture-time hashes, with later changes as
  `source_revisions` entries (newest last). A re-capture had overwritten the capture block.
- **New decision:** DD-27 (evaluation board first).


### 2026-10-25: owner decisions recorded
- **Owner choices:** evaluation board first (compact parked as a routing draft); efficiency deviation
  accepted (REQ-PWR-02 ≥ 94 %, DD-26); 4.0 A kept (DD-13).
- **Changes:**
  - `parameters.yaml` gains `current.efficiency_target_pct`, which the calculation reads; the efficiency
    check now passes (94.59 %).
  - REQ-OUT-01 is VERIFIED-SIM and REQ-PWR-02 is VERIFIED-CALC.
  - The T1.7 target was updated.
- **Evidence regenerated:**
  - ERC 0/0 on both schematics.
  - DRC: compact 0/3/20/0, evaluation 0/0/0/0.
  - Layout reviews, exports and checkpoint manifests regenerated.
  - Validation: the 2 remaining failures are compact routing and DRC. No order placed.

### 2026-10-25: compact routing options simulated
- **Router:** `grid_route.py` accepts optional per-layer rules (`layer_rules`: clearance, maximum width).
  The default behaviour is unchanged; the compact checkpoint was captured at 90f09b8.
- **Simulation on a copy of the placed copper:**
  - Moving U3's and C3's ground fanout vias removes the two unreachable MCU pins.
  - An MCU pin swap and 0.10/0.13 mm inner lines, alone or together, still leave about 19 nets clashing.
  - The table is in `engineering/compact-feasibility.md`. The board lacks routing capacity, not a better
    net order.

### 2026-10-25: compact board grid-routed to 20 open items
- **Grid router:**
  - `grid_route.py`: A* on a 0.05 mm grid over F/In2/B with through vias, against the exact placed copper.
  - Negotiates congestion between nets (PathFinder) and finishes with an exact segment clearance check.
  - `--partial` keeps the conflict-free nets; the generated `grid_routes` section is applied after the
    via fields.
  - Five tests.
- **Compact layout:**
  - No In2 VBAT pour; the F VBAT pour now covers every field via.
  - The MCU moved and rotated, with a part-free escape ring on both sides. Q6/D3/R20 sit by Q4/Q5.
  - C12 moved and U1's PGND has a plane via.
  - `place_opt` charges for nets that change side.
  - Router keep-outs are cut back around other nets' vias, and GND fanout vias stay out of other pours.
- **Result:**
  - DRC 0 errors / 3 warnings / 20 unconnected (was 0/6/31).
  - VOUT 1.46 mΩ, LD_P 0.47 mΩ.
  - Copper loss above the model +44 mW; ground-offset shift +0.75 %.
- **Schematic:** field placement for R/L/thermistor symbols fixed; both schematics regenerated (ERC 0/0).
- **Evidence:**
  - Evaluation DRC 0/0/0/0; both layout reviews and DRAFT exports PASS.
  - Compact routing checkpoint archived and evaluation manifest re-captured.
  - Validation: 147 tests, the same 3 known failures. No order placed.

### 2026-10-25: battery polarity decided and marked on the boards
- **Owner decision:** polarity does not matter provided the board marks it. The definition stays centre spring = B+,
  ring = B− (DD-12); REQ-BAT-04 is DESIGNED (was BLOCKED).
- **Silkscreen:**
  - compact: new `texts:` "B+" beside the spring pad and "B-" beside the ring (bottom), plus "B-" on top;
  - evaluation: label strokes raised from 0.12 mm to PCBWay's legend minimum (MFG-01).
  - Both were applied by finish on the archived router sessions, so no copper changed. Checkpoint
    manifests were re-captured.
- **Pipeline:**
  - `add_texts` now replaces board labels, so a changed stroke takes effect.
  - Router keep-outs take a `net` and are cut back around vias of other routed nets. A via inside a
    keep-out was an unfixable router violation.
- **Docs:** schematic title block, assembly instructions, stack-up note, export README text, AGENTS.md rule 4
  and the test plan (T3.3) updated.
- **Evidence:**
  - ERC 0/0 on both schematics.
  - DRC: evaluation 0/0/0/0; compact 0/6/31/0 (unchanged).
  - Both layout reviews and both DRAFT exports PASS.
  - Validation: 142 tests. Evaluation Gate F is PASS; the 3 known failures remain (efficiency, compact
    routing/DRC). No order placed.

### 2026-10-25: compact re-floorplan around the spring-pad via keep-out
- **Placement (DD-24):**
  - L1 now covers the spring pad and U1 sits 2 mm below, with source escapes for every pin: non-crossing
    BOOT1/SW1 lanes, BOOT2 over C7, VCC 0.6 mm to C7.
  - J3 uses 3.5 mm pads on the compact variant only.
  - Q1 sits under Q2 with an 8-via VBAT field, and Q3 moved right for the SW1 vias.
  - The MCU moved to the bottom lower left.
- **Pipeline:**
  - Source vias are reserved on both sides during automatic placement.
  - `router_keepouts` add rule areas that keep the autorouter off the power pours; finish deletes them.
  - `place_opt.py` is a new simulated-annealing small-part placer.
  - Six tests cover keep-outs, via reservation and the optimiser.
- **Result:**
  - Compact KiCad DRC is 0 errors, 6 warnings, 31 unconnected (was 0/3/43). Every power path is connected
    (VBAT 0.50 mΩ, VOUT 1.69 mΩ).
  - The PGND link remains weak: the review shows a +1.14 % worst-case setpoint shift.
  - A finish-stage GND via fix collided with routed copper and was reverted.
- **Evidence:**
  - Routing checkpoint archived.
  - Both schematics ERC 0/0; evaluation DRC 0/0/0/0.
  - Both layout reviews and both DRAFT exports PASS.
  - Validation: 137 tests; the same 3 known failures. No order placed.

### 2026-10-25: power-layout review from the routed copper
- New `automation/review/`:
  - KiCad-side copper extractor;
  - exact scanline raster model (Pillow's fill widened every shape by a cell);
  - DC current-flow solver checked against analytic cases (strip, parallel layers, barrel formula, necks,
    open paths);
  - review report covering power paths, ground offsets and setpoint error, hot loops, gate/boot/VCC loops,
    Kelvin pair, sensitive-net spacing and vias near power pins.
- The validator adds `VAL-LAYOUT-<variant>`, a freshness check only. Findings are dispositioned in
  `engineering/layout-review.md` (DD-23).
- Evaluation board:
  - Found a 0.55 mm SW1 junction carrying the whole inductor current, plus VOUT and LD_P necks.
  - Corrected the pours in source and re-applied them to the archived session; DRC still 0/0/0/0.
  - SW1 1.91 → 0.98 mΩ, VOUT 3.01 → 2.27 mΩ, LD_P 1.28 → 0.88 mΩ; copper loss above the model fell from
    142 to 96 mW.
- Documented with bench checks T2.9–T2.12:
  - package-limited items (DD-16: SW2 entry, AGND/PGND +0.28 % DC setpoint shift);
  - buck-leg drive loops;
  - VCC through In2;
  - the U1 ISP/ISN branch.
- Compact draft review recorded its gaps: open VOUT path, single-via VBAT transition, isolated U1 pin 15,
  FSW/COMP_RC 0.15 mm from switching copper.
- Root cause for the compact draft: 23 of U1's 26 pads lie inside the spring-pad via keep-out. The
  placement options are recorded in `engineering/compact-feasibility.md`; the compact CAD is unchanged.
- Copper allowances of the loss model moved to `parameters.yaml`. The loss dict merge is now sorted, so
  `power-stage-results.json` is identical across hash seeds; values are unchanged.
- Regenerated the evidence:
  - schematics: ERC 0/0, netlists exact;
  - both DRCs: evaluation 0/0/0/0, compact 0/3/43/0;
  - both layout reviews;
  - both DRAFT exports: PASS.
- Validation: 131 tests pass; 3 known failures (efficiency, compact routing/DRC). No order placed.

### 2026-10-24: completed evaluation CAD, hardened evidence and generated review packages
- Evaluation board: all 68 footprints placed, all nets connected, repeated KiCad DRC 0/0/0/0. Explicit
  MCU/PG/ground escapes and source-defined BOOT1/SW2/ILIM corrections resolve the trapped connections.
- Compact board: corrected bottom transforms, copper-only fanout, ring edge margin and capacitor spacing;
  final DRC 0 errors / 3 connection-width warnings / 43 unconnected / 0 parity. The current compact placement
  remains a routing draft; no feasibility or production claim was inferred from zero geometric errors.
- Native project symbol derivatives keep verified custom footprint filters compatible with clean ERC.
- Router minimum-width and ground-layer settings are explicit. Repeated finish is idempotent; native
  deletions fix KiCad SWIG ownership failures, and project settings are preserved with atomic writes.
- Tool failures, malformed/stale reports, source races, omissions and incomplete routes cannot pass the gate
  computation. DRC/export evidence binds placement, connectivity, parameters and actual CAD bytes. Export
  artifacts are independently checked and hashed; Git preserves those exact bytes.
- Both DRAFT PCBWay packages internally pass; all PDFs/images and signed centroid data checked. Rendering
  has no component-body/height verification. Stack-up/assembly notes and a safer unspecified rated dummy-load
  selection replace the unsupported example in the earlier bench plan.
- Toolchain doctor passes; 120 Python tests pass; firmware 26/26 checks and target build pass. Global validation
  truthfully exits 1 for the efficiency target plus compact routing/DRC; battery polarity remains BLOCKED.
- Exact router checkpoints archived; safe review packaging excludes tools, downloads, caches and failed
  staging directories and records file hashes plus actual gate states. Actual DRAFT bundle smoke test: 249
  members, no missing review files, valid ZIP CRC and per-file hashes. No order or manufacturing release.


### 2026-10-24: recovered Claude routing checkpoint and audited handoff
- Preserved unfinished `floorplan.py`, geometry export, compact PCB, project rules and latest DRC report.
- Actual checkpoint: 65 placed footprints, 33 unconnected items, 91 DRC errors (50 undersized tracks, 40 ring edge violations, one courtyard overlap), 44 warnings and six Datasheet field mismatches.
- Existing Python tests: 11 passed. The previous entry-script/export milestone had not updated this handoff or the requirement register.
- Validation audit found that Gate E omitted routing/ERC and Gate F could consequently pass an unrouted board. Fixing the evidence and release dependencies is active work; no release is approved.
- No Git remote is configured; commits are local until a destination is supplied.

### 2026-10-24 (evening): library, schematic, simulation, firmware, PCB pipeline
- **Library:**
  - TPS552882 footprint from calibrated PDF vector extraction.
  - 1206 Kelvin shunt footprint with net tie.
  - Segmented ring contact.
  - Spring and test pads.
  - Symbols from verified pin tables; PowerPAK MOSFET symbols renumbered to the footprint pads.
- **Schematics:** generated for both variants. ERC 0/0 and netlists equal the spec. Per-variant footprints and
  MPNs: Variant A uses 0201 parts and fewer test pads (DD-17).
- **Simulation:** cycle-averaged behavioural model in ngspice 47. 11 tests PASS after fixing a model bug (the INA186
  output impedance) and unrealistic test stimuli.
- **Firmware:** ATtiny1616, avr-gcc 15.2.0 build, TinyCC host unit tests.
- **PCB pipeline:** pcbnew API placement with an automatic small-part placer, automatic via fields (no via-in-pad)
  and GND fanout, DSN → FreeRouting (jar) → SES, pours, DRC with schematic parity, dangling-via cleanup.
- **Lessons recorded in the code:**
  - `SaveBoard()` overwrites `.kicad_pro` rules, and `LoadBoard()` does not resolve net classes; both are
    re-applied through the API.
  - Annular custom pads break Specctra export, so the ring is segmented.
  - Pad bounding boxes mislead hit tests for the ring; use real shapes (`pad.HitTest`).

### 2026-10-24: research, architecture, calculations (commit 862e82d)
- Workspace was empty and not a git repo; initialised `main`. The previous design files named in the brief are not
  on this machine. The concept was audited from the brief (`engineering/previous-design-audit.md`); every proposed
  part fails a datasheet limit.
- Machine: Windows 10 Pro 22H2 x64, i5-7300U, 16 GB RAM. Non-admin account, so all tools are per-user or project-local.
- Installed:
  - KiCad 10.0.6 (winget, user scope)
  - ngspice 47
  - Temurin JRE 25.0.4.1 + FreeRouting 2.5.0 jar (the native CLI crashes)
  - InteractiveHtmlBom 2.12.0
  - Python venv
- Verified:
  - Schematic writer: KiCad ERC and netlist export agree with intended connectivity at all four rotations.
  - pcbnew → DSN → FreeRouting → SES → KiCad DRC round trip: 0 violations, 0 unconnected.
- Five parallel research tasks (laser, converters, components, batteries/mechanics, PCBWay/CAD) hit the account
  usage limit once. They were resumed with bounded budgets and completed.
- Architecture A (TPS552882) selected over a TPS61288 boost with clamp, the TPS552892, and the XL6009.
