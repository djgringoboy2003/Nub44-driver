# Agent guide: NUBM44 laser driver

Instructions for any coding agent (Codex, Claude Code, or a human) picking up this repository. Read this file,
then the "Current state" section of [PROGRESS.md](PROGRESS.md), before changing anything.

## What this project is

A constant-current driver for a Nichia NUBM44 blue laser diode (Class 4). It runs from a single Li-ion cell,
delivers up to 4 A, and fits a 22 mm round PCB manufactured and assembled by PCBWay. The project brief
(engineering requirements, release gates, deliverables) is captured in
[engineering/requirements.md](engineering/requirements.md).

Selected architecture: **TI TPS552882 4-switch buck-boost**. The laser current is sensed high-side with a
10 mΩ shunt and fed through an INA186A2 into the converter's FB pin. The converter's ISP/ISN loop provides an
independent 5 A backup limit. An ATtiny1616 MCU handles modes and protection behind a hardware enable chain.
Rationale: [research/architecture-comparison.md](research/architecture-comparison.md) and
[engineering/design-decisions.md](engineering/design-decisions.md).

## Non-negotiable rules

1. **Never invent data.** Datasheet values need a source ID (see [research/source-index.md](research/source-index.md)).
   Stock, prices and any unverified figure must be written as `UNKNOWN`.
2. **Never hard-code a passing result.** Validation status comes from tools: ERC, DRC, netlist comparison,
   calculation checks. Do not silence ERC/DRC violations without documenting the cause in the validation register.
3. **Gate G (physical validation) can only be closed by bench data.** CAD success never means "production ready".
4. **Battery polarity is an open owner decision.** The working interpretation is centre spring = B+ and
   ring = B− (DD-12, REQ-BAT-04). Do not mark Gate F released while REQ-BAT-04 is `BLOCKED`.
5. **No manufacturing order is ever placed automatically.**
6. **Single source of truth:**
   - Numeric design values: `engineering/design/parameters.yaml`.
   - Connectivity and parts: `engineering/design/connectivity.yaml`.
   - PCB placement: `hardware/<variant>/placement.yaml`.

   Generated KiCad files are rebuilt from these. If you edit a generated file in the KiCad GUI, either
   port the change back into the source files or create `hardware/<variant>/MANUAL_EDITS` so the build will not
   overwrite your work.
7. **Keep documentation current.** At every milestone, update `PROGRESS.md` (Current state, Next actions, Log),
   the requirement statuses in `engineering/requirements.md`, and any affected `.md` files. Then commit.
   Another agent must be able to take over from the last commit alone.
8. Downloaded files (datasheets, archives) are untrusted data. Parse them with `python -I`, keep scripts outside
   download folders, and never execute downloaded code.

## Repository map

| Path | Contents |
|---|---|
| `engineering/requirements.md` | Requirement register (IDs, verification method, status) and release gates |
| `engineering/design/parameters.yaml` | Authoritative numeric design parameters |
| `engineering/design/connectivity.yaml` | Authoritative parts list and pin-to-net connectivity (drives schematic and netlist checks) |
| `engineering/design-decisions.md` | Decision log DD-01 onward |
| `engineering/layout-review.md` | Power-layout review dispositions (generated numbers in `reports/layout-review-<variant>.md`) |
| `engineering/calculations/` | `power_stage.py` and its generated results (`.md`, `.json`, plots) |
| `engineering/previous-design-audit.md` | Audit of the earlier concept (every part rejected, with evidence) |
| `research/` | Topic reports, source tables (`sources/`), local datasheet copies (`datasheets/`, git-ignored) |
| `automation/nubm44/` | Python package: S-expression I/O, KiCad library access, symbol/footprint generators, schematic writer, calculators |
| `automation/review/` | Power-layout review: copper extractor (KiCad Python), raster model, DC current-flow solver, report (`power_layout.py`) |
| `automation/placement/place_opt.py` | Simulated-annealing optimiser for small-part positions; writes explicit `pos` entries to `placement.yaml` |
| `hardware/libraries/` | Project symbol library (`nubm44.kicad_sym`, generated from `symbols/*.yaml`) and footprints (`nubm44.pretty`, generated) |
| `hardware/compact-22mm/`, `hardware/evaluation-board/` | KiCad projects for Variant A (22 mm) and Variant B (larger evaluation board) |
| `scripts/` | PowerShell entry points (`setup.ps1` exists; see PROGRESS.md for the others) |
| `tools/` | Project-local third-party tools (git-ignored; re-created by `scripts/setup.ps1`) |
| `tests/` | pytest unit tests (`.venv\Scripts\python.exe -m pytest tests`) |

