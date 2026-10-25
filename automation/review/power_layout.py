"""Power-layout review of a routed PCB variant.

  usage: .venv\\Scripts\\python.exe automation\\review\\power_layout.py --variant evaluation-board

1. KiCad's Python extracts the routed copper (layout_extract.py) into build/<variant>/.
2. DC current flow through every power net at the calculated operating points (dcflow.py):
   path resistance, I^2R loss, current per unit width (necks), via currents and the ground
   offsets seen by the quiet references.
3. Geometry of the TPS552882 layout guidelines (SLVSFC5 section 10.1, source LEAD-01): hot loops,
   gate/bootstrap/VCC loops, the ISP/ISN Kelvin pair, sensitive nets near switching copper and
   vias near the IC power pins.
4. reports/layout-review-<variant>.json and .md, figures in reports/layout-review/<variant>/.

Screening criteria are stated with each result. They are engineering heuristics that select items
for human review; they never close or open a release gate. DC copper analysis says nothing about
inductance or switching waveforms, and copper temperature is not modelled. Only bench data (Gate G)
can establish thermal and switching behaviour.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage, sparse
from scipy.sparse import csgraph

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import paths  # noqa: E402
from nubm44.calc import copper  # noqa: E402
from review import dcflow  # noqa: E402
from review.raster import CopperModel, norm  # noqa: E402

PROJECT = "nubm44_driver"
PARAMS = ROOT / "engineering/design/parameters.yaml"
CALC = ROOT / "engineering/calculations/power-stage-results.json"

# Boost-mode DC paths (all operating points are boost or transition; Q2 on, Q3 off).
# Terminal pads follow engineering/design/connectivity.yaml pin numbers.
POWER_PATHS = [
    {"net": "BAT_SPRING", "src": ["J1.1"], "snk": ["Q1.5"], "current": "i_in",
     "what": "battery B+ contact to Q1 drain"},
    {"net": "VBAT", "src": ["Q1.1", "Q1.2", "Q1.3"], "snk": ["Q2.5"], "current": "i_in",
     "what": "Q1 source to Q2 drain"},
    {"net": "SW1", "src": ["Q2.1", "Q2.2", "Q2.3"], "snk": ["L1.1"], "current": "i_l_rms",
     "what": "Q2 source to L1"},
    {"net": "SW2", "src": ["L1.2"], "snk": ["U1.21", "U1.25"], "current": "i_l_rms",
     "what": "L1 to U1 SW2 pins 21/25"},
    {"net": "VOUT", "src": ["U1.11", "U1.26"], "snk": ["RS1.1"], "current": "i_out",
     "what": "U1 VOUT pins 11/26 to shunt"},
    {"net": "LD_P", "src": ["RS1.4"], "snk": ["J3.1"], "current": "i_out",
     "what": "shunt to laser LD+ pad"},
]
# Ground: laser return (J3.2) and converter power-ground current (U1 PGND 9/24) to the battery B- contact.
GND_SOURCES = {"laser_return": (["J3.2"], "i_out"), "converter_pgnd": (["U1.9", "U1.24"], "i_pgnd")}
GND_SINK = ["J2.1"]
# Ground pads of the quiet references; offsets are reported relative to U1 AGND (pin 10).
QUIET_GND = ["U1.10", "U1.7", "U1.15", "C7.2", "R9.2", "R2.2", "R3.2", "C8.2", "C9.2", "U2.1", "U2.2",
             "C15.2", "R6.2", "R11.2", "R13.2", "U3.3"]

HOT_LOOPS = {
    # SLVSFC5 10.1: input capacitor -> buck switching FET -> buck rectifier FET -> PGND -> capacitor
    "buck_input": {"caps": ["C1", "C2", "C3"], "cap_hot": "VBAT",
                   "path": ["{cap}.1", ["Q2.5"], ["Q2.1", "Q2.2", "Q2.3", "Q3.5"], ["Q3.1", "Q3.2", "Q3.3"], "{cap}.2"],
                   "hot_net": ("VBAT", "{cap}.1", ["Q2.5"]), "gnd_leg": ("{cap}.2", ["Q3.1", "Q3.2", "Q3.3"])},
    # SLVSFC5 10.1: input capacitor close to the VIN pin and PGND (U1 supply decoupling)
    "u1_vin": {"caps": ["C4"], "cap_hot": "VBAT",
               "path": ["{cap}.1", ["U1.3"], ["U1.9", "U1.24"], "{cap}.2"],
               "hot_net": ("VBAT", "{cap}.1", ["U1.3"]), "gnd_leg": ("{cap}.2", ["U1.9", "U1.24"])},
    # boost switch -> rectifier -> output capacitors -> PGND of the switch (VOUT/PGND pins of U1)
    "boost_output": {"caps": ["C10", "C11", "C12", "C13", "C14"], "cap_hot": "VOUT",
                     "path": [["U1.11", "U1.26"], "{cap}.1", "{cap}.2", ["U1.9", "U1.24"]],
                     "hot_net": ("VOUT", "{cap}.1", ["U1.11", "U1.26"]), "gnd_leg": ("{cap}.2", ["U1.9", "U1.24"])},
}
DRIVE_LOOPS = [
    # signal net, its pads, return net, return pads, what
    {"net": "DR1H", "pads": ["U1.2", "Q2.4"], "ret": "SW1", "ret_pads": ["Q2.1", "U1.23"], "what": "buck high-side gate"},
    {"net": "DR1L", "pads": ["U1.1", "Q3.4"], "ret": "GND", "ret_pads": ["Q3.1", "U1.9"], "what": "buck low-side gate"},
    {"net": "BOOT1", "pads": ["U1.22", "C5.1"], "ret": "SW1", "ret_pads": ["C5.2", "U1.23"], "what": "buck bootstrap"},
    {"net": "BOOT2", "pads": ["U1.20", "C6.1"], "ret": "SW2", "ret_pads": ["C6.2", "U1.21"], "what": "boost bootstrap"},
    {"net": "VCC5", "pads": ["U1.19", "C7.1"], "ret": "GND", "ret_pads": ["C7.2", "U1.10"], "what": "VCC/driver supply"},
]
SENSITIVE = ["FB", "COMP", "COMP_RC", "FSW", "ILIM", "ISP_K", "ISN_K", "CS_OUT", "EN_UVLO"]
AGGRESSORS = ["SW1", "SW2", "BOOT1", "BOOT2", "DR1H", "DR1L"]
HIGH_Z = ["FB", "COMP", "COMP_RC", "FSW", "ILIM", "EN_UVLO"]

# Screening heuristics (not limits): see the report text for their meaning.
SCREEN_TEMP_RISE_C = 20.0          # IPC-2221 long-trace equivalent used to screen necks
SCREEN_VIA_A = 1.0                 # copper.vias_for_current rule of thumb for a 0.3 mm via
SCREEN_HIGH_Z_SPACING_MM = 0.5     # about 3x the 0.15 mm clearance rule
SCREEN_SETPOINT_PCT = 0.1          # DC ground-offset share of the 5 % current tolerance budget


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ inputs
def extract(variant: str) -> Path:
    board = paths.HARDWARE / variant / f"{PROJECT}.kicad_pcb"
    out = paths.BUILD / variant / "layout-geometry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(paths.kicad_python()), str(ROOT / "automation/review/layout_extract.py"),
                        str(board), str(out)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"layout extraction failed: {r.stdout}\n{r.stderr[-2000:]}")
    geo = json.loads(out.read_text(encoding="utf-8"))
    if geo["board_sha256"] != sha(board):
        raise RuntimeError("board changed during extraction; rerun")
    return out


def stack_from_params(p: dict, layers: list[str], temp_c: float = 25.0) -> dcflow.Stack:
    pcb = p["pcb"]
    cu = pcb["copper_oz"] * copper.OZ_TO_M * 1000
    outer_gap = pcb["prepreg_mm"] + cu
    if len(layers) == 4:
        gaps = [outer_gap, pcb["board_thickness_mm"] - 2 * outer_gap, outer_gap]
    elif len(layers) == 2:
        gaps = [pcb["board_thickness_mm"]]
    else:
        raise ValueError(f"unsupported copper layer count {len(layers)}")
    return dcflow.Stack(copper_mm={l: cu for l in layers}, gaps_mm=gaps,
                        plating_mm=pcb["via_plating_um"] / 1000, temp_c=temp_c)


def operating_points(calc: dict) -> dict:
    pts = calc["operating_points"]
    worst = max(pts, key=lambda p: p["i_in"])
    nominal = next(p for p in pts if p["corner"] == "typ_25C" and abs(p["v_in"] - 4.0) < 1e-9)
    out = {}
    for name, p in (("worst", worst), ("nominal", nominal)):
        i_l_rms = math.sqrt(p["i_l_avg"] ** 2 + p["ripple_pp"] ** 2 / 12)
        out[name] = {"corner": p["corner"], "v_in": p["v_in"], "region": p["region"], "i_in": p["i_in"],
                     "i_l_rms": i_l_rms, "i_out": p["i_out"], "i_pgnd": max(p["i_in"] - p["i_out"], 0.0),
                     "p_laser": p["p_laser"], "p_in": p["p_in"], "efficiency": p["efficiency"],
                     "model_input_path_w": p["losses"]["input_path_I2R"],
                     "model_output_path_w": p["losses"]["output_path_I2R"]}
    return out


# ------------------------------------------------------------------ geometry helpers
def centroid(model, pads: list[str]) -> tuple[float, float]:
    ids = [i for s in pads for i in model.pad_ids(s)]
    return (float(np.mean([model.pads[i]["x"] for i in ids])), float(np.mean([model.pads[i]["y"] for i in ids])))


def shoelace(pts) -> float:
    return 0.5 * abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts))))


def geodesic_mm(model, net: str, layers: list[str], src: list[str], dst: list[str], stack) -> float:
    """Shortest path through the net's copper from any src pad to any dst pad (8-connected cells,
    via barrels cost their layer spacing). inf when the copper on these layers does not join them."""
    g, h = model.grid, model.grid.h
    masks = {l: model.mask(net, l) for l in layers}
    index, off = {}, 0
    for l in layers:
        idx = np.full(masks[l].shape, -1, dtype=np.int64)
        n = int(masks[l].sum())
        idx[masks[l]] = np.arange(off, off + n)
        index[l], off = idx, off + n
    ea, eb, ew = [], [], []
    steps = ((0, 1, h), (1, 0, h), (1, 1, h * math.sqrt(2)), (1, -1, h * math.sqrt(2)))
    ny, nx = g.ny, g.nx
    for l in layers:
        idx = index[l]
        for di, dj, w in steps:
            a = idx[0:ny - di, max(0, -dj):nx - max(0, dj)]
            b = idx[di:ny, max(0, dj):nx - max(0, -dj)]
            ok = (a >= 0) & (b >= 0)
            ea.append(a[ok]); eb.append(b[ok]); ew.append(np.full(int(ok.sum()), w))
    for v in model.geo["vias"]:
        if norm(v["net"]) != net:
            continue
        span = [l for l in v["layers"] if l in layers]
        for la, lb in zip(span[:-1], span[1:]):
            ia, ib = g.cell(v["x"], v["y"])
            a, b = index[la][ia, ib], index[lb][ia, ib]
            if a >= 0 and b >= 0:
                k = model.layers.index(la)
                ea.append(np.array([a])); eb.append(np.array([b]))
                ew.append(np.array([sum(stack.gaps_mm[k:model.layers.index(lb)])]))
    n = off + 1
    s_node = off
    for spec in src:
        for pid in model.pad_ids(spec):
            for l in model.pads[pid]["layers"]:
                if l in index:
                    cells = index[l][model.pad_mask(pid, l) & masks[l]]
                    ea.append(np.full(cells.size, s_node)); eb.append(cells); ew.append(np.full(cells.size, 1e-9))
    if not ea:
        return math.inf
    a, b, w = np.concatenate(ea), np.concatenate(eb), np.concatenate(ew)
    graph = sparse.coo_matrix((w, (a, b)), shape=(n, n)).tocsr()
    dist = csgraph.dijkstra(graph, directed=False, indices=s_node)
    best = math.inf
    for spec in dst:
        for pid in model.pad_ids(spec):
            for l in model.pads[pid]["layers"]:
                if l in index:
                    cells = index[l][model.pad_mask(pid, l) & masks[l]]
                    if cells.size:
                        best = min(best, float(dist[cells].min()))
    return best


def track_samples(model, net: str, step: float):
    """(layer, x, y, ds) samples along the net's routed track centrelines."""
    out = []
    for t in model.geo["tracks"]:
        if norm(t["net"]) != net:
            continue
        (x0, y0), (x1, y1) = t["a"], t["b"]
        length = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(length / step)))
        for k in range(n):
            f = (k + 0.5) / n
            out.append((t["layer"], x0 + f * (x1 - x0), y0 + f * (y1 - y0), length / n))
    return out


