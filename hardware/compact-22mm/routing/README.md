# Generated routing checkpoint: compact-22mm

These are generated handoff artifacts copied byte-for-byte from the observed routing run in
`build/compact-22mm/`. They preserve the exact router input and output used for the current board candidate:

- `nubm44_driver.dsn`: Specctra router input.
- `nubm44_driver.ses`: exported router session.
- `routing-evidence.json`: SHA-256 binding between that input and session, plus run provenance.
- `checkpoint-source.json`: archive hashes, capture-time placement/connectivity/parameter/CAD/tool-script
  hashes, and the associated DRC report hash and counts.

The archived compact-board session remains incomplete: at capture, KiCad reported 0 errors, 3 warnings, 20 unconnected items and 0 schematic-parity findings (2026-10-25 grid-routed revision; earlier sessions 31 and 43 unconnected). The DSN already contains the `grid_routes` copper from `placement.yaml` as fixed wiring. An exported router session by itself is not a passing validation result.

## Restore the existing session

Use the board, placement source, connectivity, parameters and helper scripts from the same Git commit as this
checkpoint. Compare their SHA-256 values with `checkpoint-source.json` before restoring. The archive file
hashes must match that file, and the DSN/SES hashes must also match `routing-evidence.json`. The finish command
checks the DSN/SES binding; it does not replace the other source-hash checks.

From the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path 'build\compact-22mm' | Out-Null
Copy-Item -LiteralPath 'hardware\compact-22mm\routing\nubm44_driver.dsn' -Destination 'build\compact-22mm\nubm44_driver.dsn'
Copy-Item -LiteralPath 'hardware\compact-22mm\routing\nubm44_driver.ses' -Destination 'build\compact-22mm\nubm44_driver.ses'
Copy-Item -LiteralPath 'hardware\compact-22mm\routing\routing-evidence.json' -Destination 'build\compact-22mm\routing-evidence.json'
.venv\Scripts\python.exe automation\placement\build_pcb.py --variant compact-22mm --stage finish
.venv\Scripts\python.exe automation\placement\build_pcb.py --variant compact-22mm --stage drc
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