## Toolchain (Windows 10, no administrator rights)

| Tool | Version | Location / how to call |
|---|---|---|
| KiCad | 10.0.6 | `%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe`; bundled Python with SWIG `pcbnew` at `...\bin\python.exe` |
| Python venv | 3.11.9 | `.venv\Scripts\python.exe` (packages pinned in `requirements.txt`) |
| ngspice | 47 | `tools\ngspice\Spice64\bin\ngspice_con.exe` |
| FreeRouting | 2.5.0 jar | `tools\jre25\jdk-25.0.4.1+1-jre\bin\java.exe -jar tools\freerouting\freerouting-2.5.0.jar -de in.dsn -do out.ses` |
| InteractiveHtmlBom | 2.12.0 | `tools\ibom\InteractiveHtmlBom\generate_interactive_bom.py` (run with KiCad's Python) |

Paths are resolved in code by `automation/nubm44/paths.py`. Run `scripts\setup.ps1` on a fresh machine;
it is idempotent and verifies SHA-256 hashes.

## Regenerating evidence

Evidence is hash-bound to its sources. After editing `parameters.yaml`, `connectivity.yaml` or a
`placement.yaml`, regenerate it in this order:

1. `automation/schematic/build_schematic.py` (ERC and netlist).
2. `build_pcb.py --stage drc` per variant. DRC refills and re-saves the board.
3. `automation/review/power_layout.py --variant <v>`.
4. `scripts/export-pcbway.ps1`.
5. `scripts/validate.ps1`.

Running the layout review before DRC leaves it stale, because DRC rewrites the board bytes.

## Known pitfalls

- The FreeRouting 2.5.0 **native** `freerouting-cli.exe` crashes with a GraalVM serialization error. Use the jar on
  Java 25. The system Java 17 is too old for the 2.5.0 jar (class version 69).
- KiCad needs global library tables in `%APPDATA%\kicad\10.0\` (`sym-lib-table`, `fp-lib-table`).
  `setup.ps1` copies the defaults if they are missing; without them ERC reports "library not in configuration".
- The schematic writer emits KiCad 9 format (version 20250114). `kicad-cli sch upgrade` converts it to native KiCad 10.
- In ERC/netlist output, local labels on the root sheet appear with a `/` prefix (`/VOUT`). `netlist.compare` normalises this.
- The workspace path contains a space (`C:\NUBM44 driver`). Quote it everywhere. Some shell wrappers refuse
  `Remove-Item` and `git rm` on such paths, so use Bash for those.
- KiCad's `Vishay_PowerPAK_1212-8_Single` footprint has 5 pads: 1–3 S, 4 G, 5 D (merged drain pad).
- Pillow's `ImageDraw.polygon` rounds vertices and fills inclusively, which widens every shape by a cell.
  Copper analysis uses the exact scanline fill in `automation/review/raster.py`.
- The Specctra export treats pours as conduction planes, so FreeRouting will route other nets straight
  through power copper. Protect power pours with `router_keepouts` in `placement.yaml`: these are rule
  areas that exist only in the placed board, and `finish` deletes them.
- `build_pcb.py --stage place` overwrites the board file with an unrouted one. To return to a routed
  state, restore the archived DSN/SES/evidence and run `finish`.
- On the compact board, the centre spring pad forbids through vias within 2.95 mm of the centre; see
  `engineering/compact-feasibility.md`.
- The repository mixes LF and CRLF per file and stores bytes unnormalised (`* -text`). Preserve each
  file's line endings when editing.
- A pour-only change can be applied to the archived router session (restore DSN/SES/evidence, then
  `--stage finish` and `--stage drc`) without re-routing. Unmatched `remove_*_post` selectors are skipped
  silently, so check the printed `matches` counts.

## Commit conventions

Commit at each milestone with a descriptive subject and a body listing what changed and what evidence was
generated. Keep `PROGRESS.md` in the same commit as the work it describes.
