# Progress

## Current state (handover)

_Last updated: 2026-10-28 (GBP/UK sourcing follow-up to the pre-order and quote review on `10a29cc`; see Log). The independent audit (branch `audit/comprehensive-improvements`) is merged into `main`
and pushed. The electrical design, the 4.0 A setpoint, every protection threshold and both boards' copper are
unchanged; firmware, evidence handling, release controls, ordering files and tooling changed._

| Gate | Status | Evidence |
|---|---|---|
| A Research | PASS | Research/requirement documents |
| B Electrical design | PASS | Both schematics: ERC 0/0; exact connectivity comparison; hash-bound evidence |
| C Simulation | PASS (model-level) | SIM-01…11 pass in the averaged ngspice model; SIM-11 is now a frequency-response analysis. SIM-12 (tolerance sweep, outside Gate C) has one open finding |
| D Routing | Evaluation PASS; compact OPEN | Evaluation fully connected; compact has 20 unconnected items |
| E ERC/DRC | Evaluation PASS; compact OPEN | Evaluation 0/0/0/0; compact 0 errors / 3 warnings / 20 unconnected / 0 parity |
| F Manufacturing files | Evaluation PASS (internal consistency); compact OPEN | DRAFT packages only; the compact ZIP carries DO_NOT_FABRICATE.txt |
| G Physical validation | OPEN | No bench records (`reports/bench-report.md`); only measured data can close it |

**Release readiness:** **DRAFT_REVIEW; hold payment pending footprint dispositions.** Independent AI review of
`fab63177bd7086457878a5da7a13dc7cc917e8c3` is in `reports/pre-order-review.md`. Evaluation FP-U1, FP-L1 and
ORIENT are recorded DONE; FP-POWERPAK and FP-RS1 remain OPEN. U3's land-pattern difference also requires DFM
disposition (AUD-PCB-06). Compact reviews remain OPEN. AUD-VAL-11/12 identify missing-ID and stale-review
weaknesses in release checks. The owner decides whether AI review is sufficient. Release reports were
regenerated after merging the review (2026-10-28): the evaluation board has 2 blockers to PROTOTYPE_CANDIDATE
(FP-POWERPAK, FP-RS1); rerun the full toolchain after any disposition or fix.

**Ordering (prepared, not placed):** `documentation/ordering-guide.md` gives the files, layer order (L1 `.gtl`,
L2 `.g1`, L3 `.g2`, L4 `.gbl`) and order-form options for PCBWay (`manufacturing/pcbway/evaluation-board/`,
preferred for assembly) and JLCPCB (`manufacturing/jlcpcb/evaluation-board/`, derived with identical Gerber bytes).
Key options: 4 layers, 1.6 mm, **1 oz inner and outer copper**, **ENIG**, assembly top side only (29 parts, 52
placements), X-ray of U1/U3, no unreviewed substitutes. The pre-order review brief for Codex (or a person) is
`documentation/pre-order-review.md`, with the footprint geometry in `reports/footprint-review.md`.

**Quote/sourcing review:** `reports/bom-quote-sourcing-review.md`, per-line `reports/bom-sourcing-options.csv`.
QUOTE-01 matches all 30 BOM lines, exact MPN suffixes and J1 DNS; arithmetic correct. Five-board stored total
304.615, dollar-format cells but ISO currency UNKNOWN. L1 is 126.790 (50.79% of components); cause UNKNOWN,
request exact-MPN reprice. Owner currency GBP: conditional USD quote equivalent £229.25 (FX-01); quote ISO
still UNKNOWN. Native GBP distributor snapshots, quantities, UK eBay findings and proposed packing-only
alternatives are now recorded in the report/CSV. Exact Coilcraft L1 reference converts to £1.97 each before
unknown freight/tax/handling; current UK stock/delivered offer UNKNOWN. No cheaper electrical straight swap
approved. AliExpress Choice offers remain UNKNOWN. Three-assembly and consignment totals need PCBWay quotes; published minimum 5 and conflicting attrition rules need written
clarification.
Recommend revised turnkey; genuine L1-only consignment is the fallback to quote. Diode PREORDER-09/10/11 are
now saved locally with hashes. No design/CAD/export change. Dashboard missing board scope is new AUD-DOC-05.