def route_stats(model, net: str) -> dict:
    tracks = [t for t in model.geo["tracks"] if norm(t["net"]) == net]
    vias = [v for v in model.geo["vias"] if norm(v["net"]) == net]
    length = sum(math.hypot(t["b"][0] - t["a"][0], t["b"][1] - t["a"][1]) for t in tracks)
    return {"track_length_mm": round(length, 2), "vias": len(vias),
            "layers": sorted({t["layer"] for t in tracks}, key=model.layers.index),
            "min_width_mm": round(min((t["w"] for t in tracks), default=0.0), 3)}


def return_distance_fields(model, ret_net: str, stack) -> dict:
    """In-plane distance (mm) from every cell to the nearest copper of ret_net on each layer
    (inf on a layer without such copper)."""
    out = {}
    for l in model.layers:
        m = model.mask(ret_net, l)
        out[l] = ndimage.distance_transform_edt(~m) * model.grid.h if m.any() else np.full(m.shape, np.inf)
    return out


def loop_area(model, net: str, ret_net: str, stack, fields=None) -> dict:
    """Loop-area estimate of a signal track and its return: sum of segment length x 3-D distance to
    the nearest return-net copper on any layer (in-plane distance combined with the layer spacing)."""
    fields = fields or return_distance_fields(model, ret_net, stack)
    z = np.concatenate([[0.0], np.cumsum(stack.gaps_mm)])
    area, worst = 0.0, 0.0
    for layer, x, y, ds in track_samples(model, net, model.grid.h):
        i, j = model.grid.cell(x, y)
        k = model.layers.index(layer)
        d = min(math.hypot(fields[l][i, j], z[kk] - z[k]) for kk, l in enumerate(model.layers))
        area += d * ds
        worst = max(worst, d)
    return {"loop_area_mm2": _finite(area), "max_return_distance_mm": _finite(worst)}


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def pair_separation(model, net_a: str, net_b: str, stack) -> dict:
    """Separation of two routed nets (Kelvin pair): distance from each sample of one net's tracks to
    the nearest track of the other (adding layer spacing when on different layers)."""
    tracks = {n: [t for t in model.geo["tracks"] if norm(t["net"]) == n] for n in (net_a, net_b)}
    res = {}
    for net, other in ((net_a, net_b), (net_b, net_a)):
        area, worst, long_sep = 0.0, 0.0, 0.0
        for layer, x, y, ds in track_samples(model, net, model.grid.h):
            best = math.inf
            for t in tracks[other]:
                d = seg_dist(x, y, t["a"], t["b"])
                if t["layer"] != layer:
                    ka, kb = sorted((model.layers.index(layer), model.layers.index(t["layer"])))
                    d = math.hypot(d, sum(stack.gaps_mm[ka:kb]))
                best = min(best, d)
            area += best * ds
            worst = max(worst, best)
            if best > 1.0:
                long_sep += ds
        res[net] = {"enclosed_area_mm2": round(area, 2), "max_separation_mm": round(worst, 2),
                    "length_separated_over_1mm": round(long_sep, 2)}
    return res


