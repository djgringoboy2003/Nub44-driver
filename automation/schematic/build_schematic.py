"""Generate the KiCad schematic (and project files) for each PCB variant from connectivity.yaml.

For each variant:
  1. lay out every functional block, place real library symbols and connect every pin with
     wires + net labels (GND pins get GND power symbols, NC pins get no-connect flags);
  2. write <variant>/nubm44_driver.kicad_sch plus .kicad_pro and project library tables;
  3. upgrade to the native KiCad 10 format (kicad-cli sch upgrade);
  4. run ERC and export the netlist (kicad-cli);
  5. compare the netlist pin-by-pin with connectivity.yaml.

Results are written to reports/schematic-<variant>.json. Exit code is non-zero when ERC has errors
or the netlist differs from the specification.

Usage:  .venv\\Scripts\\python.exe automation\\schematic\\build_schematic.py [--variant compact-22mm|evaluation-board]
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import kicad_lib, netlist, paths, spec as spec_mod  # noqa: E402
from nubm44.schematic import Schematic, snap, xform  # noqa: E402

SPEC = ROOT / "engineering/design/connectivity.yaml"
VARIANTS = {
    "compact-22mm": {"title": "NUBM44 driver - Variant A (22 mm)", "fp_key": "footprint"},
    "evaluation-board": {"title": "NUBM44 driver - Variant B (evaluation board)", "fp_key": "footprint_eval"},
}
PROJECT = "nubm44_driver"
GRID = 2.54

# block placement on an A2 sheet (594 x 420 mm): origin (top-left) of each block frame
BLOCK_ORIGIN = {
    "power_in": (15.24, 25.4),
    "converter": (15.24, 132.08),
    "sense": (309.88, 25.4),
    "enable": (309.88, 132.08),
    "control": (309.88, 238.76),
}
BLOCK_COLS = {"power_in": 6, "converter": 8, "sense": 6, "enable": 6, "control": 8}
CELL_W, CELL_H = 30.48, 22.86


def load_spec() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------ geometry helpers
def pin_points(sch: Schematic, ref: str) -> dict:
    """Map (x, y) -> list of pin numbers for a placed symbol (stacked pins share a point)."""
    p = sch._get(ref)
    pts: dict[tuple, list] = {}
    for num, info in p.pins.items():
        xy = xform(info["x"], info["y"], p.x, p.y, p.rot)
        pts.setdefault(xy, []).append(num)
    return pts


def choose_rotation(lib_id: str, pins: dict) -> int:
    """For 2-pin parts: GND pin points down; otherwise pin 1 points up."""
    sym = kicad_lib.get_symbol(lib_id)
    sp = kicad_lib.symbol_pins(sym)
    if len(sp) != 2:
        return 0
    want_down = next((n for n, net in pins.items() if net == "GND"), None)
    for rot in (0, 90, 180, 270):
        dirs = {}
        for num, info in sp.items():
            a = math.radians(info["angle"])
            x0, y0 = xform(info["x"], info["y"], 0, 0, rot)
            x1, y1 = xform(info["x"] - math.cos(a), info["y"] - math.sin(a), 0, 0, rot)
            dirs[num] = "down" if y1 - y0 > 0.5 else "up" if y0 - y1 > 0.5 else "side"
        if want_down is not None:
            if dirs.get(str(want_down)) == "down":
                return rot
        elif dirs.get("1") == "up":
            return rot
    return 0


def symbol_extent(lib_id: str) -> tuple[float, float, float, float]:
    """Approximate symbol bounding box from pin end points (library coordinates)."""
    sp = kicad_lib.symbol_pins(kicad_lib.get_symbol(lib_id))
    xs = [v["x"] for v in sp.values()] or [0]
    ys = [v["y"] for v in sp.values()] or [0]
    return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------------ layout
SHEET = {"A2": (594.0, 420.0), "A1": (841.0, 594.0)}
MARGIN = 12.7
TITLE_BLOCK_H = 45.0


def layout_block(block: str, parts: list) -> dict:
    """Relative placement of one block: multi-pin parts in a top row, two-pin parts in a grid,
    single-pin parts (contacts, test pads) in a final row."""
    multi = [p for p in parts if len(p["pins"]) > 2 or (p["ref"].startswith("J") and len(p["pins"]) > 1)]
    two = [p for p in parts if p not in multi and not p["ref"].startswith(("TP", "J"))]
    single = [p for p in parts if p not in multi and p not in two]
    items = []
    x, row_h = 25.4, 0.0
    for p in multi:
        x0, y0, x1, y1 = symbol_extent(p["lib"])
        items.append((p, x - x0 + 2.54, 15.24 + y1 + 7.62, 0))
        x += (x1 - x0) + 50.8
        row_h = max(row_h, (y1 - y0) + 22.86)
    cols = BLOCK_COLS[block]
    y_grid = 15.24 + row_h + 7.62
    for i, p in enumerate(two):
        col, row = i % cols, i // cols
        items.append((p, 12.7 + col * CELL_W, y_grid + 10.16 + row * CELL_H, choose_rotation(p["lib"], p["pins"])))
    rows = math.ceil(len(two) / cols) if two else 0
    y_single = y_grid + rows * CELL_H + 12.7
    for i, p in enumerate(single):
        items.append((p, 17.78 + i * 30.48, y_single, 0))
    w = max(cols * CELL_W + 5.08, x, 17.78 + len(single) * 30.48)
    return {"items": items, "w": w, "h": y_single + 15.24}


def pack_blocks(sizes: dict) -> dict:
    """Stack blocks into columns (in spec order) so nothing overlaps the frame or the title block."""
    for paper in ("A2", "A1"):
        sw, sh = SHEET[paper]
        usable_h = sh - 2 * MARGIN - TITLE_BLOCK_H
        origins, x, y, col_w = {}, MARGIN + 2.54, MARGIN + 2.54, 0.0
        ok = True
        for block, (w, h) in sizes.items():
            if y + h > MARGIN + usable_h and y > MARGIN + 2.54:
                x, y, col_w = x + col_w + 7.62, MARGIN + 2.54, 0.0
            origins[block] = (snap(x, GRID), snap(y, GRID))
            y += h + 7.62
            col_w = max(col_w, w)
            if x + w > sw - MARGIN or y - 7.62 > MARGIN + usable_h:
                ok = False
        if ok:
            pack_blocks.paper = paper
            return origins
    raise RuntimeError("schematic blocks do not fit on A1; reduce block sizes")


# ------------------------------------------------------------------------ build
def build(variant: str, spec: dict) -> Path:
    cfg = VARIANTS[variant]
    out_dir = paths.HARDWARE / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = spec["meta"]
    sch = Schematic(PROJECT, cfg["title"], paper="A2", rev=str(meta["revision"]), date=str(meta["date"]),
                    company="NUBM44 driver project",
                    comments=("Generated from engineering/design/connectivity.yaml - do not edit by hand",
                              "Battery polarity: centre spring = B+, ring = B- (REQ-BAT-04/DD-12; marked on the silkscreen)",
                              "Class 4 laser product: see documentation/testing for safety requirements"))

    by_block: dict[str, list] = {}
    for part in spec_mod.parts_for(variant):
        by_block.setdefault(part["block"], []).append(part)

    layouts = {block: layout_block(block, parts) for block, parts in by_block.items()}
    origins = pack_blocks({b: (lay["w"], lay["h"]) for b, lay in layouts.items()})
    sch.paper = pack_blocks.paper
    for block, lay in layouts.items():
        ox, oy = origins[block]
        for p, dx, dy, rot in lay["items"]:
            _place(sch, p, snap(ox + dx, GRID), snap(oy + dy, GRID), rot, cfg)
        sch.rect(ox, oy, snap(ox + lay["w"], GRID), snap(oy + lay["h"], GRID))
        sch.text(spec["blocks"][block], ox + 2.54, oy + 2.54, size=2.0, bold=True)

    # power flags in the free space at the top-right of the power-input block
    pw = layouts["power_in"]
    fx, fy = origins["power_in"][0] + pw["w"] - 50.8, origins["power_in"][1] + 7.62
    for i, net in enumerate(spec["power_flags"]):
        x, y = snap(fx + i * 15.24, GRID), snap(fy, GRID)
        sch.flag(x, y, "up")
        sch.wire((x, y), (x, y + 5.08))
        if net == "GND":
            sch.place(f"#PWR9{i:02d}", "power:GND", x, y + 5.08, 0)
        else:
            sch.items.append(_label(sch, net, x, y + 5.08, 270))

    sch_path = out_dir / f"{PROJECT}.kicad_sch"
    sch.write(sch_path)
    _write_project_files(out_dir)
    return sch_path


def _label(sch: Schematic, net: str, x: float, y: float, angle: int):
    from nubm44.schematic import FONT, uid
    from nubm44.sexpr import S, Sym
    justify = [Sym("left"), Sym("bottom")] if angle in (0, 90) else [Sym("right"), Sym("bottom")]
    return S("label", net, S("at", x, y, angle), S("fields_autoplaced", Sym("yes")),
             S("effects", FONT, S("justify", *justify)), S("uuid", uid(sch.project, "flaglabel", net, x, y)))


def _place(sch: Schematic, p: dict, x: float, y: float, rot: int, cfg: dict) -> None:
    fields = {"MPN": p.get("mpn", ""), "Manufacturer": p.get("mfr", ""), "Block": p["block"]}
    if p.get("alt"):
        fields["Alternate"] = p["alt"]
    fp = p["footprint"]          # already resolved for the variant by spec_mod.parts_for
    lib_sym = kicad_lib.get_symbol(p["lib"])
    is_external_pad = p["ref"].startswith(("TP", "J"))
    sch.place(p["ref"], p["lib"], x, y, rot, value=str(p["value"]), footprint=fp,
              datasheet=p.get("datasheet", "~"), description=p.get("desc", ""), fields=fields,
              in_bom=p.get("in_bom", True), dnp=p.get("dnp", False))
    for xy, nums in pin_points(sch, p["ref"]).items():
        nets = {str(p["pins"].get(int(n), p["pins"].get(n))) for n in nums}
        if len(nets) != 1:
            raise ValueError(f"{p['ref']}: stacked pins {nums} have different nets {nets}")
        net = nets.pop()
        n0 = nums[0]
        if net == "NC":
            sch.no_connect(p["ref"], n0)
        elif net == "GND" and not is_external_pad:
            sch.power(p["ref"], n0, "power:GND")
        else:
            two_pin = len(kicad_lib.symbol_pins(lib_sym)) == 2
            _bent_label(sch, p["ref"], n0, net, bend=two_pin)


def _bent_label(sch: Schematic, ref: str, pin: str, net: str, bend: bool) -> None:
    """Label at the end of a pin stub; vertical stubs on two-pin parts bend right for horizontal text."""
    x0, y0, d = sch.pin_end(ref, pin)
    if d in ("up", "down") and bend:
        dy = -2.54 if d == "up" else 2.54
        x1, y1 = x0, round(y0 + dy, 4)
        x2 = round(x1 + 2.54, 4)
        sch.wire((x0, y0), (x1, y1), (x2, y1))
        sch.items.append(_label(sch, net, x2, y1, 0))
    else:
        sch.label(ref, pin, net)


def _write_project_files(out_dir: Path) -> None:
    pro = out_dir / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        tpl = json.loads((paths.kicad_share() / "template" / "kicad.kicad_pro").read_text(encoding="utf-8"))
        tpl.setdefault("meta", {})["filename"] = pro.name
        pro.write_text(json.dumps(tpl, indent=2), encoding="utf-8")
    (out_dir / "sym-lib-table").write_text(
        '(sym_lib_table\n  (version 7)\n  (lib (name "nubm44")(type "KiCad")(uri "${KIPRJMOD}/../libraries/nubm44.kicad_sym")'
        '(options "")(descr "NUBM44 driver project symbols"))\n)\n', encoding="utf-8")
    (out_dir / "fp-lib-table").write_text(
        '(fp_lib_table\n  (version 7)\n  (lib (name "nubm44")(type "KiCad")(uri "${KIPRJMOD}/../libraries/nubm44.pretty")'
        '(options "")(descr "NUBM44 driver project footprints"))\n)\n', encoding="utf-8")


# ------------------------------------------------------------------------ verification
def verify(variant: str, spec: dict, sch_path: Path) -> dict:
    cli = str(paths.kicad_cli())
    rep_dir = paths.REPORTS
    rep_dir.mkdir(parents=True, exist_ok=True)
    erc_json = rep_dir / f"erc-{variant}.json"
    summary_json = rep_dir / f"schematic-{variant}.json"
    net_path = sch_path.with_suffix(".net")
    # A failed command must never leave previous passing evidence available.
    for stale in (erc_json, summary_json, net_path):
        stale.unlink(missing_ok=True)
    up = subprocess.run([cli, "sch", "upgrade", "--force", str(sch_path)], capture_output=True, text=True,
                        check=True)
    erc = subprocess.run([cli, "sch", "erc", "--format", "json", "--severity-all", "-o", str(erc_json),
                          str(sch_path)], capture_output=True, text=True, check=True)
    export = subprocess.run([cli, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(net_path),
                             str(sch_path)], capture_output=True, text=True, check=True)
    data = json.loads(erc_json.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sheets"), list):
        raise ValueError(f"KiCad ERC produced an invalid report: {erc_json}")
    violations = [v for sh in data.get("sheets", []) for v in sh.get("violations", [])]
    errors = [v for v in violations if v["severity"] == "error"]
    warnings = [v for v in violations if v["severity"] == "warning"]

    actual = netlist.read_kicad_netlist(net_path)
    nets = {name.lstrip("/"): pins for name, pins in actual["nets"].items()}
    parts = spec_mod.parts_for(variant)
    intended = netlist.nets_from_spec(parts)
    problems = netlist.compare(intended, nets)
    # every placed part must be in the netlist with the variant's footprint
    for p in parts:
        comp = actual["components"].get(p["ref"])
        want = p["footprint"]
        if comp is None:
            problems.append(f"{p['ref']}: missing from netlist")
        elif comp["footprint"] != want:
            problems.append(f"{p['ref']}: footprint {comp['footprint']} != spec {want}")
    result = {
        "variant": variant, "schematic": str(sch_path.relative_to(ROOT)),
        "upgrade_rc": up.returncode, "erc_rc": erc.returncode, "netlist_rc": export.returncode,
        "erc_errors": len(errors), "erc_warnings": len(warnings),
        "erc_violations": [{"severity": v["severity"], "type": v["type"], "description": v["description"],
                            "items": [i.get("description", "") for i in v.get("items", [])]} for v in violations],
        "netlist_parts": len(actual["components"]), "netlist_nets": len(nets),
        "connectivity_differences": problems,
        "status": "PASS" if not errors and not problems else "FAIL",
    }
    summary_json.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=list(VARIANTS), action="append")
    args = ap.parse_args()
    spec = load_spec()
    rc = 0
    for variant in args.variant or list(VARIANTS):
        if (paths.HARDWARE / variant / "MANUAL_EDITS").exists():
            print(f"{variant}: MANUAL_EDITS present, schematic not regenerated (verifying only)")
            sch_path = paths.HARDWARE / variant / f"{PROJECT}.kicad_sch"
        else:
            sch_path = build(variant, spec)
        res = verify(variant, spec, sch_path)
        print(f"{variant}: ERC errors {res['erc_errors']}, warnings {res['erc_warnings']}, "
              f"parts {res['netlist_parts']}, nets {res['netlist_nets']}, "
              f"connectivity differences {len(res['connectivity_differences'])} -> {res['status']}")
        for v in res["erc_violations"][:40]:
            print(f"   ERC {v['severity']}: {v['type']}: {v['description']} {v['items']}")
        for d in res["connectivity_differences"][:40]:
            print(f"   NET {d}")
        rc |= res["status"] != "PASS"
    return rc


if __name__ == "__main__":
    sys.exit(main())