**Validation:** full-toolchain rerun for this review on `10a29cc` (2026-10-28, KiCad, ngspice and avr-gcc present): exit 0,
57 entries, 54 PASS and 3 known, unchanged failures listed in
`engineering/known-limitations.yaml`: compact routing and compact DRC (accepted, DD-27) and VAL-SIM-12 (pending an
owner decision, AUD-SIM-04). Any new or changed failure makes it exit 1.

**Tests (2026-10-28, full toolchain for review based on `10a29cc`):** 207 Python tests pass (the independent review saw 188 pass /
19 skip without KiCad). The regenerated firmware evidence and footprint report match the committed ones except
timestamps, and the evaluation PCB, connectivity and PCBWay package match the review's SHA-256 baseline. Firmware:
six host suites with 531 checks, register-model tests of `hal_avr.c`, ATtiny1616 build 4134 B flash / 59 B RAM with
`-Werror`, mutation check 15/15. Calculations 21/21. Simulations 11/12 (SIM-12 finding). Sourcing check 0 FAIL / 29
WARN. GitHub CI passed on the parent commit; see run 40500901442 below.

**Audit outcome** (`reports/comprehensive-project-audit.md`): 60 findings (11 high, 31 medium, 17 low, 1 info); 41 fixed, 2 mitigated, 11 documented, 6 open. Pre-order findings: AUD-VAL-11/12, AUD-PCB-06, AUD-DOC-04/05. The last is a dashboard display defect; real evaluation blockers remain two.
- **Firmware (DD-28):** fixed a board-NTC failure that silently disabled thermal protection, a watchdog cleared even
  when the tick stopped, watchdog resets that re-armed emission, the 2.5 V reference used below its VDD minimum, the
  AC2 power-loss reference written to the wrong register (the click mode change could not work), missing debounce,
  hold-up races and more. The firmware is untested on hardware.
- **Evidence:** calculations, simulations and schematics are now hash-bound with tool versions; stale or edited
  evidence fails.
- **Release controls:** DRAFT_REVIEW / PROTOTYPE_CANDIDATE / MANUFACTURING_RELEASE levels with human reviews, bench
  evidence and signed approvals; incomplete boards are marked inside their fabrication ZIP.
- **New tooling:** sourcing verification, bench-test recording (`automation/bench/bench.py`), status dashboard
  (`reports/dashboard/index.html`), CI.

**Owner decisions in force:** battery polarity centre spring = B+, ring = B−, marked on both boards (DD-12); 4.0 A kept
(DD-13); efficiency target ≥ 94 % (DD-26); evaluation board first, compact parked (DD-27).

**Decisions now required from the owner:**
1. **AUD-SIM-04 / VAL-SIM-12:** the averaged model shows 9.5 dB gain margin (< 10 dB) when four tolerances stack.
   Either accept and measure the loop on the prototype, or change R4 (Rc) 1.2 → 1.0 kΩ (exploratory simulation:
   11.1 dB worst case). A hardware change; not applied.
2. **AUD-SRC-04:** R16 (indicator resistor) is overloaded if the external LED pad is shorted; consider a larger
   package or value.
3. **AUD-PCB-04:** optional gate clamp for Q6 (VGSS ±6 V) in a later revision.
4. **Compact board direction** after bench data: HDI, 6-layer or re-architecture, plus removing the unused PG net
   (`engineering/pcb-review-2026-10-26.md`).
5. **Fab choice** (PCBWay preferred for assembly) and acceptance of the pre-order review results.

**Open limitations.**
1. HDI via-in-pad for the RPM0026A centre pads (DD-16) remains the remedy for the package-limited SW2, PGND and AGND
   items; it needs a fabrication quote and an owner decision.
2. Supplier stock and prices are partly UNKNOWN; compact BOM descriptions contradict their 0201 MPNs (AUD-MFG-03,
   fix deferred to the next CAD regeneration because it invalidates the DRC/export evidence of both boards).
3. Waveforms, temperatures, efficiency, fault response, the firmware's hold-up timing and its measurement chain are
   unmeasured until Gate G.
4. The averaged simulation model has no switching ripple, saturation or dead time; its inner-loop gain is an
   assumption.
5. Remote `origin` is the private repository https://github.com/djgringoboy2003/Nub44-driver; `main` includes the
   audit work. CI (`.github/workflows/ci.yml`) passes on GitHub (run 40500901442, 2026-10-27): Linux 188 tests pass
   and 19 skip without KiCad, gcc host tests and mutation check pass, fast validation exits 0 with the 3 known items;
   Windows pinned-toolchain target build and mutation check pass.