# ------------------------------------------------------------------ analyses
def flow_paths(model, geo, params, ops, h_gnd, figdir):
    out, figures = [], []
    h = model.grid.h
    st = stack_from_params(params, model.layers)
    for p in POWER_PATHS:
        try:
            flow = dcflow.solve(model, p["net"], {"src": (p["src"], 1.0), "snk": (p["snk"], 0.0)}, "snk", st)
        except ValueError as exc:            # unrouted copper: report it, never invent a resistance
            out.append({"net": p["net"], "what": p["what"], "terminals": {"from": p["src"], "to": p["snk"]},
                        "error": str(exc)})
            continue
        r25 = flow.resistance("src")
        hot = dcflow.hot_area_k(flow, h)
        layer = hot["layer"]
        rec = {"net": p["net"], "what": p["what"], "terminals": {"from": p["src"], "to": p["snk"]},
               "r_mohm_25c": round(r25 * 1000, 3), "r_mohm_75c": round(r25 * 1000 * (1 + copper.ALPHA_CU * 50), 3)}
        if layer is not None:
            hx = model.grid.x0 + (hot["x_idx"] + 0.5) * h
            hy = model.grid.y0 + (hot["y_idx"] + 0.5) * h
            rec["neck_location_mm"] = [round(hx, 2), round(hy, 2)]
            rec["neck_layer"] = layer
        per_amp_k = hot["k_a_per_mm"]
        for op_name, op in ops.items():
            i = op[p["current"]]
            outer = layer in (model.layers[0], model.layers[-1])
            w_screen = copper.ipc2221_width_mm(i, SCREEN_TEMP_RISE_C, params["pcb"]["copper_oz"], external=outer)
            rec[op_name] = {"current_a": round(i, 3), "loss_mw": round(i * i * r25 * 1000 * (1 + copper.ALPHA_CU * 50), 2),
                            "neck_k_a_per_mm": round(per_amp_k * i, 2), "k_max_a_per_mm": round(hot["k_max_a_per_mm"] * i, 2),
                            "equivalent_width_mm": round(1 / per_amp_k, 3) if per_amp_k else None,
                            "screen_width_mm": round(w_screen, 3), "screen_k_a_per_mm": round(i / w_screen, 2),
                            "neck_vs_screen": round(per_amp_k * i / (i / w_screen), 2) if per_amp_k else 0.0,
                            "max_via_current_a": round(max((v["max_segment_current_a"] for v in flow.via_currents), default=0.0) * i, 3),
                            "vias_over_screen": sum(v["max_segment_current_a"] * i > SCREEN_VIA_A for v in flow.via_currents)}
        out.append(rec)
        figures.append(plot_flow(model, flow, p, rec, figdir))
    # ground: superpose the two unit solutions
    gmodel = CopperModel(geo, h_gnd)
    gst = stack_from_params(params, gmodel.layers)
    unit = {}
    gnd = {"what": "laser return J3.2 and U1 PGND 9/24 to battery B- J2", "net": "GND"}
    try:
        for name, (pads, _) in GND_SOURCES.items():
            unit[name] = dcflow.solve(gmodel, "GND", {"src": (pads, 1.0), "snk": (GND_SINK, 0.0)}, "snk", gst)
    except ValueError as exc:
        gnd["error"] = str(exc)
        return out, gnd, figures
    gnd.update({
           "r_mohm_25c": {k: round(f.resistance("src") * 1000, 3) for k, f in unit.items()}})
    quiet, isolated = {}, []
    for pid in QUIET_GND:
        if not gmodel.pad_ids(pid):
            continue
        try:
            quiet[pid] = {k: dcflow.pad_potential(gmodel, f, gmodel.pad_ids(pid)[0]) for k, f in unit.items()}
        except ValueError:                   # pad copper not joined to the ground being solved
            isolated.append(pid)
    gnd["isolated_quiet_pads"] = isolated
    hot_l = dcflow.hot_area_k(unit["laser_return"], h_gnd)
    hot_c = dcflow.hot_area_k(unit["converter_pgnd"], h_gnd)
    for op_name, op in ops.items():
        ia, ib = op["i_out"], op["i_pgnd"]
        va = {k: unit["laser_return"].v_terminal[k] * ia for k in ("src", "snk")}
        vb = {k: unit["converter_pgnd"].v_terminal[k] * ib for k in ("src", "snk")}
        # loss of the superposed field from the mutual terms of the two unit solutions
        loss = superposed_loss(unit["laser_return"], unit["converter_pgnd"], ia, ib, gst)
        ref = quiet.get("U1.10")
        offsets = {pid: round(((v["laser_return"] * ia + v["converter_pgnd"] * ib)
                               - (ref["laser_return"] * ia + ref["converter_pgnd"] * ib)) * 1e6, 1)
                   for pid, v in quiet.items()} if ref else {}
        gnd[op_name] = {"i_laser_return_a": round(ia, 3), "i_pgnd_a": round(ib, 3),
                        "loss_mw": round(loss * 1000 * (1 + copper.ALPHA_CU * 50), 2),
                        "laser_return_drop_mv": round((va["src"] - va["snk"]) * 1000, 3),
                        "pgnd_drop_mv": round((vb["src"] - vb["snk"]) * 1000, 3),
                        "quiet_offsets_uv_vs_U1.10": offsets,
                        "neck_k_a_per_mm": round(max(hot_l["k_a_per_mm"] * ia, hot_c["k_a_per_mm"] * ib), 2)}
        gnd[op_name]["setpoint_error"] = setpoint_error(params, offsets)
    figures.append(plot_ground(gmodel, unit, ops["worst"], quiet, figdir))
    return out, gnd, figures


