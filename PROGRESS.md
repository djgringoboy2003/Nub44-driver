# Progress log

Newest entries first. Each entry records what was actually done and what evidence exists.

## 2026-10-24 — Phase 0: discovery and environment

### Workspace audit
- `C:\NUBM44 driver` was empty and not a git repository. Initialised git (`main`).
- The previous design files named in the brief do not exist on this machine (searched the workspace and the
  whole user profile). Recorded in `references/previous-design/README.md`. The previous concept is audited from
  the brief's description in `engineering/previous-design-audit.md`.

### Machine
- Windows 10 Pro 22H2 (10.0.19045), x64, Intel Core i5-7300U (2 cores / 4 threads), 15.9 GB RAM, ~170 GB free on C:.
- User account is **not** an administrator. All tools are installed per-user or project-local; no elevation used.

### Software found
| Tool | Version | Location |
|---|---|---|
| Git | 2.55.0.windows.5 | `C:\Program Files\Git` |
| Python | 3.11.9 | `%LOCALAPPDATA%\Programs\Python\Python311` |
| Java | Temurin OpenJDK 17.0.20.1 | `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot` |
| Node.js | 22.23.2 | `C:\Program Files\nodejs` |
| winget | 1.29.380 | WindowsApps |
| PowerShell | 7.6.8 | |

Missing at start: KiCad, ngspice, FreeRouting, EasyEDA, AVR toolchain, 7-Zip.

### Software installed
| Tool | Version | How | Location |
|---|---|---|---|
| ngspice | 47 (2026-08-11) | Official SourceForge `ngspice-47_64.7z`, extracted with py7zr | `tools/ngspice/Spice64` |
| FreeRouting CLI | 2.5.0 (2026-10-05) | Official GitHub release `freerouting-cli-2.5.0-windows-x64.zip`, SHA-256 checked against the release checksum file | `tools/freerouting` |
| Python venv | 3.11.9 | `python -m venv .venv` + numpy, scipy, matplotlib, pandas, pyyaml, jsonschema, pytest, jinja2, pypdf, pymupdf, py7zr, reportlab, sexpdata | `.venv` |
| KiCad | 10.0.6 | `winget install KiCad.KiCad --scope user` (installer's `/currentuser` mode; no admin) | in progress |

### Research (parallel)
Five research tasks launched with separate file ownership under `research/`:
NUBM44 laser diode, converter ICs/architecture, supporting components and sourcing, PCBWay + CAD tooling,
batteries + host mechanics.