## Next actions (in order)

1. **Resolve the pre-order review:** `reports/pre-order-review.md`. Correct or obtain assembler acceptance for
   RS1, U3 and PowerPAK-8S lands; fix AUD-VAL-11/12 and Q1's source link; address R16 and decide R4/Q6. Rebuild
   all affected CAD/export evidence, repeat affected reviews and full validation. Evaluation still has two
   OPEN review records. Review entries are scoped separately from the parked compact board.
2. **Owner quote confirmation:** `reports/bom-quote-sourcing-review.md` questions for PCBWay: ISO currency and
   firm GBP payable total, current exact-MPN consolidated distributor/Coilcraft UK quotes before any purchase,
   L1 exact-MPN reprice, final U1 price, UK delivered costs/X-ray scope, 3 populated + 2 bare quote, and optional
   genuine L1 consignment counts/leader/fees/shipping. Do not buy unverified Choice parts or assume 29 assembly
   survives consignment. No order placed; owner decides and merges the review branch.
3. **Owner decisions** listed above. Any adopted component or footprint change requires regenerated order files and evidence.
4. **Evaluation prototype (owner, by hand):** `documentation/ordering-guide.md` and `documentation/release-checklist.md`
   sections A and B. No tool places orders.
5. **Bench testing:** program firmware and fuses (T0.4), then run `documentation/testing/test-plan.md` with a rated
   dummy load, recording each test with `automation/bench/bench.py`. Watch especially T1.8/T1.9 (hold-up and mode
   change, never tested before), T1.10 (CC polarity), T1.11 (measurement chain), T2.11 (loop, AUD-SIM-04) and nuisance
   fault 6 (R-22).
6. **Compact board:** with the bench data, choose its direction (`engineering/pcb-review-2026-10-26.md`), then re-run
   the compact chain (`grid_route.py --variant compact-22mm --rebuild --partial --write`; `place`, `route`, `finish`,
   `drc`; `power_layout.py`). Accept it only with 0 unconnected, 0 DRC errors and every power path connected.
7. **Next CAD regeneration:** variant-specific BOM descriptions (AUD-MFG-03); rerun the full chain.

**Commands:**
```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe firmware\build.py --mutation
.venv\Scripts\python.exe automation\validation\validate.py            # full; add --mode fast without KiCad
.venv\Scripts\python.exe automation\bench\bench.py check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\export-pcbway.ps1 -Variant evaluation-board
```

The per-process PowerShell flag is needed on this machine; no system policy was changed.
- After editing any source file, regenerate evidence in the order given in `AGENTS.md`.
- For exact route restoration, follow `hardware/<variant>/routing/README.md`.
- A new `build.ps1` or `build_pcb.py --stage all` run reroutes and may change geometry. Exact post-route
  selectors then need fresh DRC and power-path inspection.
- See `documentation/developer-guide.md` for onboarding, troubleshooting and recovery.

## Log

### 2026-10-28: GBP preference, UK suppliers/eBay and straight-swap investigation
- Owner requested sterling prices and UK/UK-eBay sources. Added FX-01 dated ECB conversion: USD 1 equals
  GBP 0.752582412647...; five-board quote £229.25 only if its UNKNOWN ISO currency is confirmed USD.
- Added native GBP primary-seller price snapshots and quantity-break/MOQ/spare comparisons to the existing
  report and all-30-line CSV; recorded cache age/direct-fetch failures, VAT, stock, dispatch and delivery limits.
  Current offers/complete landed totals UNKNOWN. Coilcraft has a verified UK sales/warehouse route, exact
  L1 stock and GBP delivered offer UNKNOWN. L1 reference £1.97 FX remains the main repricing opportunity.
- Inspected a Hampshire eBay precision-resistor listing (pack/UK postage UNKNOWN) and a Shenzhen MCU listing
  with Unbranded item specifics; neither establishes a better qualified purchase. No marketplace order/cart/login.
- Proposed INA186 A2 DCK packing-only T and TI's identical U1 .A alias; no adoption. XAL5030-102MEC has higher
  DCR/lower thermal-current capability and a higher manufacturer reference price, so is not recommended to save.
