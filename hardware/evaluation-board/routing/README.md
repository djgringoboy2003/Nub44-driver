# Generated routing checkpoint: evaluation-board

These are generated handoff artifacts copied byte-for-byte from the observed routing run in
`build/evaluation-board/`. They preserve the exact router input and output used for the current board candidate:

- `nubm44_driver.dsn`: Specctra router input.
- `nubm44_driver.ses`: exported router session.
- `routing-evidence.json`: SHA-256 binding between that input and session, plus run provenance.
- `checkpoint-source.json`: archive hashes, capture-time placement/connectivity/parameter/CAD/tool-script
  hashes, and the associated DRC report hash and counts.

The evaluation-board candidate made from this session plus its source-defined corrections passed KiCad with 0 errors, 0 warnings, 0 unconnected items and 0 schematic-parity findings at capture. An exported router session by itself is not a passing validation result.

Post-capture revision (2026-10-25): the power-layout review changed three source pours in `placement.yaml`
(SW1 junction, In2 VOUT finger, LD_P). They were re-applied to this unchanged DSN/SES by the finish stage. All
post-route selectors matched, and DRC remained 0/0/0/0. `checkpoint-source.json` lists both the capture-time
hashes and the revised `source_revisions` hashes. Compare against the latest revision before restoring.

## Restore the existing session

Use the board, placement source, connectivity, parameters and helper scripts from the same Git commit as this
checkpoint. Compare their SHA-256 values with `checkpoint-source.json` before restoring. The archive file
hashes must match that file, and the DSN/SES hashes must also match `routing-evidence.json`. The finish command
checks the DSN/SES binding; it does not replace the other source-hash checks.

From the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path 'build\evaluation-board' | Out-Null
Copy-Item -LiteralPath 'hardware\evaluation-board\routing\nubm44_driver.dsn' -Destination 'build\evaluation-board\nubm44_driver.dsn'
Copy-Item -LiteralPath 'hardware\evaluation-board\routing\nubm44_driver.ses' -Destination 'build\evaluation-board\nubm44_driver.ses'
Copy-Item -LiteralPath 'hardware\evaluation-board\routing\routing-evidence.json' -Destination 'build\evaluation-board\routing-evidence.json'
.venv\Scripts\python.exe automation\placement\build_pcb.py --variant evaluation-board --stage finish
.venv\Scripts\python.exe automation\placement\build_pcb.py --variant evaluation-board --stage drc
```

The committed native PCB provides the existing placed-board base. Finish reimports the session, applies the
current `placement.yaml` copper corrections and pours, and saves the board. DRC then checks the resulting
board against current rules and the schematic. Inspect that new report; the archived counts are historical
evidence and must never be used as a substitute for running validation.

Do not run `place` between restoring the three files and `finish`: it regenerates the board and DSN. A fresh
`route`/`all` run may produce different geometry. Exact post-route correction selectors can then stop matching,
and additive corrections may conflict with new copper. Every new autorouter result requires fresh full DRC
and inspection of the intended power paths before replacing this checkpoint.

No checkpoint closes the physical-validation gate or authorizes manufacturing. All repository release
blockers in the validation register remain applicable.
