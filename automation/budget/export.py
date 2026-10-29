"""Budget-2s manufacturing package (JLCPCB/PCBWay style) from the routed, DRC-checked board.

Writes manufacturing/budget-2s/: Gerbers + drill (zipped), pick-and-place, grouped BOM (full and JLCPCB
format), schematic/assembly PDFs, renders, ORDERING.md and a hash manifest. The package is marked
DO_NOT_FABRICATE unless reports/budget-2s/drc.json has 0 errors, 0 unconnected items and 0 parity
issues and its evidence matches the board. MPN UNKNOWN lines are listed with their required spec;
no part number is invented. No order is placed by any tool.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from collections import OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import evidence, paths  # noqa: E402
from nubm44.sexpr import child, children, load  # noqa: E402
from nubm44.variants import BUDGET_VARIANT, sources_for  # noqa: E402

sys.path.insert(0, str(ROOT / "automation/export"))
import export_pcbway as ab  # noqa: E402  (shared helpers: cli, board_footprints, layer list)

PROJECT = "nubm44_budget2s"
VDIR = paths.HARDWARE / BUDGET_VARIANT
BOARD, SCH = VDIR / f"{PROJECT}.kicad_pcb", VDIR / f"{PROJECT}.kicad_sch"
REPORTS = paths.REPORTS / BUDGET_VARIANT
OUT = ROOT / "manufacturing" / BUDGET_VARIANT
SOURCES = sources_for(BUDGET_VARIANT)
# Distributor order codes per MPN (DD-39), with evidence IDs; stock and prices stay UNKNOWN until quoted.
SOURCING = SOURCES.connectivity.with_name("sourcing.yaml")
# Requirement words that must never be merged across BOM lines when no MPN is fixed yet.
SPEC_TOKENS = re.compile(r"\d+(?:\.\d+)?\s?%|\d+\s?ppm/C|\d+(?:\.\d+)?\s?V\b|\bX[57][RS]\b|\bC0G\b|\bNTC\b", re.I)


def ref_key(ref: str):
    head = ref.rstrip("0123456789")
    return head, int(ref[len(head):] or 0)


def through_hole_refs(pcb: Path) -> list[str]:
    """Footprints with plated leads. KiCad types U1 through_hole because of its thermal vias, but those
    pads have no solder mask opening of their own, so they are vias, not leads to hand-solder."""
    refs = []
    for fp in children(load(pcb), "footprint"):
        if any(str(p[2]) == "thru_hole" and any("Mask" in str(x) for x in child(p, "layers")[1:])
               for p in children(fp, "pad")):
            refs.append(next(str(p[2]) for p in children(fp, "property") if str(p[1]) == "Reference"))
    return sorted(refs, key=ref_key)


def drc_state() -> dict:
    rep, ev = REPORTS / "drc.json", REPORTS / "drc-evidence.json"
    if not rep.is_file() or not ev.is_file():
        return {"clean": False, "reason": "no DRC report; run automation/budget/build_pcb.py --stage drc"}
    d, e = json.loads(rep.read_text(encoding="utf-8")), json.loads(ev.read_text(encoding="utf-8"))
    board_rel = BOARD.relative_to(ROOT).as_posix()
    if e.get("report_sha256") != hashlib.sha256(rep.read_bytes()).hexdigest() or \
            e.get("inputs", {}).get(board_rel) != hashlib.sha256(BOARD.read_bytes()).hexdigest():
        return {"clean": False, "reason": "DRC evidence does not match the current board; rerun DRC"}
    errors = sum(v["severity"] == "error" for v in d["violations"])
    warnings = sum(v["severity"] == "warning" for v in d["violations"])
    counts = {"errors": errors, "warnings": warnings, "unconnected": len(d["unconnected_items"]),
              "parity": len(d["schematic_parity"])}
    clean = errors == 0 and counts["unconnected"] == 0 and counts["parity"] == 0
    return {"clean": clean, **counts, "reason": "" if clean else f"DRC not clean: {counts}"}


def order_codes() -> dict:
    """MPN -> {lcsc, uk}; UNKNOWN codes become blank cells, never a guessed code."""
    parts = yaml.safe_load(SOURCING.read_text(encoding="utf-8"))["parts"]
    known = lambda v: v if v and v != "UNKNOWN" else ""
    return {str(m): {"lcsc": known(c.get("lcsc")), "uk": "; ".join(c.get("uk", []))} for m, c in parts.items()}


def write_bom(out: Path, fps: list[dict], spec: dict, codes: dict) -> tuple[int, int, list[str], list[str]]:
    def key(f):
        part = spec[f["ref"]]
        k = (f["mpn"], f["mfr"], f["value"], f["fpid"], part.get("lib", ""))
        if f["mpn"] in ("", "UNKNOWN"):  # same value/land is not the same part: keep tolerance, TCR, rating apart
            k += tuple(sorted({t.replace(" ", "").upper() for t in SPEC_TOKENS.findall(part.get("desc", ""))}))
        return k

    groups: OrderedDict[tuple, list] = OrderedDict()
    for f in sorted((f for f in fps if f["in_bom"]), key=lambda f: (f["mpn"], f["value"], ref_key(f["ref"]))):
        groups.setdefault(key(f), []).append(f["ref"])
    unknown, no_lcsc = [], []
    with open(out / "assembly/BOM.csv", "w", newline="", encoding="utf-8-sig") as fh, \
            open(out / "assembly/BOM_JLCPCB.csv", "w", newline="", encoding="utf-8-sig") as fj:
        w, j = csv.writer(fh), csv.writer(fj)
        w.writerow(["Item", "Designators", "Qty", "Value", "Footprint", "Manufacturer", "MPN", "LCSC", "UK distributor",
                    "Requirement / notes"])
        j.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for i, (k, refs) in enumerate(groups.items(), start=1):
            mpn, mfr, val, fpid = k[:4]
            refs = sorted(refs, key=ref_key)
            desc = "; ".join(dict.fromkeys(spec[r].get("desc", "") for r in refs))
            code = codes.get(mpn, {"lcsc": "", "uk": ""})
            if mpn in ("", "UNKNOWN"):
                unknown.append(f"{','.join(refs)}: {val} {fpid.split(':')[-1]} - {desc}")
            elif not code["lcsc"]:
                no_lcsc.append(f"{','.join(refs)}: {mpn}" + (f" ({code['uk']})" if code["uk"] else ""))
            w.writerow([i, ",".join(refs), len(refs), val, fpid.split(":", 1)[-1], mfr, mpn or "UNKNOWN",
                        code["lcsc"], code["uk"], desc])
            j.writerow([f"{val} {mpn}" if mpn not in ("", "UNKNOWN") else f"{val} (select: {desc[:60]})",
                        ",".join(refs), fpid.split(":", 1)[-1], code["lcsc"]])
    return len(groups), sum(len(v) for v in groups.values()), unknown, no_lcsc


def write_cpl(out: Path, fps: list[dict], origin: tuple[float, float]) -> int:
    rows = sorted((f for f in fps if f["in_pos"] and not f["dnp"]), key=lambda f: ref_key(f["ref"]))
    with open(out / "assembly/CPL_JLCPCB.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for f in rows:
            w.writerow([f["ref"], f"{f['x'] - origin[0]:.4f}mm", f"{-(f['y'] - origin[1]):.4f}mm",
                        "Top" if f["side"] == "top" else "Bottom", f"{f['rot'] % 360:.2f}"])
    return len(rows)


def main() -> int:
    state = drc_state()
    stage = OUT.with_name(OUT.name + ".tmp")
    shutil.rmtree(stage, ignore_errors=True)
    for sub in ("gerbers", "drill", "assembly", "drawings"):
        (stage / sub).mkdir(parents=True)
    ab.cli("pcb", "export", "gerbers", "--no-x2", "--no-netlist", "--subtract-soldermask", "--check-zones",
           "--use-drill-file-origin", "-l", ",".join(ab.GERBER_LAYERS), "-o", stage / "gerbers", BOARD)
    ab.cli("pcb", "export", "drill", "--format", "excellon", "--drill-origin", "plot", "--excellon-units", "mm",
           "--excellon-zeros-format", "decimal", "--excellon-separate-th", "--generate-map", "--map-format", "pdf",
           "-o", stage / "drill", BOARD)
    ab.cli("sch", "export", "pdf", "-o", stage / "drawings" / f"{PROJECT}_schematic.pdf", SCH)
    ab.cli("pcb", "export", "pdf", "-l", "F.Fab,Edge.Cuts", "--include-border-title", "-o",
           stage / "drawings" / "assembly_top.pdf", BOARD)
    for side in ("top", "bottom"):
        ab.cli("pcb", "render", "--side", side, "--width", "1600", "--height", "1100", "--quality", "basic",
               "-o", stage / "drawings" / f"render_{side}.png", BOARD)
    fps, origin = ab.board_footprints(BOARD)
    spec = {p["ref"]: p for p in yaml.safe_load(SOURCES.connectivity.read_text(encoding="utf-8"))["parts"]}
    missing = sorted(set(spec) ^ {f["ref"] for f in fps})
    lines, placed, unknown, no_lcsc = write_bom(stage, fps, spec, order_codes())
    cpl = write_cpl(stage, fps, origin)
    tht = [r for r in through_hole_refs(BOARD) if spec.get(r, {}).get("in_bom", True)]
    with zipfile.ZipFile(stage / f"{BUDGET_VARIANT}-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(p for folder in ("gerbers", "drill") for p in (stage / folder).iterdir() if p.is_file()):
            z.write(f, f.name)
    fab_ok = state["clean"] and not missing
    bom_note = "assembly BOM needs the listed selections" if unknown else "every BOM line has a sourced MPN"
    status = f"FABRICATION FILES CHECKED (prototype); {bom_note}" if fab_ok \
        else "DO NOT FABRICATE: " + (state["reason"] or f"board/connectivity mismatch {missing}")
    if not fab_ok:
        (stage / "DO_NOT_FABRICATE.txt").write_text(status + "\n", encoding="utf-8")
    (stage / "ORDERING.md").write_text("\n".join([
        "# Budget-2S driver: manufacturing package", "",
        f"Generated by `automation/budget/export.py`; do not hand-edit. **Status: {status}.**", "",
        "No tool places an order. Gate G (bench validation on a dummy load) remains OPEN.", "",
        "## Board", "",
        "- 90 x 60 mm, 4 layers, 1.6 mm FR-4, 1 oz outer and inner copper, ENIG or HASL lead-free.",
        "- Layer order: L1 F.Cu (`.gtl`), L2 In1.Cu GND plane (`.g1`), L3 In2.Cu (`.g2`), L4 B.Cu (`.gbl`).",
        "- Minimum track/space 0.15/0.15 mm, vias 0.6/0.3 mm. U1's five 0.6/0.3 mm thermal vias sit in its exposed",
        "  pad, unplugged and tented on the bottom; stencil apertures are kept 0.2 mm clear of them (no via filling).",
        "- All parts on the top side. Through-hole parts (hand-solder, or order through-hole assembly): "
        + ", ".join(tht) + ".",
        "- Fit the 10 A mini-blade fuse in F1 after assembly. X-ray or inspect U1 (VQFN exposed pad).",
        "- CPL rotations are KiCad's (0-360). Check every part in the assembler's placement preview, especially pin 1",
        "  of U1-U8, Q1-Q8 and the diodes D1-D4, before approving; library orientations differ between assemblers.", "",
        "## Files", "",
        f"- `{BUDGET_VARIANT}-gerbers.zip`: Gerbers and Excellon drill (PTH/NPTH) for the PCB order.",
        "- `assembly/BOM.csv` (full, with requirements), `assembly/BOM_JLCPCB.csv`, `assembly/CPL_JLCPCB.csv` (origin = drill origin).",
        "- `drawings/`: schematic, top assembly (F.Fab), renders.", "",
        f"## Checks (from tools)", "",
        f"- DRC: {state.get('errors', 'n/a')} errors, {state.get('warnings', 'n/a')} warnings, "
        f"{state.get('unconnected', 'n/a')} unconnected, {state.get('parity', 'n/a')} schematic-parity issues.",
        f"- BOM {lines} lines / {placed} parts; CPL {cpl} placements; board vs connectivity reference mismatch: {missing or 'none'}.", "",
        "## Lines to select at order time (no part number invented)", "",
        *([f"- {u}" for u in unknown] or ["None: every line has a sourced MPN (DD-39)."]), "",
        "## Lines without an LCSC code", "",
        "Order codes and evidence: `engineering/design/budget-2s/sourcing.yaml`. Stock and prices are not recorded",
        "and stay UNKNOWN until quoted. For a JLCPCB/LCSC-assembled board these lines must be matched by MPN in the",
        "assembler's BOM tool, consigned, or fitted by hand (UK distributor in brackets where one was found):", "",
        *([f"- {u}" for u in no_lcsc] or ["- None."]), "",
        "Precision lines (0.1 %, 25 ppm/C) set the laser current and protection thresholds: buy genuine parts from a",
        "UK distributor or LCSC and keep the exact values; do not substitute 1 % parts. Verify the XT30 moulded +/- marks",
        "against the B+/B- silkscreen before first power (Q1 blocks a reversed pack). See",
        "engineering/budget-2s-design.md for open review items.", ""]),
        encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    for attempt in range(10):  # Windows: a file watcher can briefly hold the fresh folder
        try:
            stage.rename(OUT)
            break
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(1.0)
    outputs = sorted(p for p in OUT.rglob("*") if p.is_file())
    evidence.write(evidence.build("budget-export", inputs=[BOARD, SCH, SOURCES.connectivity, SOURCING,
                                                         VDIR / "placement.yaml", REPORTS / "drc.json", Path(__file__)],
                                  outputs=outputs, tools={"kicad-cli": evidence.command_version([str(paths.kicad_cli()), "version"])}),
                   REPORTS / "export-evidence.json")
    print(f"budget-2s export: {status}; BOM {lines} lines/{placed} parts, CPL {cpl}, select-at-order {len(unknown)}, "
          f"lines without an LCSC code {len(no_lcsc)}")
    return 0 if fab_ok else 1


if __name__ == "__main__":
    sys.exit(main())