- Recommendation remains exact-MPN turnkey reprice, genuine L1-only consignment fallback after a written
  PCBWay parts count/tape/fee quote. Design/CAD/exports/generated sourcing CSVs and release reviews unchanged.
- Verification: 207 pytest tests passed in 17.42 s; full validator exit 0, 57 entries / 54 PASS / the same
  three known unchanged findings, no new/changed failures, two evaluation blockers; Gate G OPEN. Independent
  Decimal checks passed all GBP conversions and spare/MOQ/tier purchases. Seven baseline hashes and all
  protected source/CAD/export/generated-sourcing bytes still match. Dashboard regenerated by validator.

### 2026-10-28: full pre-order follow-up, private quote audit and sourcing options
- Review branch `review/bom-quote-sourcing`, base `10a29cc`. Downloaded the three missing manufacturer diode
  PDFs first; recorded local paths/revisions/SHA-256 in research/source-index.md. No downloaded code executed.
- Re-ran all three brief commands with the full toolchain: pytest 207 pass; firmware six suites/531 checks,
  4134 B flash/59 B RAM and 15/15 mutants; full validation exit 0, 57 entries/54 PASS/3 known unchanged.
  All seven reviewed PCB/connectivity/package hashes still match. Final reruns after documentation/review
  updates: pytest 207 passed in 18.92 s, full validator exit 0 with the same 57 entries/3 known/2 evaluation
  blockers. Quote checker rejects a temporary missing-suffix fixture; all protected sources/exports byte-identical.
- Rechecked local PowerPAK/Ohmite/Microchip documents. Exact RS1/U3 remedies and unresolved 8S acceptance
  recorded; FP-POWERPAK/FP-RS1 stay OPEN. Evaluation orientation local-diode follow-up recorded only for that
  board. New AUD-DOC-05: dashboard omits review board scope; generator unchanged, finding OPEN.
- Parsed QUOTE-01 original XLS with system Python -I and external temporary xlrd 2.0.2 (no requirements change).
  Added reproducible checker/JSON: all 30 lines match, all arithmetic reconciles; 304.615 stored total, ISO
  currency UNKNOWN despite dollar formats. L1 126.790 dominates; request reprice, cause UNKNOWN.
- Added 5/3-board line CSV, cost chart and report: turnkey/fewer assembled/partial consignment/home/genuine
  options, safety roles, explicit spare assumptions and unknown totals. No qualified AliExpress Choice UK
  offers/prices. PCBWay promotion/minimum/attrition conflicts and exact pre-payment questions documented.
- Original private quote committed with this review. Design sources, CAD/export files, generated sourcing
  CSVs and known-limitations baseline unchanged; Gate G OPEN. No order, login, cart or supplier message.


### 2026-10-28: fresh working copy verified with the full toolchain; review sources stored locally
- `scripts/setup.ps1` failed under Windows PowerShell 5.1 (`java -version` writes to stderr, which `2>&1` turns
  into a terminating error under `Stop`). Tool banners are now captured through `Get-NativeOutput`; setup runs
  cleanly under `powershell.exe` as documented.
- Full rerun on `480a69f`: doctor all OK; pytest 207 passed; firmware PASS, 15/15 mutants; `validate.py` exit 0,
  57 entries, 3 known unchanged; evaluation board 2 blockers (FP-POWERPAK, FP-RS1). All seven SHA-256 values in
  `reports/pre-order-review.md` section 9 match the local files.
- Downloaded PREORDER-01, 04, 05, 06, 08 into `research/datasheets/` (git-ignored) and listed every local copy in
  `research/source-index.md`. PREORDER-09/10/11 refused scripted download (HTTP 403); fetch them in a browser.
- No CAD, firmware, threshold or manufacturing file changed; no order placed.

### 2026-10-27: independent pre-order review
- Codex (AI review) compared manufacturer drawings, embedded footprints, assembly PDF, iBOM and centroids.
  Evaluation U1/L1/orientation DONE; PowerPAK and RS1 OPEN. RS1/U3 pad deviations and exact 8S compatibility
  require DFM disposition. Review is bound in prose to the baseline and exact package SHA-256 values.
- Added AUD-VAL-11/12 (missing review IDs and stale approvals), AUD-PCB-06 (land deviations) and AUD-DOC-04
  (Q1 source link). Four issues documented with remedies; no CAD, firmware or release-check code changed.
