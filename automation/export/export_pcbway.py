"""Stage and independently verify PCBWay exports. Never places an order."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths, spec  # noqa: E402
from nubm44.sexpr import child, children, load  # noqa: E402

PROJECT = "nubm44_driver"
GERBER_EXTENSIONS = OrderedDict([
    ("F.Cu", "gtl"), ("In1.Cu", "g1"), ("In2.Cu", "g2"), ("B.Cu", "gbl"),
    ("F.Paste", "gtp"), ("B.Paste", "gbp"), ("F.Silkscreen", "gto"),
    ("B.Silkscreen", "gbo"), ("F.Mask", "gts"), ("B.Mask", "gbs"), ("Edge.Cuts", "gm1"),
])
GERBER_LAYERS = list(GERBER_EXTENSIONS)
TEMPLATE_COLUMNS = ["Item #", "*Designator", "*Qty", "Manufacturer", "*Mfg Part #", "Description / Value",
                    "*Package/Footprint ", "Type", "Your Instructions / Notes"]
BOM_COLUMNS = ["Designator", "Quantity", "Value", "Footprint", "Package", "MPN", "DNP", "Mount_Type", "Manufacturer"]
CPL_COLUMNS = ["pos_x", "pos_y", "rotation", "side", "designator", "mpn", "pack", "footprint", "value", "mount_type"]
KPOS_COLUMNS = ["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli(*args):
    r = subprocess.run([str(paths.kicad_cli()), *map(str, args)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"kicad-cli {' '.join(map(str, args))} failed ({r.returncode}):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r


def board_footprints(pcb: Path) -> tuple[list[dict], tuple[float, float]]:
    """Read native orientation and position without a bottom-side correction."""
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
        fps.append({
            "ref": props.get("Reference", ""), "value": props.get("Value", ""),
            "fpid": str(fp[1]), "x": float(at[1]), "y": float(at[2]),
            "rot": float(at[3]) if len(at) > 3 else 0.0,
            "side": "bottom" if str(child(fp, "layer")[1]) == "B.Cu" else "top",
            "mpn": props.get("MPN", ""), "mfr": props.get("Manufacturer", ""),
            "desc": props.get("Description", ""),
            "in_bom": "exclude_from_bom" not in flags, "in_pos": "exclude_from_pos_files" not in flags,
            "dnp": "dnp" in flags,
            "mount": "thru-hole" if any(str(p[2]) == "thru_hole" for p in pads) else "smd",
        })
    return fps, origin


def required_files(variant: str) -> list[str]:
    required = [f"gerbers/{PROJECT}-{layer.replace('.', '_')}.{ext}" for layer, ext in GERBER_EXTENSIONS.items()]
    required += [f"drill/{PROJECT}-{kind}{suffix}" for kind in ("PTH", "NPTH")
                 for suffix in (".drl", "-drl_map.pdf")]
    required += ["assembly/" + n for n in ("BOM_PCBWay_template.csv", "BOM_PCBWay_plugin.csv", "CPL_PCBWay.csv", "ibom.html")]
    required += ["drawings/" + n for n in (f"{PROJECT}_schematic.pdf", "assembly_top.pdf", "assembly_bottom.pdf",
                                            "fab_outline.pdf", "render_top.png", "render_bottom.png", "render_iso.png", "stack-up.md")]
    return required + ["reports/kicad_pos.csv", "REVIEW_ONLY.md", f"{variant}-gerbers.zip"]


def output_problems(out: Path, variant: str) -> list[str]:
    problems = []
    for rel in required_files(variant):
        p = out / rel
        if not p.is_file() or p.stat().st_size == 0:
            problems.append(f"missing or empty required output: {rel}")
    return problems


def write_assembly(out: Path, fps: list[dict], origin: tuple[float, float]) -> tuple[int, int, int]:
    bom_parts = [f for f in fps if f["in_bom"]]
    pos_parts = [f for f in fps if f["in_pos"] and not f["dnp"]]
    # One line per orderable part: assemblers price and buy per line, so identical parts are never split by their
    # functional descriptions (those are merged into the description column).
    groups: OrderedDict[tuple, list] = OrderedDict()
    descs: dict[tuple, list] = {}
    for f in sorted(bom_parts, key=lambda f: (f["mpn"], f["value"], _ref_key(f["ref"]))):
        key = tuple(f[k] for k in ("mpn", "mfr", "value", "fpid", "mount", "dnp"))
        groups.setdefault(key, []).append(f["ref"])
        if f["desc"] not in descs.setdefault(key, []):
            descs[key].append(f["desc"])
    with open(out / "assembly/BOM_PCBWay_template.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(TEMPLATE_COLUMNS)
        for i, ((mpn, mfr, val, fpid, mount, dnp), refs) in enumerate(groups.items(), start=1):
            typ = "DNS" if dnp else ("thru-hole" if mount == "thru-hole" else "SMD")
            note = "Do not place: customer fits the battery spring by hand" if dnp else ""
            w.writerow([i, ",".join(sorted(refs, key=_ref_key)), len(refs), mfr, mpn,
                        f"{val} - {'; '.join(descs[(mpn, mfr, val, fpid, mount, dnp)])}",
                        fpid.split(":", 1)[-1], typ, note])
    with open(out / "assembly/BOM_PCBWay_plugin.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(BOM_COLUMNS)
        for (mpn, mfr, val, fpid, mount, dnp), refs in groups.items():
            w.writerow([",".join(sorted(refs, key=_ref_key)), len(refs), val, fpid, fpid.split(":", 1)[-1], mpn,
                        "DNP" if dnp else "", mount, mfr])
    with open(out / "assembly/CPL_PCBWay.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(CPL_COLUMNS)
        for f in sorted(pos_parts, key=lambda f: _ref_key(f["ref"])):
            w.writerow([f"{f['x'] - origin[0]:.4f}", f"{-(f['y'] - origin[1]):.4f}", f"{f['rot']:.2f}", f["side"],
                        f["ref"], f["mpn"], f["fpid"].split(":", 1)[-1], f["fpid"], f["value"], f["mount"]])
    return len(groups), len(bom_parts), len(pos_parts)


def read_csv(path: Path, columns: list[str], problems: list[str]) -> list[dict]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != columns:
                problems.append(f"{path.name}: unexpected or duplicate CSV columns")
                return []
            rows = list(reader)
            if any(None in r or any(v is None for v in r.values()) for r in rows):
                problems.append(f"{path.name}: malformed CSV row")
                return []
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        problems.append(f"{path.name}: cannot read CSV: {exc}")
        return []


def check_ref_counts(refs: list[str], expected: list[str], label: str, problems: list[str]) -> None:
    actual_counts, expected_counts = Counter(refs), Counter(expected)
    duplicates = sorted(r for r, count in actual_counts.items() if count > 1)
    if duplicates:
        problems.append(f"{label}: duplicate designators {duplicates}")
    if actual_counts != expected_counts:
        problems.append(f"{label}: designator counts differ from board; missing {list((expected_counts - actual_counts).elements())}, "
                        f"extra {list((actual_counts - expected_counts).elements())}")


def numeric_mismatch(row: dict, key: str, expected: float, tolerance: float, angular=False) -> bool:
    try:
        actual = float(row[key])
    except (ValueError, TypeError, KeyError):
        return True
    if not math.isfinite(actual):
        return True
    delta = abs((actual - expected + 180) % 360 - 180) if angular else abs(actual - expected)
    return delta > tolerance


def check_assembly(out: Path, pcb: Path) -> list[str]:
    """Re-read the CSVs and the PCB, independently of the writer's in-memory groups."""
    problems = []
    fps, origin = board_footprints(pcb)
    if not fps or any(not f["ref"] for f in fps):
        problems.append("board has no footprints or contains a blank designator")
    counts = Counter(f["ref"] for f in fps)
    if any(c != 1 for c in counts.values()):
        problems.append("board contains duplicate designators")
    by_ref = {f["ref"]: f for f in fps}
    bom_expected = [f["ref"] for f in fps if f["in_bom"]]
    pos_expected = [f["ref"] for f in fps if f["in_pos"] and not f["dnp"]]
    for filename, columns, ref_col, qty_col, template in (
            ("BOM_PCBWay_template.csv", TEMPLATE_COLUMNS, "*Designator", "*Qty", True),
            ("BOM_PCBWay_plugin.csv", BOM_COLUMNS, "Designator", "Quantity", False)):
        refs = []
        rows = read_csv(out / "assembly" / filename, columns, problems)
        for row in rows:
            line_refs = [r.strip() for r in row[ref_col].split(",")]
            refs.extend(line_refs)
            try:
                if int(row[qty_col]) != len(line_refs) or int(row[qty_col]) <= 0:
                    problems.append(f"{filename}: quantity differs from designator count")
            except ValueError:
                problems.append(f"{filename}: invalid quantity")
            for ref in line_refs:
                f = by_ref.get(ref)
                if f is None:
                    continue
                package = f["fpid"].split(":", 1)[-1]
                expected = ({"*Mfg Part #": f["mpn"], "Manufacturer": f["mfr"], "*Package/Footprint ": package,
                             "Description / Value": f"{f['value']} - {f['desc']}",
                             "Type": "DNS" if f["dnp"] else ("thru-hole" if f["mount"] == "thru-hole" else "SMD")}
                            if template else {"MPN": f["mpn"], "Manufacturer": f["mfr"], "Value": f["value"],
                                              "Footprint": f["fpid"], "Package": package, "Mount_Type": f["mount"],
                                              "DNP": "DNP" if f["dnp"] else ""})
                for key, value in expected.items():
                    if key == "Description / Value":     # merged line: value first, this part's description inside
                        ok = row[key].startswith(f"{f['value']} - ") and f["desc"] in row[key]
                    else:
                        ok = row[key] == value
                    if not ok:
                        problems.append(f"{filename}: {ref} {key} differs from board")
        check_ref_counts(refs, bom_expected, filename, problems)
    missing_mpn = sorted(f["ref"] for f in fps if f["in_bom"] and not f["dnp"] and f["mpn"] in ("", "-", "UNKNOWN"))
    if missing_mpn:
        problems.append(f"BOM parts without MPN: {missing_mpn}")
    for filename, columns, ref_col, x_col, y_col, rot_col, side_col, native in (
            ("assembly/CPL_PCBWay.csv", CPL_COLUMNS, "designator", "pos_x", "pos_y", "rotation", "side", False),
            ("reports/kicad_pos.csv", KPOS_COLUMNS, "Ref", "PosX", "PosY", "Rot", "Side", True)):
        rows = read_csv(out / filename, columns, problems)
        check_ref_counts([r[ref_col] for r in rows], pos_expected, filename, problems)
        for row in rows:
            ref = row[ref_col]
            f = by_ref.get(ref)
            if f is None:
                continue
            for key, value, tol, angular in ((x_col, f["x"] - origin[0], 0.001, False),
                                             (y_col, -(f["y"] - origin[1]), 0.001, False),
                                             (rot_col, f["rot"], 0.01, True)):
                if numeric_mismatch(row, key, value, tol, angular):
                    problems.append(f"{filename}: {ref} {key} differs from board")
            expected = ({"Side": f["side"], "Val": f["value"], "Package": f["fpid"].split(":", 1)[-1]}
                        if native else {"side": f["side"], "mpn": f["mpn"], "pack": f["fpid"].split(":", 1)[-1],
                                        "footprint": f["fpid"], "value": f["value"], "mount_type": f["mount"]})
            for key, value in expected.items():
                if row[key] != value:
                    problems.append(f"{filename}: {ref} {key} differs from board")
    return problems


