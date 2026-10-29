"""Budget-2s routed-copper check: DC resistance of each power path against the power-model allocations.

  usage: .venv/Scripts/python.exe automation/budget/layout_review.py

The A/B copper extractor (automation/review/layout_extract.py) and DC solver (review.dcflow, review.raster)
are reused unchanged. Each path is a two-terminal solve between the listed pads at 25 C on the routed board,
scaled by power_model.copper_hot_factor. The output loop (L1 to J2 LD+, and the laser return from J2 LD- to
U1's power ground) is compared with power_model.output_copper_ohm_allocation. The input copper (J1 B+ to U1
VIN except the fuse and reverse FET, plus the return from U1's power ground to J1 B-) and the two XT30
contacts are subtracted from input_path_ohm_allocation; what is left is the hot resistance budget for the
fuse and its holder. DC only: no inductance, switching or copper-temperature model. Results select items
for review and never close a gate; bench data (Gate G) decides.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from budget import power  # noqa: E402
from nubm44 import evidence, paths  # noqa: E402
from nubm44.calc import copper  # noqa: E402
from nubm44.variants import BUDGET_VARIANT, sources_for  # noqa: E402
from review import dcflow  # noqa: E402
from review.power_layout import stack_from_params  # noqa: E402
from review.raster import CopperModel  # noqa: E402

SOURCES = sources_for(BUDGET_VARIANT)
BOARD = paths.HARDWARE / BUDGET_VARIANT / "nubm44_budget2s.kicad_pcb"
GEOMETRY = paths.BUILD / BUDGET_VARIANT / "layout-geometry.json"
OUT = paths.REPORTS / BUDGET_VARIANT
H_MM, H_GND_MM = 0.05, 0.1
SCREEN_TEMP_RISE_C = 20.0  # IPC-2221 equivalent width used only to flag necks for review (as A/B)

# net, from pads, to pads, current, group, description. Pins from engineering/design/budget-2s/connectivity.yaml.
PATHS = [
    ("VBAT_IN", ["J1.2"], ["F1.1"], "i_in", "input", "J1 B+ to fuse holder"),
    ("VBAT_F", ["F1.2"], ["Q1.5", "Q1.6", "Q1.7", "Q1.8"], "i_in", "input", "fuse holder to Q1 drain"),
    ("VBAT_P", ["Q1.1", "Q1.2", "Q1.3"], ["U1.4", "U1.5", "U1.6"], "i_in", "input", "Q1 source to U1 VIN"),
    ("GND", ["U1.15"], ["J1.1"], "i_in", "input", "U1 power ground to J1 B-"),
    ("PH", ["U1.11", "U1.12"], ["L1.1"], "i_laser", "converter", "U1 switch node to L1 (not in an allocation)"),
    ("VBUCK", ["L1.2"], ["RS1.1"], "i_laser", "output", "L1 to shunt"),
    ("VSH", ["RS1.2"], ["Q2.1", "Q2.2", "Q2.3"], "i_laser", "output", "shunt to Q2 source"),
    ("LASER_P", ["Q2.5"], ["J2.1"], "i_laser", "output", "Q2 drain to J2 LD+"),
    ("GND", ["J2.2"], ["U1.15"], "i_laser", "output", "J2 LD- to U1 power ground"),
]


def extract() -> dict:
    GEOMETRY.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(paths.kicad_python()), str(ROOT / "automation/review/layout_extract.py"),
                        str(BOARD), str(GEOMETRY)], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"layout extraction failed: {r.stdout}\n{r.stderr[-2000:]}")
    geo = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    if geo["board_sha256"] != evidence.sha256_file(BOARD):
        raise RuntimeError("board changed during extraction; rerun")
    return geo


def solve_paths(geo: dict, p: dict, currents: dict) -> list[dict]:
    hot_factor, oz = p["power_model"]["copper_hot_factor"], p["pcb"]["copper_oz"]
    models = {}
    out = []
    for net, src, snk, ikey, group, what in PATHS:
        h = H_GND_MM if net == "GND" else H_MM
        model = models.setdefault(h, CopperModel(geo, h))
        rec = {"net": net, "what": what, "group": group, "from": src, "to": snk}
        try:
            flow = dcflow.solve(model, net, {"src": (src, 1.0), "snk": (snk, 0.0)}, "snk",
                                stack_from_params(p, model.layers))
        except ValueError as exc:  # unrouted copper: report it, never invent a resistance
            out.append({**rec, "error": str(exc)})
            continue
        r25 = flow.resistance("src")
        i = currents[ikey]
        hot = dcflow.hot_area_k(flow, h)
        rec.update({"r_mohm_25c": round(r25 * 1e3, 3), "r_mohm_hot": round(r25 * hot_factor * 1e3, 3),
                    "current_a": round(i, 3), "loss_mw_hot": round(i * i * r25 * hot_factor * 1e3, 1)})
        if hot["layer"] is not None and hot["k_a_per_mm"] > 0:
            outer = hot["layer"] in (model.layers[0], model.layers[-1])
            screen = copper.ipc2221_width_mm(i, SCREEN_TEMP_RISE_C, oz, external=outer)
            width = 1 / hot["k_a_per_mm"]
            rec["neck"] = {"layer": hot["layer"],
                           "at_mm": [round(model.grid.x0 + (hot["x_idx"] + 0.5) * h, 2),  # board-centre origin,
                                     round(model.grid.y0 + (hot["y_idx"] + 0.5) * h, 2)],  # as placement.yaml
                           "equivalent_width_mm": round(width, 3), "screen_width_mm": round(screen, 3),
                           "flag": width < screen}
        out.append(rec)
    return out


def summarise(paths_: list[dict], p: dict) -> dict:
    m = p["power_model"]
    if any("error" in r for r in paths_):
        return {"ok": False, "reason": "unrouted copper on: " + ", ".join(r["net"] for r in paths_ if "error" in r)}
    total = lambda g: sum(r["r_mohm_hot"] for r in paths_ if r["group"] == g) / 1e3
    out_hot, in_hot = total("output"), total("input")
    contacts = 2 * m["connector_contact_ohm_each"]
    fuse_budget = m["input_path_ohm_allocation"] - in_hot - contacts
    necks = [f"{r['net']} ({r['what']})" for r in paths_ if r.get("neck", {}).get("flag")]
    return {"output_copper_ohm_hot": out_hot, "output_allocation_ohm": m["output_copper_ohm_allocation"],
            "output_ok": out_hot <= m["output_copper_ohm_allocation"],
            "input_copper_ohm_hot": in_hot, "connector_contacts_ohm": contacts,
            "input_allocation_ohm": m["input_path_ohm_allocation"], "fuse_and_holder_budget_ohm_hot": fuse_budget,
            "input_ok": fuse_budget > 0, "necks_flagged": necks,
            "ok": out_hot <= m["output_copper_ohm_allocation"] and fuse_budget > 0}


def markdown(paths_: list[dict], s: dict, currents: dict) -> str:
    lines = ["# Budget-2S routed-copper check", "",
             "Generated by `automation/budget/layout_review.py`; do not hand-edit. DC resistance of the routed",
             "copper between the listed pads (KiCad extraction, resistor-grid solve), scaled by the power model's",
             "hot-copper factor. DC only: inductance, switching and copper temperature are not modelled. These",
             "screens select items for review and never close a gate; bench data (Gate G) decides.", "",
             f"Currents: input {currents['i_in']:.3f} A and laser {currents['i_laser']:.3f} A at the nominal "
             "operating point of `automation/budget/power.py` (VBUCK auxiliary loads and ripple RMS neglected).", "",
             "| Group | Path | 25 °C mΩ | Hot mΩ | Current A | Hot loss mW | Neck (layer, at mm, equiv./screen width mm) |",
             "|---|---|---|---|---|---|---|"]
    for r in paths_:
        if "error" in r:
            lines.append(f"| {r['group']} | {r['net']}: {r['what']} | ERROR: {r['error']} | | | | |")
            continue
        n = r.get("neck")
        neck = (f"{n['layer']} ({n['at_mm'][0]}, {n['at_mm'][1]}), {n['equivalent_width_mm']}/{n['screen_width_mm']}"
                + (" **review**" if n["flag"] else "")) if n else "-"
        lines.append(f"| {r['group']} | {r['net']}: {r['what']} | {r['r_mohm_25c']} | {r['r_mohm_hot']} | "
                     f"{r['current_a']} | {r['loss_mw_hot']} | {neck} |")
    lines += [""]
    if "reason" in s:
        lines += [f"**Result: FAIL**: {s['reason']}.", ""]
    else:
        lines += [
            f"- **Output loop:** {s['output_copper_ohm_hot'] * 1e3:.3f} mΩ hot against the "
            f"{s['output_allocation_ohm'] * 1e3:g} mΩ `output_copper_ohm_allocation`: "
            + ("within the allocation." if s["output_ok"] else "**exceeds the allocation**."),
            f"- **Input path:** copper {s['input_copper_ohm_hot'] * 1e3:.3f} mΩ hot plus XT30 contacts "
            f"{s['connector_contacts_ohm'] * 1e3:g} mΩ (BUD-30) leaves **{s['fuse_and_holder_budget_ohm_hot'] * 1e3:.3f} mΩ** "
            f"for the fuse and holder (hot) inside the {s['input_allocation_ohm'] * 1e3:g} mΩ `input_path_ohm_allocation`. "
            "Fuse and holder resistance are UNKNOWN until a part is chosen; it must meet this figure.",
            "- **Necks flagged for review** (equivalent width below the IPC-2221 20 K screen): "
            + (", ".join(s["necks_flagged"]) or "none") + ".", ""]
    return "\n".join(lines)


def main() -> int:
    p = yaml.safe_load(SOURCES.parameters.read_text(encoding="utf-8"))
    t = p["targets"]
    fet = power.output_fet(p, p["disconnect"]["selected_output_mpn"])
    op = power.operating_point(p, fet, t["input_v_nominal"], t["laser_v_typ"], t["current_a"], "typical")
    currents = {"i_in": op["i_in_a"], "i_laser": op["i_laser_a"]}
    geo = extract()
    res = solve_paths(geo, p, currents)
    s = summarise(res, p)
    OUT.mkdir(parents=True, exist_ok=True)
    jp, md = OUT / "layout-review.json", OUT / "layout-review.md"
    jp.write_text(json.dumps({"paths": res, "summary": s, "currents_a": currents,
                              "grid_mm": {"power": H_MM, "ground": H_GND_MM}}, indent=1) + "\n", encoding="utf-8")
    md.write_text(markdown(res, s, currents), encoding="utf-8")
    evidence.write(evidence.build(
        "budget-layout-review", inputs=[BOARD, SOURCES.parameters, Path(__file__), Path(power.__file__),
                                        ROOT / "automation/review/layout_extract.py", ROOT / "automation/review/dcflow.py",
                                        ROOT / "automation/review/raster.py"],
        outputs=[jp, md], tools=evidence.python_tools(["numpy", "scipy", "PyYAML"])), OUT / "layout-review-evidence.json")
    for r in res:
        print(f"{r['group']:9} {r['net']:8} " + (f"ERROR {r['error']}" if "error" in r else
              f"{r['r_mohm_25c']:7.3f} mOhm 25C, {r['r_mohm_hot']:7.3f} hot, {r['loss_mw_hot']:6.1f} mW"))
    print(json.dumps(s, indent=1))
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
