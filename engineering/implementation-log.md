# Implementation log

Chronological record of the audit work on branch `audit/comprehensive-improvements`. Each entry lists what
changed, the tests run with their actual results, and what remains. Issue IDs refer to
[reports/comprehensive-project-audit.md](../reports/comprehensive-project-audit.md).

## 2026-10-26: baseline and audit

- Branch `audit/comprehensive-improvements` created from `main` at 3d04793 (clean tree, no user changes to
  preserve).
- Baseline: 147 Python tests pass; firmware 26/26 host checks and the ATtiny1616 build pass; the committed
  validation register shows the two known compact-board failures.
- Created the audit register, risk register, roadmap and this log.

## 2026-10-26: firmware safety and testability (roadmap phase 1)

- **Datasheet checks** found two further defects in the hardware layer: the DAC2/AC2 reference was written to
  `VREF.CTRLC` instead of `CTRLD` (power-loss trip near 0.57 V instead of 2.6 V, AUD-FW-19), and DAC2 stopped in
  standby (AUD-FW-20). The 2.5 V reference was used below its 2.9 V VDD minimum (AUD-FW-04).
- **Restructured** `firmware/src`: `hal.h`/`hal_avr.c` (registers and ISRs only), `fw.c` (start-up, supervision
  cycle, hold-up), `app.c` (state machine), `conv.c` (ratiometric measurements, NTC classification), `holdup.c`
  (gap logic), `fuses.h`. Decisions recorded as DD-28; no protection threshold, setpoint or hardware changed.
- **Fixed:** AUD-FW-01…15, 17, 19, 20; AUD-FW-16 mitigated (fuse values defined and checked at start-up; programming
  stays manual). AGENTS.md control characters (AUD-DOC-01) and the firmware README (AUD-DOC-02).
- **Tests added:** `test_app.c` (110 checks), `test_app` with `APP_LASER_NTC_REQUIRED=1` (2), `test_conv.c` (297),
  `test_holdup.c` (16), `test_fw.c` against a scripted HAL (41), `test_hal.c` register model of `hal_avr.c` (65);
  `tests/test_firmware_build.py` (mock constants equal the avr-libc header, every test file is built, mutant
  patterns still match).
- **Build driver:** `firmware/build.py` replaces the compile commands in `build.ps1` and `validate.py`; it writes
  `reports/firmware-evidence.json`.
- **Results (actual):** six host suites, 531 checks, 0 failures; ATtiny1616 build PASS with `-Werror`, 4134 B flash,
  59 B RAM; mutation check 15/15 killed.
- **Found on the way:** the agent shell collapses `\\` inside heredocs, which is how AGENTS.md acquired BEL/BS/TAB
  bytes; text with backslashes is now written with file tools, and a repository hygiene test is planned.
- **Bench items added:** T0.4 (fuses), T1.11 (measurement chain), T2.13 (sensor faults); T1.8/T1.9 extended.

## 2026-10-26: evidence, validation and release controls (roadmap phases 2 and 3, part)

- **Evidence manifests** (`automation/nubm44/evidence.py`): calculations (`power-stage-evidence.json`) and simulations
  (`simulation/results/evidence.json`) record input/output hashes, tool versions and the expected check or SIM list.
  The validator re-hashes them and re-judges every saved status (AUD-VAL-01/02/03); both generators exit 1 on failure.
- **Calculation fix:** inductor RMS now includes ripple (7.42 A, was 7.39 A; limit 12.8 A). Layout reviews regenerated
  (only their calculation hash changed).
- **Simulation:** SIM-11 is now a frequency-response analysis of the ngspice deck (injection between the CSA output and
  R8, 16 frequencies plus refinement, three corners): PM 114.2/121.0/121.9 deg, GM 12.6/12.4/11.9 dB; the Python model
  differs by -12.7 % in crossover and -5.0 deg in PM at 3.7 V. SIM-12 (new) sweeps 11 tolerance/assumption cases:
  10 pass; the combined worst case gives GM 9.5 dB (AUD-SIM-04, owner decision pending; R4 1.2 -> 1.0 kOhm explored in
  a scratch run only: 11.1 dB). SIM-08 cites ILIM_PK. Run time about 2.5 min.
- **Validator:** modes full/fast/eval-cad/compact-cad/manufacturing/bench; `--rerun-stale`; `--strict`;
  `engineering/known-limitations.yaml` baseline (exit 0 only when every failure is an unchanged known item); gate
  evidence classes; Gate G reads `reports/bench-summary.json`.
- **Release controls:** `automation/export/release_check.py` with DRAFT_REVIEW / PROTOTYPE_CANDIDATE /
  MANUFACTURING_RELEASE, human reviews in `engineering/release/design-reviews.yaml` and signed approvals in
  `manufacturing/approvals/`. Exports of an incomplete board are classed DRAFT_REVIEW_INCOMPLETE_BOARD and carry
  `DO_NOT_FABRICATE.txt` in the fabrication ZIP. Both packages re-exported (Gerber/drill changes are KiCad
  creation timestamps only).
- **Tests added:** `tests/test_evidence_and_readiness.py` (21 tests).
- **Results (actual):** 174 Python tests pass; `validate.py` exit 0: 55 entries, 3 known unchanged (compact routing,
  compact DRC, SIM-12 pending); gates A/B/C PASS, D/E/F evaluation PASS, compact OPEN, G OPEN; readiness: both boards
  DRAFT_REVIEW (evaluation needs the five human reviews for PROTOTYPE_CANDIDATE).