INCOMPLETE_MARKER = "DO_NOT_FABRICATE.txt"


def cad_state(variant: str, pcb: Path) -> dict:
    """The board's DRC state at export time (audit AUD-MFG-01). Missing or stale DRC evidence counts as incomplete."""
    report = ROOT / "reports" / f"drc-{variant}.json"
    manifest = ROOT / "reports" / f"drc-{variant}-evidence.json"
    state = {"drc_report": report.relative_to(ROOT).as_posix(), "complete": False}
    try:
        d = json.loads(report.read_text(encoding="utf-8"))
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(state, reason="DRC report or evidence manifest missing or unreadable")
    viol = d.get("violations") if isinstance(d, dict) else None
    unconn, parity = d.get("unconnected_items"), d.get("schematic_parity")
    if not all(isinstance(x, list) for x in (viol, unconn, parity)):
        return dict(state, reason="DRC report malformed")
    state.update(drc_report_sha256=sha256(report), unconnected=len(unconn), parity=len(parity),
                 errors=sum(v.get("severity") == "error" for v in viol if isinstance(v, dict)),
                 warnings=sum(v.get("severity") == "warning" for v in viol if isinstance(v, dict)))
    key = pcb.relative_to(ROOT).as_posix()
    if not isinstance(m, dict) or (m.get("inputs") or {}).get(key) != sha256(pcb):
        return dict(state, reason="DRC evidence does not match the current PCB")
    state["complete"] = state["unconnected"] == 0 and state["errors"] == 0 and state["parity"] == 0
    if not state["complete"]:
        state["reason"] = (f"{state['unconnected']} unconnected items, {state['errors']} DRC errors, "
                           f"{state['parity']} parity issues")
    return state


