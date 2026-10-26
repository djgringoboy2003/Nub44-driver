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