- **Deferred:** schematic-summary hashes (AUD-VAL-08) and variant-specific BOM descriptions (AUD-MFG-03) wait for the
  next CAD regeneration.

## 2026-10-26: sourcing verification (roadmap phase 3)

- `sourcing/build_sourcing.py` split into `compute()` and `build()` (CSV output byte-identical).
- New `sourcing/check_sourcing.py` (validator entry VAL-SRC, PROTOTYPE_CANDIDATE requirement): stale CSV detection,
  MPN size/dielectric/voltage decoding against footprint and description, capacitor voltage derating per net,
  resistor power in normal operation and single faults, rating table against parameters.yaml, data age, datasheet
  links, non-drop-in alternates. Reports `sourcing/sourcing-check.md/.json`.
- **Result (actual):** PASS, 0 FAIL, 29 WARN (26 compact description mismatches = AUD-MFG-03; C14 10 V vs 7.3 V fault
  level < 1.5x; R16 80 mW in a pad short = new AUD-SRC-04), 72 INFO.
- **Tests:** `tests/test_sourcing_check.py` (10).

## 2026-10-26: bench-test recording framework (roadmap phase 4)

- `documentation/testing/bench-tests.yaml`: machine-readable pass criteria for the 34 tests of the bench plan, with
  conditions (for example efficiency at 4.0 V and 3.0 V), the variants each test is required for, and links to the
  predictions (calculation results, calculation checks, simulation metrics).
- `automation/bench/bench.py`: `template`, `import-csv` (copies raw files into `raw/`, records SHA-256, refuses to run
  without `--measured`), `check` (validates every record, judges against the catalogue, writes
  `reports/bench-summary.json` and `reports/bench-report.md` with predictions beside the measurements).
- The validator refreshes the summary in full/manufacturing/bench modes; Gate G and MANUFACTURING_RELEASE read it.
- **Result (actual):** no records exist; Gate G NO DATA for both boards (29 required evaluation tests, 23 compact).
- **Tests:** `tests/test_bench.py` (11, synthetic records in temporary folders; none written to the project).

## 2026-10-26: engineering status dashboard (roadmap phase 4)

- `automation/dashboard/build_dashboard.py` writes `reports/dashboard/index.html`: one self-contained page (inline CSS,
  SVG and a small tooltip script; no network) built only from the evidence files and the audit/risk registers:
  overview tiles, decisions and human reviews required, per-board gates and blockers, release gates with evidence
  class, current test results, estimated efficiency (prediction), simulation table, SIM-11 loop gain, SIM-12 gain
  margin per case, open findings and risks, sourcing and cost summary, required bench tests, computed next actions.
  Light and dark themes; tables behind every chart. The validator regenerates it in full mode.
- Rendered with headless Edge and inspected; label collisions fixed.
- The dashboard showed three findings fixed but still marked OPEN in the audit (DOC-01, DOC-03, PROC-01): corrected.
- `tests/test_dashboard.py` (generated from evidence; missing evidence shows UNKNOWN and no PASS badge) and
  `tests/test_repo_hygiene.py` (no control characters, UTF-8 text) added.

## 2026-10-26: continuous integration and schematic evidence (roadmap phase 4)

- `.github/workflows/ci.yml`: a portable Linux job (pytest; `firmware/build.py --host-only --mutation` with gcc;
  `validate.py --mode fast`) and a Windows job (avr-gcc 15.2.0 and TinyCC fetched with the SHA-256 pins of
  `scripts/setup.ps1`; host tests, ATtiny1616 build, mutation check). KiCad, FreeRouting and ngspice runs stay local;
  CI re-hashes their committed evidence. The validator's known-limitations baseline lets CI fail only on new or
  changed failures. **Not yet run on GitHub** (no push in this session).
- Schematic evidence is now hash-bound (AUD-VAL-08): `build_schematic.py` writes a manifest; the existing evidence
  was migrated with `validate.py --attest-schematic` after its legacy mtime check passed (schematics not regenerated).
  Without this, a fresh CI checkout would have produced arbitrary modification-time failures.
- `firmware/tests/hal_mock.c`: loop counter made 32-bit (found by an avr-gcc warning proxy for gcc).
- **Results (actual):** 202 Python tests pass; with KiCad hidden 181 pass and 18 skip; `validate.py --mode fast`
  exit 0; avr-gcc `-O1 -Wall -Wextra -Werror` proxy compile of every host source clean.

## 2026-10-26: PCB review and documentation (roadmap phase 5)

- `engineering/pcb-review-2026-10-26.md`: independent review of the evaluation-board items (DR1H via, U1 ISP/ISN pair,
  C5, VCC, SW2 entry, AGND/PGND, package-limited heat) with options, trade-offs and the recommendation to order the
  first prototype unchanged; compact-board strategy table (HDI, 6-layer, re-architecture, fewer parts, two-board
  stack, larger outline) and the finding that PG is unused (one open compact item removable). New risk R-22 (ISP/ISN
  pickup could cause nuisance fault 6).
- New documents: `documentation/developer-guide.md` (architecture, fresh clone to prototype candidate, commands,
  validation modes, troubleshooting, recovery) and `documentation/release-checklist.md`.
- Updated: README (status, commands, readiness), AGENTS.md (repository map, regeneration order, validator baseline,
  bench rule, pitfalls), PROGRESS.md (current state and next actions rewritten), requirements (REQ-MFG-01/03,
  REQ-SRC-01), assembly instructions, test plan recording section, final report (superseded statements marked).
- The README edit hit the heredoc backslash hazard again (control characters in two paths); the hygiene test caught it
  and the paths were fixed.
