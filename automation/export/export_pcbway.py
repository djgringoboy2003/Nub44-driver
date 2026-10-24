"""PCBWay manufacturing export for one PCB variant.

Everything is derived from the board file (hardware/<variant>/nubm44_driver.kicad_pcb) with kicad-cli and the
board's own footprint data, then cross-checked:
  * every BOM designator is a placed footprint and vice versa (excluding non-BOM features);
  * every centroid row equals the footprint position in the board file (place origin, Y up);
  * every expected Gerber/drill file exists and is non-empty.

Outputs (manufacturing/pcbway/<variant>/):
  gerbers/         RS-274X, X2 off (PCBWay KiCad guide), Protel extensions
  drill/           Excellon mm, separate PTH/NPTH, drill map PDF
  assembly/        BOM_PCBWay_template.csv, BOM_PCBWay_plugin.csv, CPL_PCBWay.csv, ibom.html
  drawings/        assembly drawings (top/bottom), schematic PDF, fab drawing, 3D renders
  reports/         export-check.json
  <variant>-gerbers.zip   upload file for the bare-board order
No order is placed. Release state is decided by scripts/validate.ps1 (gates), not here.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import zipfile
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import paths  # noqa: E402
from nubm44.sexpr import child, children, load  # noqa: E402

PROJECT = "nubm44_driver"
GERBER_LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu", "F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen",
                 "F.Mask", "B.Mask", "Edge.Cuts"]


def cli(*args, check=True):
    r = subprocess.run([str(paths.kicad_cli()), *map(str, args)], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"kicad-cli {' '.join(map(str, args))} failed:\n{r.stdout}\n{r.stderr}")
    return r


def board_footprints(pcb: Path) -> tuple[list[dict], tuple[float, float]]:
    """Footprints with position, side, fields and attributes, straight from the board file."""
    root = load(pcb)
    setup = child(root, "setup")
    aux = child(setup, "aux_axis_origin") if setup else None
    origin = (float(aux[1]), float(aux[2])) if aux else (0.0, 0.0)
    fps = []
    for fp in children(root, "footprint"):
        at = child(fp, "at")
        props = {str(p[1]): str(p[2]) for p in children(fp, "property")}
        attr = child(fp, "attr")
        flags = {str(a) for a in attr[1:]} if attr else set()
        pads = children(fp, "pad")
        mount = "thru-hole" if any(str(p[2]) == "thru_hole" for p in pads) else "smd"
        fps.append({
            "ref": props.get("Reference", ""), "value": props.get("Value", ""),
            "fpid": str(fp[1]), "x": float(at[1]), "y": float(at[2]),
            "rot": float(at[3]) if len(at) > 3 else 0.0,
            "side": "bottom" if str(child(fp, "layer")[1]) == "B.Cu" else "top",
            "mpn": props.get("MPN", ""), "mfr": props.get("Manufacturer", ""),
            "desc": props.get("Description", ""),
            "in_bom": "exclude_from_bom" not in flags, "in_pos": "exclude_from_pos_files" not in flags,
            "dnp": "dnp" in flags, "mount": mount,
        })
    return fps, origin


def export(variant: str) -> dict:
    vdir = paths.HARDWARE / variant
    pcb, sch = vdir / f"{PROJECT}.kicad_pcb", vdir / f"{PROJECT}.kicad_sch"
    out = paths.MANUFACTURING / "pcbway" / variant
    if out.exists():
        shutil.rmtree(out)
    for sub in ("gerbers", "drill", "assembly", "drawings", "reports"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    check = {"variant": variant, "problems": [], "files": {}}

    # ---- fabrication
    cli("pcb", "export", "gerbers", "--no-x2", "--no-netlist", "--subtract-soldermask", "--check-zones",
        "-l", ",".join(GERBER_LAYERS), "-o", out / "gerbers", pcb)
    cli("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-zeros-format",
        "decimal", "--excellon-separate-th", "--generate-map", "--map-format", "pdf", "-o", out / "drill", pcb)
    gerbers = sorted((out / "gerbers").glob("*"))
    if len(gerbers) < len(GERBER_LAYERS):
        check["problems"].append(f"expected {len(GERBER_LAYERS)} Gerber files, got {len(gerbers)}")
    for g in gerbers + sorted((out / "drill").glob("*")):
        size = g.stat().st_size
        check["files"][str(g.relative_to(out))] = size
        if size == 0:
            check["problems"].append(f"empty file {g.name}")
    if not list((out / "drill").glob("*PTH*.drl")):
        check["problems"].append("no PTH drill file")

    # ---- assembly data from the board file
    fps, origin = board_footprints(pcb)
    bom_parts = [f for f in fps if f["in_bom"]]
    pos_parts = [f for f in fps if f["in_pos"] and not f["dnp"]]

    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for f in sorted(bom_parts, key=lambda f: (f["mpn"], f["value"], f["ref"])):
        groups.setdefault((f["mpn"], f["mfr"], f["value"], f["fpid"], f["mount"], f["dnp"], f["desc"]), []).append(f["ref"])
    with open(out / "assembly" / "BOM_PCBWay_template.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Item #", "*Designator", "*Qty", "Manufacturer", "*Mfg Part #", "Description / Value",
                    "*Package/Footprint ", "Type", "Your Instructions / Notes"])
        for i, ((mpn, mfr, val, fpid, mount, dnp, desc), refs) in enumerate(groups.items(), start=1):
            typ = "DNS" if dnp else ("thru-hole" if mount == "thru-hole" else "SMD")
            note = "Do not place: customer fits the battery spring by hand" if dnp else ""
            w.writerow([i, ",".join(sorted(refs, key=_ref_key)), len(refs), mfr, mpn, f"{val} - {desc}",
                        fpid.split(":", 1)[-1], typ, note])
    with open(out / "assembly" / "BOM_PCBWay_plugin.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Quantity", "Value", "Footprint", "Package", "MPN", "DNP", "Mount_Type",
                    "Manufacturer"])
        for (mpn, mfr, val, fpid, mount, dnp, desc), refs in groups.items():
            w.writerow([",".join(sorted(refs, key=_ref_key)), len(refs), val, fpid, fpid.split(":", 1)[-1], mpn,
                        "DNP" if dnp else "", mount, mfr])
    with open(out / "assembly" / "CPL_PCBWay.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["pos_x", "pos_y", "rotation", "side", "designator", "mpn", "pack", "footprint", "value", "mount_type"])
        for f in sorted(pos_parts, key=lambda f: _ref_key(f["ref"])):
            w.writerow([f"{f['x'] - origin[0]:.4f}", f"{-(f['y'] - origin[1]):.4f}", f"{f['rot']:.2f}", f["side"],
                        f["ref"], f["mpn"], f["fpid"].split(":", 1)[-1], f["fpid"], f["value"], f["mount"]])

    # cross-check the centroid against kicad-cli's own position export
    kpos = out / "reports" / "kicad_pos.csv"
    cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin",
        "--exclude-dnp", "-o", kpos, pcb)
    with open(kpos, encoding="utf-8") as fh:
        k = {r["Ref"]: r for r in csv.DictReader(fh)}
    for f in pos_parts:
        r = k.get(f["ref"])
        if r is None:
            check["problems"].append(f"{f['ref']}: in CPL but not in kicad-cli position export")
            continue
        dx = abs(float(r["PosX"]) - (f["x"] - origin[0]))
        dy = abs(float(r["PosY"]) - (-(f["y"] - origin[1])))
        if f["side"] == "bottom":
            dx = abs(abs(float(r["PosX"])) - abs(f["x"] - origin[0]))
        if dx > 0.001 or dy > 0.001:
            check["problems"].append(f"{f['ref']}: CPL position differs from kicad-cli by ({dx:.4f}, {dy:.4f}) mm")
    extra = set(k) - {f["ref"] for f in pos_parts}
    if extra:
        check["problems"].append(f"kicad-cli position export has parts missing from CPL: {sorted(extra)}")
    bom_refs = {r for refs in groups.values() for r in refs}
    if bom_refs != {f["ref"] for f in bom_parts}:
        check["problems"].append("BOM designators differ from BOM footprints")
    missing_mpn = sorted(f["ref"] for f in bom_parts if not f["dnp"] and f["mpn"] in ("", "-", "UNKNOWN"))
    if missing_mpn:
        check["problems"].append(f"BOM parts without MPN: {missing_mpn}")

    # ---- drawings and documentation outputs
    cli("sch", "export", "pdf", "-o", out / "drawings" / f"{PROJECT}_schematic.pdf", sch)
    for side, layers, mirror in (("top", "F.Fab,F.Courtyard,Edge.Cuts", False), ("bottom", "B.Fab,B.Courtyard,Edge.Cuts", True)):
        args = ["pcb", "export", "pdf", "--mode-single", "-l", layers, "--include-border-title",
                "-o", out / "drawings" / f"assembly_{side}.pdf", pcb]
        if mirror:
            args.insert(3, "--mirror")
        cli(*args, check=False)
    cli("pcb", "export", "pdf", "--mode-single", "-l", "Edge.Cuts,F.Cu,User.Drawings,User.Comments",
        "--include-border-title", "-o", out / "drawings" / "fab_outline.pdf", pcb, check=False)
    for side in ("top", "bottom"):
        cli("pcb", "render", "--side", side, "--quality", "high", "--width", "1600", "--height", "1600",
            "--zoom", "1.0", "-o", out / "drawings" / f"render_{side}.png", pcb, check=False)
    cli("pcb", "render", "--side", "top", "--quality", "high", "--rotate", "-35,0,30", "--width", "1600",
        "--height", "1200", "-o", out / "drawings" / "render_iso.png", pcb, check=False)
    ibom = ROOT / "tools/ibom/InteractiveHtmlBom/generate_interactive_bom.py"
    if ibom.exists():
        subprocess.run([str(paths.kicad_python()), str(ibom), str(pcb), "--no-browser", "--dest-dir",
                        str(out / "assembly"), "--name-format", "ibom", "--extra-fields", "MPN,Manufacturer",
                        "--include-tracks"], capture_output=True, text=True)
        if not (out / "assembly" / "ibom.html").exists():
            check["problems"].append("interactive BOM not generated")

    # ---- packaging (bare-board upload zip = gerbers + drill)
    zpath = out / f"{variant}-gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((out / "gerbers").glob("*")) + sorted((out / "drill").glob("*")):
            z.write(f, f"{f.parent.name}/{f.name}")
    check["bom_lines"] = len(groups)
    check["bom_parts"] = len(bom_parts)
    check["cpl_parts"] = len(pos_parts)
    check["status"] = "PASS" if not check["problems"] else "FAIL"
    (out / "reports" / "export-check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    return check


def _ref_key(ref: str):
    i = len(ref.rstrip("0123456789"))
    return (ref[:i], int(ref[i:] or 0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="compact-22mm")
    a = ap.parse_args()
    res = export(a.variant)
    print(f"{a.variant}: export {res['status']}; BOM lines {res['bom_lines']}, parts {res['bom_parts']}, "
          f"CPL {res['cpl_parts']}; problems: {res['problems']}")
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
