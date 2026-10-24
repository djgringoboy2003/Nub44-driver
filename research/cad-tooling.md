# CAD tooling notes: InteractiveHtmlBom, EasyEDA, FreeRouting Java and KiCad hooks

Researched 2026-10-24. The scope was narrowed by the coordinator: KiCad CLI flags and FreeRouting
CLI flags are being verified locally by the lead engineer, so they are not documented here.
Source IDs refer to `research/sources/manufacturing-sources.md`.

## 1. InteractiveHtmlBom (openscopeproject/InteractiveHtmlBom), MFG-25

**Releases**
- Latest is **v2.12.0, published 2026-09-10**. Assets are `InteractiveHtmlBom.zip` and `InteractiveHtmlBom_v2.12.0_pcm.zip`. PyPI `InteractiveHtmlBom` 2.12.0 (uploaded 2026-09-10) needs Python ≥3.8, `wxpython>=4.0` and `jsonschema>=4.1`.
- The repository is MIT licensed.

**KiCad 10 compatibility**
- v2.11.0 (2026-03-24): "This release updates compatibility with KiCad v10". It adds "[Added] support for new variants in KiCad v10" and "Make wx dependency optional for CLI usage".
- v2.11.1 (2026-03-31) and v2.11.2 (2026-05-24) are KiCad 10 bug-fix releases.
- v2.12.0 adds "support for KiCad 10 native barcodes/QR codes" and "native KiCad knockout text".
- `master` has later, unreleased fixes. One is "Fix DNP and variant fields being ignored with field case normalization (#588)", dated 2026-10-10. If DNP handling misbehaves on v2.12.0, try `master`.

**Running it headless on Windows (wiki "Usage")**
- Quoted: "On windows the trick is to use python that is bundled with KiCad so the command will look like this: `path/to/kicad/bin/python.exe .../generate_interactive_bom.py .../board.kicad_pcb`".
- The KiCad parser does `import pcbnew` and `pcbnew.LoadBoard(...)`. It therefore **needs KiCad's bundled Python with the SWIG `pcbnew` module**. A plain system Python 3.11 will not work.
- For a per-user KiCad 10 install, the interpreter path is probably `%LOCALAPPDATA%\Programs\KiCad\10.0\bin\python.exe`. **Verify this locally**; it is not confirmed.
- Set the environment variable `INTERACTIVE_HTML_BOM_NO_DISPLAY` to skip creating a wx App. In `compat.py`, `should_create_wx_app()` returns False when that variable is present. `--show-dialog` is then refused.
- Relevant options (from `core/config.py`):
  - `--no-browser`, `--dest-dir`, `--name-format`
  - `--include-tracks`, `--include-nets`
  - `--extra-fields`, `--show-fields`, `--group-fields`
  - `--dnp-field`, `--kicad-variant`, `--variant-field`
  - `--blacklist`, `--checkboxes`
  - `--highlight-pin1 [none|all|selected]`
  - `--board-rotation`, `--offset-back-rotation`
  - `--dark-mode`, `--layer-view`, `--bom-view`
  - `--use-ini`, `--custom-metadata`
- Run `--help` for the defaults.
- Example (paths to verify):
  ```
  set INTERACTIVE_HTML_BOM_NO_DISPLAY=1
  "%LOCALAPPDATA%\Programs\KiCad\10.0\bin\python.exe" <ibom>\InteractiveHtmlBom\generate_interactive_bom.py board.kicad_pcb --no-browser --dest-dir ..\manufacturing\ibom --include-tracks --include-nets --highlight-pin1 all --extra-fields "MPN,Manufacturer"
  ```

**Risk.** iBOM's KiCad path depends on the SWIG bindings. KiCad dev docs say they are "deprecated as of KiCad 9.0" and that "The current plan is to remove the SWIG bindings in KiCad 11.0" (MFG-27). This is fine for KiCad 10.

## 2. EasyEDA interoperability, MFG-29