def superposed_loss(fa, fb, ia, ib, st) -> float:
    # P = sum g (ia dVa + ib dVb)^2 over copper; evaluated from the per-layer potential maps
    total = 0.0
    for l in fa.v_map:
        g = 1.0 / st.r_sheet(l)
        v = fa.v_map[l] * ia + fb.v_map[l] * ib
        for d in (np.diff(v, axis=0), np.diff(v, axis=1)):
            total += float(np.nansum(g * d * d))
    return total


def setpoint_error(params, offsets_uv) -> dict:
    """Regulated-current error from DC ground offsets. FB regulates to VREF above U1 AGND; FB is
    k * CS_OUT plus (1-k) * the R9 ground, and CS_OUT is referenced to U2's ground pins."""
    cm = params["components"]
    k = cm["fb_divider"]["r_bot_ohm"] / (cm["fb_divider"]["r_top_ohm"] + cm["fb_divider"]["r_bot_ohm"])
    gain = cm["shunt"]["r_ohm"] * cm["csa"]["gain"]
    if "U2.1" not in offsets_uv or "R9.2" not in offsets_uv:
        return {}
    v_u2 = offsets_uv["U2.1"] * 1e-6
    v_r9 = offsets_uv["R9.2"] * 1e-6
    d_i = -(k * v_u2 + (1 - k) * v_r9) / (k * gain)
    i_set = params["current"]["i_set_a"]
    return {"delta_i_ma": round(d_i * 1000, 3), "delta_pct": round(100 * d_i / i_set, 4)}


def hot_loop_metrics(model, geo, params):
    st = stack_from_params(params, model.layers)
    top = model.layers[0]
    res = {}
    for name, spec in HOT_LOOPS.items():
        rows = []
        for cap in spec["caps"]:
            if not model.pad_ids(f"{cap}.1"):
                continue
            pts = []
            for item in spec["path"]:
                pads = [item.format(cap=cap)] if isinstance(item, str) else item
                pts.append(centroid(model, pads))
            net, cap_pad, ic_pads = spec["hot_net"]
            gpad, gdst = spec["gnd_leg"]
            rows.append({
                "cap": cap, "value": model.footprints[cap]["value"],
                "centroid_loop_area_mm2": round(shoelace(pts), 2),
                "hot_leg_top_mm": _finite(geodesic_mm(model, net, [top], [cap_pad.format(cap=cap)], ic_pads, st)),
                "gnd_leg_top_mm": _finite(geodesic_mm(model, "GND", [top], [gpad.format(cap=cap)], gdst, st)),
                "gnd_leg_any_layer_mm": _finite(geodesic_mm(model, "GND", model.layers, [gpad.format(cap=cap)], gdst, st)),
                "gnd_vias_within_1mm_of_cap": sum(1 for v in geo["vias"] if norm(v["net"]) == "GND" and
                                                  math.hypot(v["x"] - model.pads[model.pad_ids(gpad.format(cap=cap))[0]]["x"],
                                                             v["y"] - model.pads[model.pad_ids(gpad.format(cap=cap))[0]]["y"]) < 1.0),
            })
        res[name] = rows
    return res


def _finite(v):
    return round(v, 2) if math.isfinite(v) else None


def _blank(v):
    return "" if v is None else v


def drive_loop_metrics(model, params):
    st = stack_from_params(params, model.layers)
    out = []
    fields = {}
    for d in DRIVE_LOOPS:
        if d["ret"] not in fields:
            fields[d["ret"]] = return_distance_fields(model, d["ret"], st)
        a, b = (centroid(model, [p]) for p in d["pads"])
        rec = {"net": d["net"], "what": d["what"], "return": d["ret"],
               "pad_to_pad_mm": round(math.hypot(a[0] - b[0], a[1] - b[1]), 2),
               "route_mm": _finite(geodesic_mm(model, d["net"], model.layers, [d["pads"][0]], [d["pads"][1]], st))}
        rec.update(route_stats(model, d["net"]))
        rec.update(loop_area(model, d["net"], d["ret"], st, fields[d["ret"]]))
        rec["return_path_top_mm"] = _finite(geodesic_mm(model, d["ret"], [model.layers[0]], [d["ret_pads"][0]], [d["ret_pads"][1]], st))
        rec["return_path_any_layer_mm"] = _finite(geodesic_mm(model, d["ret"], model.layers, [d["ret_pads"][0]], [d["ret_pads"][1]], st))
        out.append(rec)
    return out


