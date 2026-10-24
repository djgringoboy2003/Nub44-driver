# Progress

## Current state (handover)

_Last updated: 2026-10-24 (Codex continuation; evaluation CAD and review exports complete)._

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
and mirrored into the requirement register by the validator. `scripts/validate.ps1` currently returns 1
because the efficiency target and compact routing/DRC checks are unresolved, while all 120 Python tests pass.

**Design and deliverables:**
- TPS552882 constant-current architecture and all hardware protections retained; default setpoint remains 4 A.
- Both native KiCad projects are committed. The evaluation board is 45 x 40 mm, four layers, 68 footprints
  and 13 labelled test points. Repeated finishing/DRC preserves its clean result.
- The compact board has 65 footprints. Its corrected geometry has no DRC errors or parity findings,
  but three connection-width warnings and 43 incomplete connections remain. See
  [the compact assessment](engineering/compact-feasibility.md).
- Firmware: 26 host checks pass; ATtiny1616 target build succeeds with warnings treated as errors
  (approximately 2.4 kB flash image).
- Calculations: 20 of 21 pass. Current estimated efficiency is 94.5883% at 4 V against a greater-than-95% target;
  actual efficiency remains unmeasured.
- Both `manufacturing/pcbway/<variant>/` review packages pass source/artifact hash, output inventory,
  BOM/centroid and ZIP checks. Each has 31 artifacts, 48 BOM lines / 53 BOM parts and 52 centroid rows.
  All PDFs open; all PNGs verify. Renders show board geometry without resolved component bodies.
- Assembly instructions, stack-up note, dummy-load-first bench plan and final review report are under
  `documentation/`. Source-defined routing checkpoints (DSN/SES/manifests/instructions) are archived in
  `hardware/<variant>/routing/` so the exact current route can be restored from Git.
- `doctor`, `build`, `validate`, `export-pcbway` and DRAFT `package` entry points exist. The toolchain doctor passes.

**Owner decisions / open limitations:**
1. REQ-BAT-04 remains BLOCKED: working contact polarity is centre spring B+, ring B-. Evaluation Gate F is held.
2. Default 4 A remains the brief's setpoint and the documented diode-life risk (DD-13); alternate selection
   requires an owner decision and the matching divider/calculation update.
3. The current efficiency estimate misses its target; review losses/rework or document an accepted deviation.
4. Supplier availability, unverified prices and physical measurements remain UNKNOWN.
5. Evaluation power-layout review and bench validation remain open. Clean DRC does not verify switching
   waveforms, power-neck temperature, thermal coupling or host fit.
6. No Git remote is configured. Commits are local; a GitHub destination was requested asynchronously.

## Next actions (in order)

1. Confirm owner polarity before any Gate F release. Resolve the current/efficiency decisions as appropriate;
   no part value or requirement has been silently relaxed.
2. Review evaluation gate/boot loops, Kelvin/feedback isolation, power necks and thermal paths against the
   source datasheets. Use `hardware/evaluation-board/LAYOUT.md` and the actual CAD/assembly package.
3. After CAD/owner release, assemble an evaluation prototype and execute `documentation/testing/test-plan.md`
   using a rated dummy load first. Record measured data; only bench evidence can close Gate G.
4. Rework compact placement and explicit fanout using `engineering/compact-feasibility.md`. Do not rerun the
   same autoroute expecting a different conclusion or waive its remaining findings.
5. Verify supplier stock/prices and proposed alternatives; retain UNKNOWN until evidence is available.

**Commands and routing replay:**
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\doctor.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\validate.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\export-pcbway.ps1 -Variant evaluation-board
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\package.ps1
```

The per-process PowerShell flag is needed on this machine; no system policy was changed.
For exact route restoration, follow `hardware/<variant>/routing/README.md`. A new `build.ps1` or
`build_pcb.py --stage all` reroutes and may change geometry; exact post-route selectors then need fresh
DRC and power-path inspection. Successful exports and review ZIPs never place orders.

## Log

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
