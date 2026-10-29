"""Generate the budget-2s KiCad schematic from its own connectivity, run ERC and compare the netlist.

Reuses the A/B generator's block layout and pin-labelling helpers without changing them, so the A/B
evidence is unaffected. Sources: engineering/design/budget-2s/connectivity.yaml and the budget2s
library (automation/budget/build_library.py). Outputs: hardware/budget-2s/nubm44_budget2s.kicad_sch,
reports/budget-2s/erc.json, schematic.json, schematic.pdf and a hash manifest. Exit 0 only for 0 ERC errors and an
exact pin-by-pin netlist match; this is schematic evidence, not a PCB or release result.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import evidence, kicad_lib, netlist, paths  # noqa: E402
from nubm44.schematic import Schematic, snap  # noqa: E402
from nubm44.variants import BUDGET_VARIANT, sources_for  # noqa: E402

_ab_spec = importlib.util.spec_from_file_location("ab_build_schematic", ROOT / "automation/schematic/build_schematic.py")
ab = importlib.util.module_from_spec(_ab_spec)
_ab_spec.loader.exec_module(ab)

SOURCES = sources_for(BUDGET_VARIANT)
OUT_DIR = paths.HARDWARE / BUDGET_VARIANT
REPORTS = paths.REPORTS / BUDGET_VARIANT
PROJECT = "nubm44_budget2s"
LIB_FILES = [kicad_lib.BUDGET_LIB_DIR / f"{kicad_lib.BUDGET_LIB}.kicad_sym",
             *sorted((kicad_lib.BUDGET_LIB_DIR / "symbols").glob("*.yaml"))]


def load_spec() -> dict:
    spec = yaml.safe_load(SOURCES.connectivity.read_text(encoding="utf-8"))
    refs = [p["ref"] for p in spec["parts"]]
    if len(refs) != len(set(refs)):
        raise ValueError("duplicate reference designators in budget connectivity")
    for p in spec["parts"]:
        missing = {"ref", "block", "lib", "value", "footprint", "pins"} - p.keys()
        if missing or p["block"] not in spec["blocks"]:
            raise ValueError(f"{p.get('ref')}: missing {sorted(missing)} or unknown block")
        if not all(isinstance(n, str) and n for n in p["pins"].values()):
            raise ValueError(f"{p['ref']}: every pin needs a net name or NC")
    return spec


def layout_block(block: str, parts: list, per_row: int = 4) -> dict:
    """As the A/B layout, but multi-pin parts wrap into rows of `per_row` so wide blocks fit the sheet."""
    multi = [p for p in parts if len(p["pins"]) > 2 or (p["ref"].startswith("J") and len(p["pins"]) > 1)]
    two = [p for p in parts if p not in multi and not p["ref"].startswith(("TP", "J"))]
    single = [p for p in parts if p not in multi and p not in two]
    items, y, x_max = [], 15.24, 0.0
    for start in range(0, len(multi), per_row):
        x, row_h = 25.4, 0.0
        for p in multi[start:start + per_row]:
            x0, y0, x1, y1 = ab.symbol_extent(p["lib"])
            items.append((p, x - x0 + 2.54, y + y1 + 7.62, 0))
            x += (x1 - x0) + 50.8
            row_h = max(row_h, (y1 - y0) + 22.86)
        x_max, y = max(x_max, x), y + row_h
    cols = ab.BLOCK_COLS.get(block, 6)
    y_grid = y + 7.62
    for i, p in enumerate(two):
        col, row = i % cols, i // cols
        items.append((p, 12.7 + col * ab.CELL_W, y_grid + 10.16 + row * ab.CELL_H, ab.choose_rotation(p["lib"], p["pins"])))
    rows = -(-len(two) // cols) if two else 0
    y_single = y_grid + rows * ab.CELL_H + 12.7
    for i, p in enumerate(single):
        items.append((p, 17.78 + i * 30.48, y_single, 0))
    w = max(cols * ab.CELL_W + 5.08, x_max, 17.78 + len(single) * 30.48)
    return {"items": items, "w": w, "h": y_single + 15.24}


def build(spec: dict) -> Path:
    meta = spec["meta"]
    sch = Schematic(PROJECT, meta["title"], paper="A2", rev=str(meta["revision"]), date=str(meta["date"]),
                    company="NUBM44 driver project - budget-2s (separate circuit)",
                    comments=("Generated from engineering/design/budget-2s/connectivity.yaml - do not edit by hand",
                              "DRAFT: ELECTRICAL_QUALIFICATION, not for fabrication; footprints marked budget2s: are OPEN",
                              "Class 4 laser product: see documentation/testing for safety requirements"))
    by_block: dict[str, list] = {}
    for part in spec["parts"]:
        by_block.setdefault(part["block"], []).append(part)
    layouts = {block: layout_block(block, parts) for block, parts in by_block.items()}
    origins = ab.pack_blocks({b: (lay["w"], lay["h"]) for b, lay in layouts.items()})
    sch.paper = ab.pack_blocks.paper
    for block, lay in layouts.items():
        ox, oy = origins[block]
        for p, dx, dy, rot in lay["items"]:
            ab._place(sch, p, snap(ox + dx, ab.GRID), snap(oy + dy, ab.GRID), rot, {})
        sch.rect(ox, oy, snap(ox + lay["w"], ab.GRID), snap(oy + lay["h"], ab.GRID))
        sch.text(spec["blocks"][block], ox + 2.54, oy + 2.54, size=2.0, bold=True)
    pw = layouts["power_in"]
    fx, fy = origins["power_in"][0] + pw["w"] - 50.8, origins["power_in"][1] + 7.62
    for i, net in enumerate(spec["power_flags"]):
        x, y = snap(fx + i * 15.24, ab.GRID), snap(fy, ab.GRID)
        sch.flag(x, y, "up")
        sch.wire((x, y), (x, y + 5.08))
        if net == "GND":
            sch.place(f"#PWR9{i:02d}", "power:GND", x, y + 5.08, 0)
        else:
            sch.items.append(ab._label(sch, net, x, y + 5.08, 270))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sch_path = OUT_DIR / f"{PROJECT}.kicad_sch"
    sch.write(sch_path)
    write_project_files()
    return sch_path


def write_project_files() -> None:
    pro = OUT_DIR / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        tpl = json.loads((paths.kicad_share() / "template" / "kicad.kicad_pro").read_text(encoding="utf-8"))
        tpl.setdefault("meta", {})["filename"] = pro.name
        pro.write_text(json.dumps(tpl, indent=2), encoding="utf-8")
    lib = kicad_lib.BUDGET_LIB
    (OUT_DIR / "sym-lib-table").write_text(
        f'(sym_lib_table\n  (version 7)\n  (lib (name "{lib}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{lib}.kicad_sym")'
        '(options "")(descr "Budget-2S project symbols"))\n)\n', encoding="utf-8")
    (OUT_DIR / "fp-lib-table").write_text(
        f'(fp_lib_table\n  (version 7)\n  (lib (name "{lib}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{lib}.pretty")'
        '(options "")(descr "Budget-2S project footprints"))\n)\n', encoding="utf-8")


def verify(spec: dict, sch_path: Path) -> dict:
    cli = str(paths.kicad_cli())
    REPORTS.mkdir(parents=True, exist_ok=True)
    erc_json, summary_json, pdf = REPORTS / "erc.json", REPORTS / "schematic.json", REPORTS / "schematic.pdf"
    net_path = sch_path.with_suffix(".net")
    manifest = REPORTS / "schematic-evidence.json"
    for stale in (erc_json, summary_json, net_path, pdf, manifest):
        stale.unlink(missing_ok=True)
    run = lambda *args: subprocess.run([cli, *args], capture_output=True, text=True, check=True)
    up = run("sch", "upgrade", "--force", str(sch_path))
    erc = run("sch", "erc", "--format", "json", "--severity-all", "-o", str(erc_json), str(sch_path))
    export = run("sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(net_path), str(sch_path))
    run("sch", "export", "pdf", "-o", str(pdf), str(sch_path))
    data = json.loads(erc_json.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sheets"), list):
        raise ValueError(f"KiCad ERC produced an invalid report: {erc_json}")
    violations = [v for sh in data["sheets"] for v in sh.get("violations", [])]
    errors = [v for v in violations if v["severity"] == "error"]
    actual = netlist.read_kicad_netlist(net_path)
    nets = {name.lstrip("/"): pins for name, pins in actual["nets"].items()}
    problems = netlist.compare(netlist.nets_from_spec(spec["parts"]), nets)
    for p in spec["parts"]:
        comp = actual["components"].get(p["ref"])
        if comp is None:
            problems.append(f"{p['ref']}: missing from netlist")
        elif comp["footprint"] != p["footprint"]:
            problems.append(f"{p['ref']}: footprint {comp['footprint']} != spec {p['footprint']}")
    open_footprints = sorted({p["footprint"] for p in spec["parts"] if p["footprint"].startswith(kicad_lib.BUDGET_LIB + ":")
                              and not kicad_lib.footprint_path(p["footprint"]).exists()})
    result = {"variant": BUDGET_VARIANT, "schematic": sch_path.relative_to(ROOT).as_posix(),
              "upgrade_rc": up.returncode, "erc_rc": erc.returncode, "netlist_rc": export.returncode,
              "erc_errors": len(errors), "erc_warnings": sum(v["severity"] == "warning" for v in violations),
              "erc_violations": [{"severity": v["severity"], "type": v["type"], "description": v["description"],
                                  "items": [i.get("description", "") for i in v.get("items", [])]} for v in violations],
              "netlist_parts": len(actual["components"]), "netlist_nets": len(nets),
              "connectivity_differences": problems, "footprints_not_generated": open_footprints,
              "status": "PASS" if not errors and not problems else "FAIL",
              "scope": "schematic ERC and connectivity only; footprints, PCB and release remain OPEN"}
    summary_json.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    evidence.write(evidence.build(
        "budget-schematic", inputs=[SOURCES.connectivity, SOURCES.parameters, Path(__file__),
                                    ROOT / "automation/schematic/build_schematic.py", ROOT / "automation/nubm44/kicad_lib.py",
                                    *LIB_FILES],
        outputs=[sch_path, erc_json, summary_json, net_path, pdf],
        tools={"kicad-cli": evidence.command_version([cli, "version"])}), manifest)
    return result


def main() -> int:
    spec = load_spec()
    if (OUT_DIR / "MANUAL_EDITS").exists():
        print("budget-2s: MANUAL_EDITS present, schematic not regenerated (verifying only)")
        sch_path = OUT_DIR / f"{PROJECT}.kicad_sch"
    else:
        sch_path = build(spec)
    res = verify(spec, sch_path)
    print(f"budget-2s: ERC errors {res['erc_errors']}, warnings {res['erc_warnings']}, parts {res['netlist_parts']}, "
          f"nets {res['netlist_nets']}, connectivity differences {len(res['connectivity_differences'])}, "
          f"footprints not generated {res['footprints_not_generated']} -> {res['status']}")
    for v in res["erc_violations"][:60]:
        print(f"   ERC {v['severity']}: {v['type']}: {v['description']} {v['items']}")
    for d in res["connectivity_differences"][:40]:
        print(f"   NET {d}")
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
