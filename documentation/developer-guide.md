# Developer guide

For anyone (person or agent) who picks up the NUBM44 driver. Read [AGENTS.md](../AGENTS.md) for the rules and
[PROGRESS.md](../PROGRESS.md) for the current state first.

## 1. Architecture of the repository

```
engineering/design/parameters.yaml     numeric design values (single source)
engineering/design/connectivity.yaml   parts and pin-to-net connectivity (single source)
hardware/<variant>/placement.yaml      PCB placement, pours, keep-outs, post-route fixes (single source)
        │
        ├─ engineering/calculations/power_stage.py ──► power-stage-results.* + power-stage-evidence.json
        ├─ simulation/run_sims.py (ngspice) ─────────► simulation/results/* + evidence.json
        ├─ automation/schematic/build_schematic.py ──► hardware/<variant>/*.kicad_sch, .net; reports/erc-*, schematic-*
        ├─ automation/placement/build_pcb.py (KiCad, FreeRouting) ► hardware/<variant>/*.kicad_pcb; reports/drc-*
        ├─ automation/review/power_layout.py ────────► reports/layout-review-*
        ├─ automation/export/export_pcbway.py ───────► manufacturing/pcbway/<variant>/ (DRAFT packages)
        ├─ sourcing/build_sourcing.py, check_sourcing.py ► sourcing/*.csv, sourcing-check.*
        └─ firmware/build.py (TinyCC/gcc, avr-gcc) ──► firmware/build/*.hex; reports/firmware-evidence.json

documentation/testing/results/<serial>/ (bench records, MEASURED only) ── automation/bench/bench.py ──► reports/bench-*

automation/validation/validate.py reads all evidence ──► reports/validation-register.*, release-readiness.*,
                                                          dashboard/index.html, requirement gate table
```

Every generated result is bound to its inputs by SHA-256 (`automation/nubm44/evidence.py` manifests, DRC and export
manifests). Editing a source without regenerating makes the validator report stale evidence.

## 2. Fresh clone to a validated working copy

```powershell
git clone https://github.com/djgringoboy2003/Nub44-driver.git "C:\NUBM44 driver"
cd "C:\NUBM44 driver"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1     # tools, venv (no admin rights)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\doctor.ps1
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe firmware\build.py --mutation
.venv\Scripts\python.exe automation\validation\validate.py
```

Expected today: all Python tests pass; firmware PASS with 15/15 mutants killed; the validator exits 0 with three
known, unchanged items (compact routing, compact DRC, SIM-12 pending a decision). Open
`reports/dashboard/index.html` in a browser for the overview.

## 3. Everyday commands

| Task | Command |
|---|---|
| Python tests | `.venv\Scripts\python.exe -m pytest tests -q` |
| Firmware: host tests, ATtiny1616 build, mutation check | `.venv\Scripts\python.exe firmware\build.py --mutation` |
| Calculations | `.venv\Scripts\python.exe engineering\calculations\power_stage.py` (exit 1 if a check fails) |
| Simulations (about 2.5 min) | `.venv\Scripts\python.exe simulation\run_sims.py` (exit 1 while SIM-12 fails) |
| Sourcing check | `.venv\Scripts\python.exe sourcing\check_sourcing.py` |
| Validation, everything | `.venv\Scripts\python.exe automation\validation\validate.py` |
| Validation, without KiCad/ngspice/avr-gcc | `... validate.py --mode fast` |
| Validation of one board's CAD | `... validate.py --mode eval-cad` or `--mode compact-cad` |
| Release readiness only | `... validate.py --mode manufacturing` |
| Bench evidence | `... validate.py --mode bench` or `.venv\Scripts\python.exe automation\bench\bench.py check` |
| Regenerate stale calculations/simulations first | add `--rerun-stale` |
| Any failure counts (no baseline) | add `--strict` |
| Dashboard only | `.venv\Scripts\python.exe automation\dashboard\build_dashboard.py` |
| Export review packages | `scripts\export-pcbway.ps1 -Variant evaluation-board` |
| JLCPCB upload files (from the PCBWay package) | `.venv\Scripts\python.exe automation\export\export_jlcpcb.py --variant evaluation-board` |
| Footprint review pack | `.venv\Scripts\python.exe automation\review\footprint_report.py` |