def proximity(model):
    h = model.grid.h
    aggr = {l: np.zeros((model.grid.ny, model.grid.nx), dtype=bool) for l in model.layers}
    for n in AGGRESSORS:
        for l in model.layers:
            aggr[l] |= model.mask(n, l)
    dist = {l: ndimage.distance_transform_edt(~aggr[l]) * h for l in model.layers}
    out = []
    for n in SENSITIVE:
        rec = {"net": n, "same_layer_min_gap_mm": None, "adjacent_overlap_mm2": 0.0, "layers": []}
        for k, l in enumerate(model.layers):
            m = model.mask(n, l)
            if not m.any():
                continue
            rec["layers"].append(l)
            if aggr[l].any():
                gap = float(dist[l][m].min()) - h          # centre-to-centre -> approximately edge-to-edge
                rec["same_layer_min_gap_mm"] = round(gap if rec["same_layer_min_gap_mm"] is None
                                                     else min(gap, rec["same_layer_min_gap_mm"]), 2)
            for kk in (k - 1, k + 1):
                if 0 <= kk < len(model.layers):
                    rec["adjacent_overlap_mm2"] += float((m & aggr[model.layers[kk]]).sum()) * h * h
        rec["adjacent_overlap_mm2"] = round(rec["adjacent_overlap_mm2"], 3)
        out.append(rec)
    return out


def ic_vias(geo):
    pads = {f"{fp['ref']}.{p['num']}": p for fp in geo["footprints"] for p in fp["pads"]}
    out = {}
    for group, ids, net in (("U1 PGND 9/24", ["U1.9", "U1.24"], "GND"), ("U1 VOUT 11/26", ["U1.11", "U1.26"], "VOUT"),
                            ("U1 SW2 21/25", ["U1.21", "U1.25"], "SW2"), ("Q3 source", ["Q3.1", "Q3.2", "Q3.3"], "GND"),
                            ("Q2 drain", ["Q2.5"], "VBAT")):
        ps = [pads[i] for i in ids if i in pads]
        if not ps:
            continue
        counts = {}
        for r in (1.0, 2.0):
            counts[f"within_{r:g}mm"] = sum(1 for v in geo["vias"] if norm(v["net"]) == net and
                                            min(math.hypot(v["x"] - p["x"], v["y"] - p["y"]) for p in ps) <= r)
        out[group] = counts
    return out


def kelvin(model, params):
    st = stack_from_params(params, model.layers)
    rec = {n: route_stats(model, n) for n in ("ISP_K", "ISN_K")}
    rec["pairing"] = pair_separation(model, "ISP_K", "ISN_K", st)
    return rec


def switch_node_area(geo):
    out = {}
    for z in geo["zones"]:
        n = norm(z["net"])
        if n in ("SW1", "SW2"):
            out.setdefault(n, {})[z["layer"]] = z["filled_area_mm2"]
    return out


# ------------------------------------------------------------------ findings
def findings(paths_, gnd, ops, params, hot, drive, prox, kel):
    f = []
    for p in paths_ + [gnd]:
        if "error" in p:
            f.append({"level": "REVIEW", "id": f"CONNECT-{p['net']}",
                      "text": f"{p['net']}: no copper current path ({p['error']})."})
    for p in paths_:
        if "error" in p:
            continue
        w = p["worst"]
        if w["neck_vs_screen"] > 1.0:
            f.append({"level": "REVIEW", "id": f"NECK-{p['net']}",
                      "text": f"{p['net']}: {w['neck_k_a_per_mm']} A/mm over the hottest 0.25 mm2 at {w['current_a']} A "
                              f"(equivalent width {p['worst']['equivalent_width_mm']} mm) exceeds the IPC-2221 "
                              f"{SCREEN_TEMP_RISE_C:g} K long-trace screen of {w['screen_k_a_per_mm']} A/mm "
                              f"({w['screen_width_mm']} mm) by x{w['neck_vs_screen']} at {p.get('neck_location_mm')} "
                              f"on {p.get('neck_layer')}."})
        if w["vias_over_screen"]:
            f.append({"level": "REVIEW", "id": f"VIA-{p['net']}",
                      "text": f"{p['net']}: {w['vias_over_screen']} via barrel segment(s) carry more than "
                              f"{SCREEN_VIA_A} A (max {w['max_via_current_a']} A)."})
    by = {p["net"]: p for p in paths_ if "error" not in p}
    nom = ops["nominal"]
    if len(by) < len(paths_) or "error" in gnd:
        comp = {"incomplete": "one or more power paths are not connected; no copper-loss comparison"}
        return _signal_findings(f, gnd, drive, prox, kel, hot), comp
    cad_in = (sum(by[n]["nominal"]["loss_mw"] for n in ("BAT_SPRING", "VBAT") if n in by) + gnd["nominal"]["loss_mw"]) / 1000
    cad_out = sum(by[n]["nominal"]["loss_mw"] for n in ("VOUT", "LD_P") if n in by) / 1000
    cad_sw = sum(by[n]["nominal"]["loss_mw"] for n in ("SW1", "SW2") if n in by) / 1000
    model_in = nom["i_in"] ** 2 * params["pcb"]["model_copper_input_ohm"]
    model_out = nom["i_out"] ** 2 * params["pcb"]["model_copper_output_ohm"]
    delta = (cad_in - model_in) + (cad_out - model_out) + cad_sw
    eta = nom["p_laser"] / (nom["p_in"] + delta)
    comp = {"cad_input_copper_w": round(cad_in, 4), "model_input_copper_w": round(model_in, 4),
            "cad_output_copper_w": round(cad_out, 4), "model_output_copper_w": round(model_out, 4),
            "cad_switch_node_copper_w": round(cad_sw, 4), "delta_w": round(delta, 4),
            "model_efficiency_pct": round(nom["efficiency"] * 100, 3),
            "efficiency_with_cad_copper_pct": round(eta * 100, 3)}
    if delta > 0:
        f.append({"level": "REVIEW", "id": "COPPER-LOSS",
                  "text": f"Routed copper at 75 C dissipates {delta * 1000:.0f} mW more than the loss model allows at "
                          f"the 4.0 V nominal point (switch-node copper is not in the model); estimated efficiency "
                          f"{comp['model_efficiency_pct']} % -> {comp['efficiency_with_cad_copper_pct']} %."})
    return _signal_findings(f, gnd, drive, prox, kel, hot), comp


