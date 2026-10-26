# Improvement roadmap

Ordered by safety, risk, dependency and development value. Issue IDs refer to
[reports/comprehensive-project-audit.md](../reports/comprehensive-project-audit.md). Nothing here changes the
4.0 A setpoint, a protection threshold or the protection topology; items that would are listed under "Needs owner
approval".

## Phase 1: firmware safety (no hardware needed)

1. Sensor validity: mandatory board NTC, optional-at-boot laser NTC, latched sensor faults (FW-01, FW-02).
2. Watchdog serviced only after a full supervision cycle; latched fault after a watchdog reset (FW-03, FW-07).
3. Measurement chain inside datasheet limits: ratiometric VBAT/CS with VDD calibration, 1.5 V references for
   ADC1/DAC0/DAC2, reference settling (FW-04, FW-05).
4. Switch debounce and press lockout; start-voltage re-check before every emission; over-voltage latched in every
   state; output-while-off detection; readable blink codes (FW-06, FW-11, FW-14, FW-15, FW-13).
5. CC/PG pull-up handling (FW-10).
6. Hardware abstraction and host tests: `hal.h`, `hal_avr.c`, `fw.c`, `conv.c`, `holdup.c`, recording mock HAL;
   tick backlog, hold-up races and reconnection debounce (FW-17, FW-12, FW-08, FW-09).
7. Fuse definition and verification step (FW-16).

## Phase 2: evidence and validation

8. Evidence manifests with input hashes and tool versions for calculations, simulations and firmware
   (VAL-01, VAL-02, VAL-07).
9. Strict parsing of calculation/simulation results, exit codes (VAL-03, VAL-09).
10. Known-limitations baseline, per-board readiness, validation modes (`fast`, `full`, `eval-cad`,
    `compact-cad`, `manufacturing`, `bench`) (VAL-05, VAL-06).
11. Independent SIM-11 (frequency-response analysis) and a sensitivity sweep (VAL-04, SIM-03); SIM-08 cleanup
    (SIM-02); RMS check (CAL-01).

## Phase 3: release controls and sourcing

12. Release levels DRAFT_REVIEW / PROTOTYPE_CANDIDATE / MANUFACTURING_RELEASE with blockers and a human approval
    file; DO_NOT_FABRICATE marker for incomplete boards (MFG-01, MFG-02).
13. Sourcing consistency and derating checks; data age flag; BOM description check (SRC-01, SRC-02, MFG-03).

## Phase 4: tooling for people

14. Bench-test recording framework (schema, importer, comparison with predictions, reports) (VAL-10).
15. Generated engineering status dashboard (HTML) from the evidence.
16. GitHub Actions: portable Python tests, firmware host tests and target build, evidence integrity, with the
    Windows/KiCad steps kept separate (CI-01).

## Phase 5: documentation

17. README, AGENTS.md (control characters), PROGRESS, requirements, firmware README, test plan (new T0.4, T1.11),
    developer onboarding and release checklist (DOC-01..03).

## Deferred: needs a CAD regeneration session

- Variant-specific BOM descriptions in `connectivity.yaml` (MFG-03). Changing `connectivity.yaml` invalidates the
  DRC/export evidence of both boards; do it together with the next routed-board change and rerun the full chain
  (AGENTS.md "Regenerating evidence").
- Evaluation-board layout options (DR1H via, U1 ISP/ISN pair, C5): each needs a new router session
  (`engineering/pcb-review-2026-10-26.md`).

## Needs owner approval

- Hardware gate clamp for Q6 (R-13 / PCB-04).
- Compact board direction: HDI, placement re-architecture or fewer parts (R-07 / PCB-02).
- Any change to battery thresholds, setpoint, interlock topology or fault-latch policy beyond what is listed above.
- Purchasing, fabrication quotes and every bench test.