### Validator exit codes

The register keeps every failure. The exit code is 1 only for a failure that is new or that changed compared with
`engineering/known-limitations.yaml` (`accepted` owner decisions and `pending_disposition` findings). When a known
item improves or worsens, update that file deliberately in the same commit, with the reason.

## 4. Regenerating evidence after a source change

Follow the order in AGENTS.md ("Regenerating evidence"). In short: schematics → DRC per board → layout review →
exports → calculations/simulations if parameters changed → `validate.py`. Running the layout review before DRC
leaves it stale because DRC rewrites the board. Changing `connectivity.yaml` invalidates the DRC and export evidence
of both boards.

## 5. Firmware workflow

- Logic lives in `firmware/src/app.c` (pure state machine), `conv.c`, `holdup.c`; hardware access only in
  `hal_avr.c`; `fw.c` ties them together. Add a host test for every behaviour change and, for a safety defect, a
  mutant in `firmware/build.py` `MUTANTS` that re-injects it.
- `firmware/tests/mock/avr/io.h` models the registers `hal_avr.c` uses; `tests/test_firmware_build.py` checks its
  constants against the real avr-libc header. Add any new register constant there.
- Thresholds in `app.h` come from DD-06/DD-08: changing one needs an owner decision and a design-decision entry.
- Fuses: `firmware/src/fuses.h`; programming and readback in `firmware/README.md`.

## 6. Recording bench results

See `documentation/testing/results/README.md`. Never type values that were not measured; the importer requires
`--measured`, and any non-MEASURED record is INVALID.

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `scripts\*.ps1` refused by execution policy | Run with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` (per process only). |
| ERC reports "library not in configuration" | Global KiCad library tables missing in `%APPDATA%\kicad\10.0\`; rerun `scripts\setup.ps1`. |
| FreeRouting crashes with a GraalVM error | Use the 2.5.0 jar on Java 25 (`paths.freerouting_cmd()`), not the native CLI. |
| Validator: "stale evidence: X changed since it was generated" | Rerun the generator named by the manifest (`--rerun-stale` for calculations and simulations; the CAD chain for DRC/layout/export). |
| Validator: "CHANGED VAL-…" for a known item | The known limitation changed (better or worse); review and update `engineering/known-limitations.yaml`. |
| Firmware build: avr-gcc or tcc not found | `scripts\setup.ps1`, or set `AVR_GCC_BIN` / `CC`. |
| `firmware/build.py` mutant SURVIVED | A test no longer catches an audited defect: strengthen the test, never delete the mutant. |
| Text file shows odd characters after an agent edit | Shell heredocs collapse doubled backslashes; write such files with a file tool. `tests/test_repo_hygiene.py` catches control characters. |
| Path errors | The workspace path contains a space; quote it everywhere. |

## 8. Recovering from common failures

- **`build_pcb.py --stage place` overwrote a routed board:** restore the archived DSN/SES/evidence from
  `hardware/<variant>/routing/` and run `--stage finish` then `--stage drc` (see the routing README).
- **A generator failed half-way:** generators delete their previous evidence before writing; rerun them. Never
  hand-edit generated reports or manifests to make them pass.
- **An export failed:** the previous package stays in place and a draft staging folder is kept for inspection
  (`manufacturing/pcbway/.<variant>-staging-*`, git-ignored).
- **A known limitation resolved:** the validator prints RESOLVED; remove the entry from
  `engineering/known-limitations.yaml`.

## 9. From a fresh clone to an evaluation-board prototype candidate

1. Working copy validated as in section 2.
2. Human reviews recorded in `engineering/release/design-reviews.yaml` (FP-U1, FP-L1, FP-POWERPAK, FP-RS1, ORIENT):
   a reviewer compares the footprints and orientations with the manufacturer drawings and fills in reviewer, date and
   evidence.
3. `validate.py` shows the evaluation board at PROTOTYPE_CANDIDATE in `reports/release-readiness.md`.
4. The owner reviews the package, confirms stock and prices, and orders by hand (no tool orders). Then follow
   [the release checklist](release-checklist.md) and the bench plan.