def _signal_findings(f, gnd, drive, prox, kel, hot):
    for op_name in ("worst",):
        se = gnd.get(op_name, {}).get("setpoint_error", {})
        if se and abs(se["delta_pct"]) > SCREEN_SETPOINT_PCT:
            f.append({"level": "REVIEW", "id": "GND-OFFSET",
                      "text": f"DC ground offsets shift the regulated current by {se['delta_i_ma']} mA ({se['delta_pct']} %)."})
    if gnd.get("isolated_quiet_pads"):
        f.append({"level": "REVIEW", "id": "GND-ISOLATED",
                  "text": f"Quiet ground pads not joined to the solved ground copper: {', '.join(gnd['isolated_quiet_pads'])}."})
    for d in drive:
        if d["vias"]:
            f.append({"level": "REVIEW", "id": f"DRIVE-{d['net']}",
                      "text": f"{d['net']} ({d['what']}) changes layer through {d['vias']} via(s); route "
                              f"{d['route_mm']} mm for a {d['pad_to_pad_mm']} mm pad spacing, loop-area estimate "
                              f"{d['loop_area_mm2']} mm2 against {d['return']}."})
    for p in prox:
        if p["adjacent_overlap_mm2"] > 0:
            f.append({"level": "REVIEW", "id": f"COUPLE-{p['net']}",
                      "text": f"{p['net']} overlaps switching copper on an adjacent layer ({p['adjacent_overlap_mm2']} mm2)."})
        if p["net"] in HIGH_Z and p["same_layer_min_gap_mm"] is not None and p["same_layer_min_gap_mm"] < SCREEN_HIGH_Z_SPACING_MM:
            f.append({"level": "REVIEW", "id": f"SPACE-{p['net']}",
                      "text": f"High-impedance {p['net']} is {p['same_layer_min_gap_mm']} mm from switching copper "
                              f"(screen {SCREEN_HIGH_Z_SPACING_MM} mm)."})
    for net, rec in kel["pairing"].items():
        if rec["length_separated_over_1mm"] > 0:
            f.append({"level": "REVIEW", "id": f"KELVIN-{net}",
                      "text": f"{net}: {rec['length_separated_over_1mm']} mm of route is more than 1 mm from its Kelvin "
                              f"partner (max {rec['max_separation_mm']} mm, enclosed {rec['enclosed_area_mm2']} mm2); "
                              f"SLVSFC5 10.1 asks for parallel, close ISP/ISN traces."})
    for name, rows in hot.items():
        for r in rows:
            if r["gnd_leg_top_mm"] is None:
                f.append({"level": "INFO", "id": f"LOOP-{r['cap']}",
                          "text": f"{name} loop via {r['cap']}: the ground leg does not close on the top layer; "
                                  f"it returns through vias ({r['gnd_vias_within_1mm_of_cap']} within 1 mm) and the "
                                  f"plane, path {r['gnd_leg_any_layer_mm']} mm."})
    return f


# ------------------------------------------------------------------ figures
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_flow(model, flow, p, rec, figdir):
    plt = _plt()
    from matplotlib.colors import LogNorm
    layers = [l for l in model.layers if np.nanmax(np.nan_to_num(flow.k_map[l], nan=0)) > 1e-3]
    rows = np.zeros((model.grid.ny, model.grid.nx), dtype=bool)
    for l in layers:
        rows |= ~np.isnan(flow.k_map[l])
    ys, xs = np.nonzero(rows)
    g = model.grid
    xa, xb = g.x0 + (xs.min() - 10) * g.h, g.x0 + (xs.max() + 10) * g.h
    ya, yb = g.y0 + (ys.min() - 10) * g.h, g.y0 + (ys.max() + 10) * g.h
    i = rec["worst"]["current_a"]
    fig, axes = plt.subplots(1, len(layers), figsize=(5.2 * len(layers), 5.2), squeeze=False)
    ext = [g.x0, g.x0 + g.nx * g.h, g.y0 + g.ny * g.h, g.y0]
    vmax = max(np.nanmax(flow.k_map[l]) for l in layers) * i
    for ax, l in zip(axes[0], layers):
        im = ax.imshow(flow.k_map[l] * i, extent=ext, norm=LogNorm(vmin=vmax / 300, vmax=vmax), cmap="inferno",
                       interpolation="nearest")
        for name in p["src"] + p["snk"]:
            for pid in model.pad_ids(name):
                pad = model.pads[pid]
                ax.text(pad["x"], pad["y"], pid, fontsize=7, color="cyan", ha="center")
        if rec.get("neck_layer") == l:
            ax.plot(*rec["neck_location_mm"], marker="o", mfc="none", mec="lime", ms=14)
        ax.set_xlim(xa, xb)
        ax.set_ylim(yb, ya)
        ax.set_title(l)
        ax.set_facecolor("#dddddd")
    fig.colorbar(im, ax=list(axes[0]), label="current per width at worst point (A/mm)")
    fig.suptitle(f"{p['net']}: {p['what']}; R25 {rec['r_mohm_25c']} mOhm; {i} A worst-case")
    out = figdir / f"flow-{p['net']}.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out.name


def plot_ground(model, unit, op, quiet, figdir):
    plt = _plt()
    g = model.grid
    ext = [g.x0, g.x0 + g.nx * g.h, g.y0 + g.ny * g.h, g.y0]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, l in zip(axes, (model.layers[0], model.layers[1])):
        v = (unit["laser_return"].v_map[l] * op["i_out"] + unit["converter_pgnd"].v_map[l] * op["i_pgnd"]) * 1000
        im = ax.imshow(v, extent=ext, cmap="viridis", interpolation="nearest")
        fig.colorbar(im, ax=ax, label="mV above battery B- contact")
        for pid in quiet:
            pad = model.pads[model.pad_ids(pid)[0]]
            ax.plot(pad["x"], pad["y"], "r.", ms=4)
            ax.text(pad["x"], pad["y"], pid, fontsize=6, color="w")
        ax.set_title(f"GND {l} potential, worst point")
        ax.set_facecolor("#dddddd")
    out = figdir / "ground-potential.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out.name