def generate_outputs(out: Path, pcb: Path, sch: Path, variant: str, check: dict) -> None:
    incomplete = not check["cad_state"]["complete"]
    warning = ("## INCOMPLETE BOARD - DO NOT FABRICATE\n\n"
               f"The board is not complete: {check['cad_state'].get('reason', 'DRC state unknown')}.\n"
               f"The fabrication ZIP carries `{INCOMPLETE_MARKER}`. These files are for layout review only.\n\n"
               if incomplete else "")
    (out / "REVIEW_ONLY.md").write_text(
        "# DRAFT - review only\n\n" + warning + "This package has not been released for manufacturing.\n"
        "`reports/export-check.json` checks exported file completeness and consistency; it does not close a release gate.\n"
        "Review the project's current `reports/validation-register.md` and `reports/release-readiness.md` before\n"
        "ordering a prototype: a prototype needs the PROTOTYPE_CANDIDATE level (complete CAD, current evidence and\n"
        "the recorded human reviews). A production release additionally needs the Gate G bench results from an\n"
        "assembled prototype and a signed approval. This tool does not place manufacturing orders.\n", encoding="utf-8")
    if incomplete:
        (out / INCOMPLETE_MARKER).write_text(
            f"DO NOT FABRICATE: {variant} is an incomplete PCB draft ({check['cad_state'].get('reason')}).\n"
            "These Gerber and drill files are for layout review only. See REVIEW_ONLY.md in the package.\n",
            encoding="utf-8")
    shutil.copyfile(ROOT / "documentation/stack-up.md", out / "drawings/stack-up.md")
    cli("pcb", "export", "gerbers", "--no-x2", "--no-netlist", "--subtract-soldermask", "--check-zones",
        "--use-drill-file-origin", "-l", ",".join(GERBER_LAYERS), "-o", out / "gerbers", pcb)
    cli("pcb", "export", "drill", "--format", "excellon", "--drill-origin", "plot", "--excellon-units", "mm",
        "--excellon-zeros-format", "decimal", "--excellon-separate-th", "--generate-map", "--map-format", "pdf",
        "-o", out / "drill", pcb)
    fps, origin = board_footprints(pcb)
    check["bom_lines"], check["bom_parts"], check["cpl_parts"] = write_assembly(out, fps, origin)
    cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin",
        "--exclude-dnp", "-o", out / "reports/kicad_pos.csv", pcb)
    check["problems"] += check_assembly(out, pcb)
    cli("sch", "export", "pdf", "-o", out / f"drawings/{PROJECT}_schematic.pdf", sch)
    for side, layers in (("top", "F.Fab,F.Courtyard,Edge.Cuts"), ("bottom", "B.Fab,B.Courtyard,Edge.Cuts")):
        args = ["pcb", "export", "pdf", "--mode-single", "-l", layers, "--include-border-title",
                "-o", out / f"drawings/assembly_{side}.pdf", pcb]
        if side == "bottom":
            args.insert(3, "--mirror")
        cli(*args)
    cli("pcb", "export", "pdf", "--mode-single", "-l", "Edge.Cuts,F.Cu,User.Drawings,User.Comments",
        "--include-border-title", "-o", out / "drawings/fab_outline.pdf", pcb)
    for side in ("top", "bottom"):
        cli("pcb", "render", "--side", side, "--quality", "basic", "--width", "1600", "--height", "1600",
            "--zoom", "1.0", "-o", out / f"drawings/render_{side}.png", pcb)
    # KiCad 10's argument parser rejects a vector beginning with '-'; 325 degrees equals -35.
    cli("pcb", "render", "--side", "top", "--quality", "basic", "--rotate", "325,0,30", "--width", "1600",
        "--height", "1200", "-o", out / "drawings/render_iso.png", pcb)
    ibom = ROOT / "tools/ibom/InteractiveHtmlBom/generate_interactive_bom.py"
    if not ibom.is_file():
        raise FileNotFoundError("InteractiveHtmlBom is required; run scripts/setup.ps1")
    env = dict(os.environ, INTERACTIVE_HTML_BOM_NO_DISPLAY="1")
    r = subprocess.run([str(paths.kicad_python()), str(ibom), str(pcb), "--no-browser", "--dest-dir",
                        str(out / "assembly"), "--name-format", "ibom", "--extra-fields", "MPN,Manufacturer",
                        "--include-tracks"], capture_output=True, text=True, timeout=300, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"InteractiveHtmlBom failed ({r.returncode}): {r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    fabrication = sorted(p for folder in ("gerbers", "drill") for p in (out / folder).iterdir() if p.is_file())
    if incomplete:
        fabrication.insert(0, out / INCOMPLETE_MARKER)
    zpath = out / f"{variant}-gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in fabrication:
            z.write(f, f.relative_to(out).as_posix())
    with zipfile.ZipFile(zpath) as z:
        if Counter(z.namelist()) != Counter(f.relative_to(out).as_posix() for f in fabrication) or z.testzip():
            check["problems"].append("fabrication ZIP is incomplete or corrupt")
        for f in fabrication:
            if hashlib.sha256(z.read(f.relative_to(out).as_posix())).hexdigest() != sha256(f):
                check["problems"].append(f"ZIP content differs from {f.name}")


def promote(staged: Path, destination: Path) -> None:
    """Keep the previous package until its checked replacement is in place."""
    parent = destination.parent.resolve()
    if staged.resolve().parent != parent or destination.resolve().parent != parent:
        raise ValueError("export directories must stay inside the package parent")
    backup = staged.with_name(staged.name + "-previous")
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        if backup.resolve().parent != parent:
            raise ValueError("backup resolved outside package parent")
        shutil.rmtree(backup)


def export(variant: str) -> dict:
    if variant not in spec.VARIANTS:
        raise ValueError(f"unknown PCB variant: {variant}")
    vdir = paths.HARDWARE / variant
    pcb, sch = vdir / f"{PROJECT}.kicad_pcb", vdir / f"{PROJECT}.kicad_sch"
    destination = paths.MANUFACTURING / "pcbway" / variant
    destination.parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix=f".{variant}-staging-", dir=destination.parent))
    for sub in ("gerbers", "drill", "assembly", "drawings", "reports"):
        (out / sub).mkdir()
    check = {"variant": variant, "problems": [], "files": {}, "file_sha256": {}, "inputs": {},
             "release_status": "DRAFT_REVIEW", "manufacturing_release": False,
             "required_files": required_files(variant), "bom_lines": 0, "bom_parts": 0, "cpl_parts": 0}
    check["cad_state"] = cad_state(variant, pcb) if pcb.is_file() else {"complete": False, "reason": "PCB missing"}
    check["package_class"] = "DRAFT_REVIEW" if check["cad_state"]["complete"] else "DRAFT_REVIEW_INCOMPLETE_BOARD"
    try:
        check["inputs"] = {p.relative_to(ROOT).as_posix(): sha256(p) for p in
                           (pcb, sch, vdir / f"{PROJECT}.kicad_pro", ROOT / "documentation/stack-up.md",
                            vdir / "placement.yaml", ROOT / "engineering/design/connectivity.yaml",
                            ROOT / "engineering/design/parameters.yaml")}
        generate_outputs(out, pcb, sch, variant, check)
        for rel, digest in check["inputs"].items():
            if sha256(ROOT / rel) != digest:
                check["problems"].append(f"CAD input changed during export: {rel}")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        check["problems"].append(f"{type(exc).__name__}: {exc}")
    check["problems"] += output_problems(out, variant)
    for f in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = f.relative_to(out).as_posix()
        check["files"][rel] = f.stat().st_size
        check["file_sha256"][rel] = sha256(f)
        if f.stat().st_size == 0:
            check["problems"].append(f"empty output: {rel}")
    check["status"] = "PASS" if not check["problems"] else "FAIL"
    check["output_directory"] = (destination if check["status"] == "PASS" else out).relative_to(ROOT).as_posix()
    (out / "reports/export-check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    if check["status"] == "PASS":
        promote(out, destination)
    return check


def _ref_key(ref: str):
    i = len(ref.rstrip("0123456789"))
    return (ref[:i], int(ref[i:] or 0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="compact-22mm", choices=spec.VARIANTS)
    res = export(ap.parse_args().variant)
    print(f"{res['variant']}: export {res['status']}; BOM {res['bom_parts']} parts, CPL {res['cpl_parts']}; "
          f"output: {res['output_directory']}; problems: {res['problems']}")
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