- EasyEDA Pro docs ("Import KiCad", page "Last updated" blank, © 2026) say: **"EasyEDA Pro supports importing files from KiCad versions below 10.0."**
- Import procedure: package the project with KiCad's own archive function, "Do not pack it in the folder yourself", then import the zip on the Pro start page.
- "After PCB is imported, it will automatically rebuild and copper area. The result of copper area will be different, please check carefully."
- EasyEDA Standard docs (search snippet only, older) cite "KiCAD v4.06 and greater" and warn about format changes since 5.1.3.
- **Practical recommendation (DERIVED):**
  - Do not plan on EasyEDA round-trips of the KiCad 10 project. KiCad 10 files are outside EasyEDA Pro's stated support.
  - I did not check whether KiCad 10 can save in KiCad 9 format; treat that as unavailable unless verified.
  - PCBWay ordering does not need EasyEDA at all. For reviewers without KiCad, share Gerbers, the iBOM HTML, PDFs or a STEP file instead.
  - If an EasyEDA copy is ever required, import Gerbers as a reference only. Gerbers carry no schematic or nets.

## 3. FreeRouting: Java requirement and KiCad integration (facts already gathered), MFG-26

**Version and Java requirement**
- Latest release is **v2.5.0, published 2026-10-05**. The repo is github.com/freerouting/freerouting (GPL-3.0).
- Assets:
  - `freerouting-2.5.0.jar`
  - `freerouting-2.5.0-windows-x64.msi`
  - **`freerouting-cli-2.5.0-windows-x64.zip`**: native GraalVM binary `freerouting-cli`, SHA-256 `5750dc0bed261eefae29d79784301b478af978fd472407d77e01e85dbb794857`
  - Linux, macOS and AppImage builds.
- **The jar requires Java 25.** Our Temurin 17 cannot run it.
  - `build.gradle` at v2.5.0 sets `sourceCompatibility = JavaVersion.VERSION_25` and toolchain 25. This has been true since v2.2.0 (2026-04-27); v2.1.0 and earlier targeted Java 21.
  - README: "Install Java JRE … Choose version `25`."
  - The KiCad PCM plugin metadata says: "It needs Java JRE 25".
- The release notes say the native CLI binaries "eliminate the Java JRE requirement for CLI users". That is the path to use; the coordinator reports it is installed.

**CLI caveat**
- The v2.5.0 release notes say: "`-hr` (`hybridRatio`), and strategy values `RANDOM`, `GREEDY`, and `HYBRID` for `-us`/`-is` have been removed. Use `-us GLOBAL_OPTIMAL` with `-is SEQUENTIAL` or `-is PRIORITIZED`."
- The built-in `--help` text and `docs/command_line_arguments.md` still list the old values.
- In the v2.5.0 source, any `-us` value maps to GLOBAL_OPTIMAL.
- `-mp` and `-inc` still work but log deprecation warnings. The canonical forms are `--router.autorouter.max_passes=` and `--router.autorouter.ignore_net_classes=`.

**KiCad integration**
- The KiCad plugin README says DSN mode is "Default / Recommended", and JSON/API mode is "Experimental".
- The v2.5.0 release notes introduce a "KiCad 10+ IPC Extension Mode" with a "Seamless fallback to the battle-tested Specctra DSN/SES pipeline if IPC is unavailable".
- They also state the next release will "completely remove legacy KiCad SWIG support".
- For our scripted flow, keep the DSN to `freerouting-cli` to SES route.

## 4. KiCad hooks already verified before the scope change (lead to re-check locally)

- **Specctra in SWIG:** the KiCad **10.0.6** source `pcbnew/python/scripting/pcbnew_scripting_helpers.h` (identical in 10.0.7) declares two board-taking overloads. Each is documented as one that "doesn't need a valid PCB_EDIT_FRAME set and can be used in a standalone python script" (MFG-28):
  - `bool ExportSpecctraDSN( BOARD* aBoard, wxString& aFullFilename )`
  - `bool ImportSpecctraSES( BOARD* aBoard, wxString& aFullFilename )`
- **No Specctra in `kicad-cli`:** `kicad-cli pcb import` (new in KiCad 10) lists `pads, altium, eagle, cadstar, fabmaster, pcad, solidworks` only. No CLI command imports or exports Specctra.
- **SWIG status:** "deprecated as of KiCad 9.0 … The current plan is to remove the SWIG bindings in KiCad 11.0" (MFG-27).
- **Versions:** the kicad.org blog lists KiCad 10.0.0 (2026-03-20), **10.0.7 released 2026-10-07** and 10.0.8-rc1 (2026-10-22). The lead is installing 10.0.6, one bug-fix release behind.
- **Position export:** `kicad-cli pcb export pos` defaults to `--units in` and `--format ascii`. Pass `--format csv --units mm` (see `pcbway-requirements.md` §5.2).