def plot_nets(model, geo, figdir):
    plt = _plt()
    from matplotlib.colors import ListedColormap
    named = ["GND", "VBAT", "BAT_SPRING", "SW1", "SW2", "VOUT", "LD_P", "DR1H", "DR1L", "BOOT1", "BOOT2",
             "ISP_K", "ISN_K", "FB", "COMP", "COMP_RC", "CS_OUT", "VCC5"]
    colours = ["#bbbbbb", "#e41a1c", "#ff7f00", "#984ea3", "#f781bf", "#377eb8", "#4daf4a", "#a65628", "#e6c800",
               "#00ced1", "#8b008b", "#006400", "#ff1493", "#000000", "#556b2f", "#808000", "#1e90ff", "#ff4500"]
    order = named + sorted(model.nets() - set(named))
    cmap = ListedColormap(["#ffffff"] + colours + ["#999966"] * (len(order) - len(named)))
    g = model.grid
    ext = [g.x0, g.x0 + g.nx * g.h, g.y0 + g.ny * g.h, g.y0]
    names = []
    for layer in model.layers:
        fig, ax = plt.subplots(figsize=(13, 13 * g.ny / g.nx))
        ax.imshow(model.net_index(layer, order), cmap=cmap, vmin=0, vmax=len(order), extent=ext,
                  interpolation="nearest")
        for fp in geo["footprints"]:
            ax.text(fp["x"], fp["y"], fp["ref"], fontsize=6, ha="center", va="center", clip_on=True)
        for v in geo["vias"]:
            ax.add_patch(plt.Circle((v["x"], v["y"]), v["drill"] / 2, color="k", fill=False, lw=0.4))
        ax.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in colours], named, loc="upper left",
                  bbox_to_anchor=(1.01, 1.0), fontsize=7)
        ax.set_xlim(ext[0], ext[1])
        ax.set_ylim(ext[2], ext[3])
        ax.set_title(f"{layer} copper by net")
        name = f"nets-{layer.replace('.', '_')}.png"
        fig.savefig(figdir / name, dpi=110, bbox_inches="tight")
        plt.close(fig)
        names.append(name)
    return names