- Fixed the test review fixture to reset synthetic statuses explicitly; release-check assertions preserved.
- Actual checks: 356/356 Git blobs matched; pytest 188 passed/19 skipped; firmware six suites/531 checks and
  15/15 mutants; fast validator exit 0, three known failures, no new/changed failures. KiCad, ngspice and
  AVR target tools unavailable locally; full saved evidence retained. Gate G remains OPEN.
- PCBWay/JLC common Gerber/drill members identical; all 52 placements agree. Report committed on a review
  branch per the brief. Owner order decision remains pending.


### 2026-10-27: CI verified on GitHub
- First run (40497985197): Windows job passed; Linux pytest failed twice: gcc rejected unused static test functions in
  the `APP_LASER_NTC_REQUIRED` host build (TinyCC does not warn), and the footprint report needed KiCad. Fixed in
  4f608a9; second run (40500901442) passed both jobs.

### 2026-10-27: ordering files for PCBWay and JLCPCB; pre-order review pack; merged and pushed
- `documentation/ordering-guide.md`: files, layer order and order-form options for both fabs; assembly options.
- `automation/export/export_jlcpcb.py`: JLCPCB files derived from the checked PCBWay package (flat Gerber ZIP with
  identical bytes, JLC BOM with 9 of 29 part numbers recorded, JLC CPL); refuses incomplete boards; validator entry
  VAL-JLC-<variant> fails if the PCBWay package changes afterwards.
- PCBWay BOM fixed to one line per orderable part (30 lines; was 48), AUD-MFG-05; both packages re-exported.
- `automation/review/footprint_report.py` -> `reports/footprint-review.md` (pad tables incl. custom-pad outlines,
  nets, pin names, placement); `documentation/pre-order-review.md` brief for Codex.
- 207 Python tests pass; validator exit 0 (3 known items); firmware PASS. Merged into `main` and pushed. No order.

### 2026-10-26: audit follow-up: sourcing checks, bench framework, dashboard, CI, documentation (same branch)
- `sourcing/check_sourcing.py` (0 FAIL, 29 WARN; new finding AUD-SRC-04 on R16); `automation/bench/bench.py` with
  `documentation/testing/bench-tests.yaml` (MEASURED records only; Gate G NO DATA); `reports/dashboard/index.html`;
  `.github/workflows/ci.yml` (not yet run on GitHub); hash-bound schematic evidence.
- Documentation: developer guide, release checklist, PCB review (`engineering/pcb-review-2026-10-26.md`), README,
  AGENTS.md (map, regeneration order, pitfalls incl. the heredoc backslash hazard), requirements, assembly, test plan.
- 202 Python tests pass; validator exit 0 (3 known items); firmware PASS with 15/15 mutants. No order, no push.

### 2026-10-26: independent audit, firmware fixes, evidence binding and release levels (branch `audit/comprehensive-improvements`)
- **Audit:** `reports/comprehensive-project-audit.md` (single issue register), `engineering/risk-register.md`,
  `engineering/improvement-roadmap.md`, `engineering/implementation-log.md` (details and actual test results).
- **Firmware (DD-28):** board-NTC failure no longer disables thermal protection; watchdog cleared only after a full
  cycle; watchdog resets latch a fault; ratiometric measurements (the 2.5 V reference was used below its VDD
  minimum); the AC2 power-loss reference was in the wrong register (`VREF.CTRLD`), so the click mode change could
  not work; debounce, re-check of the start voltage, output-while-off detection, hold-up race fixes, fuse check.
  HAL split with host tests: 531 checks, 15/15 mutants caught; ATtiny1616 build 4134 B.
- **Evidence:** calculation and simulation results are hash-bound to their inputs and tool versions; SIM-11 is now
  a frequency-response analysis; SIM-12 sensitivity sweep found GM 9.5 dB at combined tolerances (AUD-SIM-04, owner
  decision pending).
- **Validation and release:** known-limitations baseline (exit 0 unless a failure is new or changed), modes,
  per-board readiness (both boards DRAFT_REVIEW), incomplete-board marker in the compact fabrication ZIP.
- No hardware, threshold or setpoint change; no order placed; nothing pushed.

### 2026-10-26: repository pushed to GitHub
- Added remote `origin` (private repository djgringoboy2003/Nub44-driver) and pushed all 16 commits of `main`.
  The remote matches the local branch.

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
