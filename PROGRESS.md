# Progress

## Current state (handover)

_Last updated: 2026-10-25 (Claude continuation; power-layout review of the routed copper)._

| Gate | Status | Evidence |
|---|---|---|
| A Research | PASS | Research/requirement documents; computed register |
| B Electrical design | PASS | Both schematics: ERC 0 errors / 0 warnings; exact connectivity comparison |
| C Simulation | PASS (model-level) | SIM-01 through SIM-11; behavioural averaged model, no vendor model |
| D Routing | Evaluation PASS; compact OPEN | Evaluation fully connected; compact has 43 unconnected items |
| E ERC/DRC | Evaluation PASS; compact OPEN | Evaluation 0 errors / 0 warnings / 0 unconnected / 0 parity; compact 0 / 3 / 43 / 0 |
| F Manufacturing files | Evaluation HELD (REQ-BAT-04); compact OPEN | Both DRAFT review exports internally PASS; no manufacturing release |
| G Physical validation | OPEN | Requires assembled-prototype measurements; cannot be closed by software |

The authoritative gate statuses are generated in [reports/validation-register.md](reports/validation-register.md)
and mirrored into the requirement register by the validator.

- `scripts/validate.ps1` returns 1 for three known reasons: the efficiency target, compact routing and compact
  DRC.
- All 131 Python tests pass.
- `VAL-LAYOUT-<variant>` checks that each power-layout review was generated from the current board.

**Power-layout review (new this session).**

The tool `automation/review/power_layout.py` reads the routed copper. It solves the DC current flow per
power net at the calculated operating points and measures the SLVSFC5 §10.1 layout geometry. It writes
`reports/layout-review-<variant>.md/.json` and figures. Dispositions and lessons are in
[engineering/layout-review.md](engineering/layout-review.md) (DD-23).

- **Evaluation board pours corrected.** Three source pours were re-applied to the archived router session.
  DRC is still 0/0/0/0 and every post-route selector matched.
  - SW1: the old 0.55 mm junction now meets the Q2 source pins along their height (1.91 → 0.98 mΩ).
  - VOUT: an In2 finger runs under U1's output column (3.01 → 2.27 mΩ).
  - LD_P: the pour is larger (1.28 → 0.88 mΩ).
- **Accepted with bench checks T2.9–T2.12:**
  - the package-limited SW2 entry (0.75 mm equivalent) and AGND/PGND arrangement (+0.28 % DC setpoint
    shift), both under DD-16;
  - the buck-leg DR1H/BOOT1 loops, which switch only in the transition region;
  - C7 (VCC) reached through In2;
  - the U1 branch of ISP/ISN.
- **Efficiency.** Routed copper adds about 96 mW over the loss model at 4.0 V. The estimate falls from 94.6 %
  to about 94.1 %, and REQ-PWR-02 stays AT-RISK. Copper allowances moved into `parameters.yaml`, and the
  calculation output is now deterministic: the same values with sorted keys.
- **Compact draft.** The review lists the gaps that the rework must close:
  - VOUT is not connected from U1 to the shunt;
  - the whole VBAT input current crosses one via;
  - U1 pin 15 is isolated from ground;
  - FSW and COMP_RC sit 0.15 mm from switching copper.

**Design and deliverables (unchanged unless noted):**
- TPS552882 constant-current architecture and all hardware protections retained; default setpoint remains 4 A.
- Evaluation board: 45 x 40 mm, four layers, 68 footprints, 13 labelled test points. Compact board:
  65 footprints, routing draft (`engineering/compact-feasibility.md`).
- Firmware: 26 host checks pass; ATtiny1616 target build succeeds with warnings treated as errors.
- Calculations: 20 of 21 pass. The efficiency check fails (94.5883 % against > 95 %); actual efficiency is
  unmeasured.
- Both `manufacturing/pcbway/<variant>/` DRAFT review packages were regenerated from the current boards.
  Each passes its source/artifact hash, inventory, BOM/centroid and ZIP checks.
- Assembly instructions, stack-up note, dummy-load-first bench plan (now with T2.9–T2.12) and final review
  report are under `documentation/`. The routing checkpoints in `hardware/<variant>/routing/` restore the
  exact sessions; the evaluation checkpoint records the 2026-10-25 pour revision.

**Owner decisions / open limitations:**
1. REQ-BAT-04 remains BLOCKED: the working contact polarity is centre spring B+, ring B-. Evaluation Gate F is
   held.
2. Default 4 A remains the brief's setpoint and the documented diode-life risk (DD-13). An alternate setpoint
   needs an owner decision and the matching divider/calculation update.
3. Efficiency misses its target: model 94.6 %, with routed copper about 94.1 %. The owner must accept a
   deviation, or loss rework is needed (lower-Rds reverse FET, copper, HDI via-in-pad).
4. HDI via-in-pad for the RPM0026A centre pads (DD-16) is the remedy for the package-limited SW2/PGND/AGND
   items. It needs a fabrication quote and an owner decision.
5. Supplier availability, unverified prices and physical measurements remain UNKNOWN.
6. No Git remote is configured. Commits are local.

## Next actions (in order)

1. Owner decisions: confirm polarity before any Gate F release; decide on the current setpoint, the
   efficiency deviation and the HDI via-in-pad option. No part value or requirement has been silently
   relaxed.
2. Optional evaluation improvements, each needing a new router session followed by DRC, the layout review
   and fresh post-route selectors:
   - move the DR1H via off the SW1 junction;
   - route U1's ISP/ISN as a same-layer pair;
   - move C5 nearer U1.
   Re-check every result with `power_layout.py`.
3. After CAD/owner release, assemble an evaluation prototype and execute
   `documentation/testing/test-plan.md`, starting with a rated dummy load. Record measured data; only bench
   evidence can close Gate G.
4. Rework the compact placement using `engineering/compact-feasibility.md` and the priorities in
   `engineering/layout-review.md`.
   - Start with the structural constraint recorded there: 23 of U1's 26 pads, 13 of them needing a via,
     lie inside the 2.95 mm through-via keep-out of the centre spring pad.
   - Preferred fix: move the L1/U1 column 2–2.5 mm off the spring pad, then add explicit U1 escapes
     before autorouting.
   - Accept the rework only when the current-flow report shows every power path connected and no
     single-via power transitions.
5. Verify supplier stock/prices and proposed alternatives; keep UNKNOWN until evidence is available.

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