# ------------------------------------------------------------------ report
def write_md(variant, data, path: Path):
    L = [f"# Power-layout review: {variant}", "",
         f"Generated by `automation/review/power_layout.py` from `{data['inputs']['board']}` "
         f"(SHA-256 `{data['inputs']['board_sha256'][:12]}`). Numbers come from the routed copper; "
         "the screening criteria below select items for review and never open or close a gate. "
         "DC copper analysis does not model inductance, switching waveforms or temperature. "
         "Physical behaviour remains a Gate G (bench) item.", "",
         "## Assumptions", ""]
    for k, v in data["assumptions"].items():
        L.append(f"- {k}: {v}")
    L += ["", "## Operating points", "", "| Point | Corner | Vin (V) | Region | I_in (A) | I_L rms (A) | I_out (A) |",
          "|---|---|---|---|---|---|---|"]
    for k, o in data["operating_points"].items():
        L.append(f"| {k} | {o['corner']} | {o['v_in']} | {o['region']} | {o['i_in']:.2f} | {o['i_l_rms']:.2f} | {o['i_out']:.2f} |")
    L += ["", "## Power-path copper (DC current flow)", "",
          "Neck = current per unit width exceeded over the hottest 0.25 mm² of copper outside the pad and via "
          "crowding zones; equivalent width = path current / neck value. Screen = width an IPC-2221 long trace "
          f"needs for the same current at {SCREEN_TEMP_RISE_C:g} K rise (short necks spread heat into wider copper, "
          "so exceeding it marks a review item, not a failure).", "",
          "| Net | Path | R 25 °C (mΩ) | Worst I (A) | Loss 75 °C (mW) | Neck (A/mm) | Equiv. width (mm) | Screen width (mm) | Ratio | Neck at | Max via (A) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in data["paths"]:
        if "error" in p:
            L.append(f"| {p['net']} | {p['what']} | not connected | | | | | | | {p['error']} | |")
            continue
        w = p["worst"]
        L.append(f"| {p['net']} | {p['what']} | {p['r_mohm_25c']} | {w['current_a']} | {w['loss_mw']} | "
                 f"{w['neck_k_a_per_mm']} | {w['equivalent_width_mm']} | {w['screen_width_mm']} | {w['neck_vs_screen']} | "
                 f"{p.get('neck_layer', '')} {p.get('neck_location_mm', '')} | {w['max_via_current_a']} |")
    g = data["ground"]
    if "error" in g:
        L += ["", f"**Ground** ({g['what']}): not solved, {g['error']}."]
    else:
        L += ["", f"**Ground** ({g['what']}): unit-current resistance {g['r_mohm_25c']} mΩ at 25 °C.", ""]
        for k in ("worst", "nominal"):
            gg = g[k]
            L.append(f"- {k}: loss {gg['loss_mw']} mW at 75 °C; laser-return drop {gg['laser_return_drop_mv']} mV; "
                     f"PGND drop {gg['pgnd_drop_mv']} mV; setpoint shift from ground offsets {gg.get('setpoint_error', {})}.")
        L += ["", "Quiet-reference ground offsets at the worst point (µV relative to U1 AGND pin 10):", "",
              "| Pad | µV |", "|---|---|"]
        for pid, v in g["worst"]["quiet_offsets_uv_vs_U1.10"].items():
            L.append(f"| {pid} | {v} |")
    c = data["copper_vs_model"]
    L += ["", "## Copper loss against the efficiency model (4.0 V nominal point, copper at 75 °C)", ""]
    if "incomplete" in c:
        L.append(f"Not evaluated: {c['incomplete']}.")
    else:
        L += ["| Item | CAD (W) | Loss model (W) |", "|---|---|---|",
              f"| Input path incl. ground return | {c['cad_input_copper_w']} | {c['model_input_copper_w']} |",
              f"| Output path (VOUT + LD_P) | {c['cad_output_copper_w']} | {c['model_output_copper_w']} |",
              f"| Switch-node copper (SW1 + SW2) | {c['cad_switch_node_copper_w']} | not modelled |", "",
              f"Efficiency estimate {c['model_efficiency_pct']} % (model) -> {c['efficiency_with_cad_copper_pct']} % with "
              "the CAD copper substituted."]
    L += ["", "## Hot loops (SLVSFC5 10.1)", "",
          "Centroid loop area: polygon through the pad centroids of the loop (top view). Legs: shortest copper path "
          "on the top layer (blank = the leg does not close on the top layer) and on any layer through vias.", ""]
    for name, rows in data["hot_loops"].items():
        L += [f"**{name}**", "", "| Cap | Value | Centroid area (mm²) | Hot leg top (mm) | GND leg top (mm) | GND leg any (mm) | GND vias ≤1 mm |",
              "|---|---|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['cap']} | {r['value']} | {r['centroid_loop_area_mm2']} | {_blank(r['hot_leg_top_mm'])} | "
                     f"{_blank(r['gnd_leg_top_mm'])} | {_blank(r['gnd_leg_any_layer_mm'])} | {r['gnd_vias_within_1mm_of_cap']} |")
        L.append("")
    L += ["## Gate-drive, bootstrap and VCC loops", "",
          "Loop-area estimate: track length × distance to the nearest return-net copper on the same or an adjacent "
          "layer (adjacent layers add their spacing).", "",
          "| Net | Function | Return | Pad spacing (mm) | Route (mm) | Track (mm) | Vias | Layers | Loop area (mm²) | Max return distance (mm) | Return path top / any (mm) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in data["drive_loops"]:
        L.append(f"| {d['net']} | {d['what']} | {d['return']} | {d['pad_to_pad_mm']} | {d['route_mm']} | {d['track_length_mm']} | "
                 f"{d['vias']} | {', '.join(d['layers'])} | {d['loop_area_mm2']} | {d['max_return_distance_mm']} | "
                 f"{_blank(d['return_path_top_mm'])} / {_blank(d['return_path_any_layer_mm'])} |")
    k = data["kelvin"]
    L += ["", "## ISP/ISN Kelvin pair", "", "| Net | Track (mm) | Vias | Layers | Enclosed area (mm²) | Max separation (mm) | Length > 1 mm apart (mm) |",
          "|---|---|---|---|---|---|---|"]
    for n in ("ISP_K", "ISN_K"):
        s, pr = k[n], k["pairing"][n]
        L.append(f"| {n} | {s['track_length_mm']} | {s['vias']} | {', '.join(s['layers'])} | {pr['enclosed_area_mm2']} | "
                 f"{pr['max_separation_mm']} | {pr['length_separated_over_1mm']} |")
    L += ["", "## Sensitive nets near switching copper", "",
          f"Aggressors: {', '.join(AGGRESSORS)}. Screen for high-impedance nodes ({', '.join(HIGH_Z)}): "
          f"≥ {SCREEN_HIGH_Z_SPACING_MM} mm on the same layer and no overlap on an adjacent layer.", "",
          "| Net | Layers | Same-layer gap (mm) | Adjacent-layer overlap (mm²) |", "|---|---|---|---|"]
    for p in data["proximity"]:
        L.append(f"| {p['net']} | {', '.join(p['layers'])} | {p['same_layer_min_gap_mm']} | {p['adjacent_overlap_mm2']} |")
    L += ["", "## Vias near power pins", "", "| Pins | ≤ 1 mm | ≤ 2 mm |", "|---|---|---|"]
    for grp, c2 in data["ic_vias"].items():
        L.append(f"| {grp} | {c2['within_1mm']} | {c2['within_2mm']} |")
    L += ["", f"Switch-node pour area (mm²): {data['switch_node_area_mm2']}", "", "## Screening results", ""]
    if not data["findings"]:
        L.append("No screening criterion was exceeded.")
    for f in data["findings"]:
        L.append(f"- **{f['level']} {f['id']}**: {f['text']}")
    L += ["", "## Figures", ""] + [f"- [{n}](layout-review/{variant}/{n})" for n in data["figures"]]
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="evaluation-board")
    ap.add_argument("--h", type=float, default=0.05, help="raster cell size for signal/power nets (mm)")
    ap.add_argument("--h-gnd", type=float, default=0.1, help="raster cell size for the ground solve (mm)")
    ap.add_argument("--no-extract", action="store_true", help="reuse build/<variant>/layout-geometry.json")
    args = ap.parse_args()
    v = args.variant
    board = paths.HARDWARE / v / f"{PROJECT}.kicad_pcb"
    geo_path = paths.BUILD / v / "layout-geometry.json" if args.no_extract else extract(v)
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    if geo["board_sha256"] != sha(board):
        raise SystemExit("layout-geometry.json is stale for the current board; rerun without --no-extract")
    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    calc = json.loads(CALC.read_text(encoding="utf-8"))
    ops = operating_points(calc)
    figdir = paths.REPORTS / "layout-review" / v
    figdir.mkdir(parents=True, exist_ok=True)

    model = CopperModel(geo, args.h)
    path_res, gnd, figs = flow_paths(model, geo, params, ops, args.h_gnd, figdir)
    hot = hot_loop_metrics(model, geo, params)
    drive = drive_loop_metrics(model, params)
    prox = proximity(model)
    kel = kelvin(model, params)
    figs = plot_nets(model, geo, figdir) + figs
    finds, comp = findings(path_res, gnd, ops, params, hot, drive, prox, kel)
    st = stack_from_params(params, geo["copper_layers"])
    data = {
        "variant": v,
        "inputs": {"board": board.relative_to(ROOT).as_posix(), "board_sha256": sha(board),
                   "parameters_sha256": sha(PARAMS), "calculations_sha256": sha(CALC)},
        "assumptions": {
            "copper": f"{params['pcb']['copper_oz']} oz ({st.copper_mm[geo['copper_layers'][0]] * 1000:.1f} um) on every "
                      "layer (DD-14 target; finished thickness UNKNOWN)",
            "layer spacing (mm)": [round(x, 4) for x in st.gaps_mm],
            "via barrel plating": f"{params['pcb']['via_plating_um']} um (assumed; fabricator value UNKNOWN)",
            "solver": f"DC resistor grid, {args.h} mm cells ({args.h_gnd} mm for GND), resistance at 25 C, losses "
                      "scaled to 75 C copper; terminals are equipotential pad groups",
            "currents": "boost-mode DC: input current through BAT_SPRING/VBAT, inductor RMS through SW1/SW2, "
                        "output current through VOUT/LD_P; ground carries the laser return plus I_in - I_out from PGND",
        },
        "operating_points": ops,
        "paths": path_res, "ground": gnd, "copper_vs_model": comp,
        "hot_loops": hot, "drive_loops": drive, "kelvin": kel, "proximity": prox,
        "ic_vias": ic_vias(geo), "switch_node_area_mm2": switch_node_area(geo),
        "findings": finds, "figures": figs,
    }
    out_json = paths.REPORTS / f"layout-review-{v}.json"
    out_json.write_text(json.dumps(data, indent=1, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    write_md(v, data, paths.REPORTS / f"layout-review-{v}.md")
    print(f"{v}: {len(finds)} screening results; report {out_json.relative_to(ROOT)}")
    for f in finds:
        print(f"  {f['level']} {f['id']}: {f['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
