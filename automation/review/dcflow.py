"""DC current flow through the copper of one net (finite-volume resistor grid).

Each copper cell of the raster model (raster.CopperModel) is a node. Neighbouring cells on a
layer are joined by one square of copper (conductance 1/R_sheet). Via barrels and plated pad
holes join the cells inside the drill on consecutive layers of their span. Each terminal (a
group of component pads that a part drives as one equipotential, e.g. U1 pins 11 + 26) is an
extra node tied to all of its pad cells; currents are injected there. One terminal is the
reference (0 V) and absorbs the sum of the others.

The model is linear and resistive: it gives the DC/low-frequency current distribution, path
resistance and I^2R loss of the copper. It says nothing about inductance, skin effect or
switching-edge currents, and its sheet resistance assumes the nominal copper thickness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse import csgraph
from scipy.sparse.linalg import spsolve

RHO_CU_20C = 1.724e-8      # ohm*m (also automation/nubm44/calc/copper.py)
ALPHA_CU = 0.00393         # 1/K
TIE = 50.0                 # terminal tie conductance per cell, in units of the sheet conductance


def rho(temp_c: float) -> float:
    return RHO_CU_20C * (1 + ALPHA_CU * (temp_c - 20.0))


@dataclass
class Stack:
    """Copper thickness per layer and spacing between consecutive copper layers (mm)."""
    copper_mm: dict[str, float]
    gaps_mm: list[float]          # centre-to-centre distance between layer k and k+1
    plating_mm: float = 0.020     # via barrel wall thickness (copper.py default; fabricator UNKNOWN)
    temp_c: float = 25.0

    def r_sheet(self, layer: str) -> float:
        return rho(self.temp_c) / (self.copper_mm[layer] * 1e-3)

    def barrel_r(self, drill_mm: float, length_mm: float) -> float:
        r_in = drill_mm / 2 * 1e-3
        r_out = r_in + self.plating_mm * 1e-3
        return rho(self.temp_c) * length_mm * 1e-3 / (math.pi * (r_out ** 2 - r_in ** 2))


@dataclass
class FlowResult:
    net: str
    terminals: dict[str, float]               # injected current per terminal (A); reference included
    reference: str
    v_terminal: dict[str, float]              # terminal potentials (V)
    k_map: dict[str, np.ndarray]              # current per unit width per layer (A/mm), NaN off copper
    v_map: dict[str, np.ndarray]              # potential per layer (V), NaN off copper
    loss_w: float                             # copper I^2R, ties excluded
    via_currents: list[dict] = field(default_factory=list)
    exclusion: dict[str, np.ndarray] = field(default_factory=dict)

    def resistance(self, source: str) -> float:
        """Two-terminal resistance source -> reference (valid when only these two carry current)."""
        return (self.v_terminal[source] - self.v_terminal[self.reference]) / self.terminals[source]


def solve(model, net: str, terminals: dict[str, tuple[list[str], float]], reference: str,
          stack: Stack, exclude_mm: float = 0.3) -> FlowResult:
    """terminals: name -> (pad ids "REF.NUM", injected current A). The reference terminal's current
    is ignored and set to minus the sum of the others."""
    grid, layers = model.grid, model.layers
    h = grid.h
    masks = {l: model.mask(net, l) for l in layers}
    index = {}
    offset = 0
    for l in layers:
        idx = np.full(masks[l].shape, -1, dtype=np.int64)
        n = int(masks[l].sum())
        idx[masks[l]] = np.arange(offset, offset + n)
        index[l] = idx
        offset += n
    n_cells = offset
    copper_edges = []                           # (a, b, g) arrays for loss accounting
    for l in layers:
        g = 1.0 / stack.r_sheet(l)
        idx = index[l]
        for a, b in ((idx[:, :-1], idx[:, 1:]), (idx[:-1, :], idx[1:, :])):
            ok = (a >= 0) & (b >= 0)
            ea, eb = a[ok], b[ok]
            copper_edges.append((ea, eb, np.full(ea.size, g)))

    # vias and plated pad holes: barrel segments between consecutive layers of the span
    barrels = [(v["x"], v["y"], v["drill"], v["layers"], f"via@{v['x']:.2f},{v['y']:.2f}")
               for v in model.geo["vias"] if v["net"].lstrip("/") == net]
    barrels += [(p["x"], p["y"], p["drill"], p["layers"], name)
                for name, p in model.pads.items()
                if p["drill"] > 0 and p["net"].lstrip("/") == net and len(p["layers"]) > 1]
    via_edges = []
    for x, y, drill, span, name in barrels:
        disc = grid.disc(x, y, max(drill / 2, h * 0.75))
        segs = []
        for la, lb in zip(span[:-1], span[1:]):
            k = layers.index(la)
            length = sum(stack.gaps_mm[k:layers.index(lb)])
            both = disc & masks[la] & masks[lb]
            if not both.any():
                continue
            a, b = index[la][both], index[lb][both]
            g = 1.0 / stack.barrel_r(drill, length) / a.size
            segs.append((la, lb, a, b, g))
            copper_edges.append((a, b, np.full(a.size, g)))
        via_edges.append((name, x, y, segs))

    # terminal ties
    term_names = list(terminals)
    term_node = {t: n_cells + k for k, t in enumerate(term_names)}
    tie_edges = []
    terminals = {t: ([pid for spec in pads for pid in model.pad_ids(spec)], i) for t, (pads, i) in terminals.items()}
    for t, (pads, _) in terminals.items():
        cells = []
        for pid in pads:
            pad = model.pads[pid]
            for l in pad["layers"]:
                pm = model.pad_mask(pid, l) & masks[l]
                cells.append(index[l][pm])
        cells = np.concatenate(cells) if cells else np.array([], dtype=np.int64)
        if cells.size == 0:
            raise ValueError(f"{net}: terminal {t} has no copper cells")
        g_tie = TIE / stack.r_sheet(layers[0])
        tie_edges.append((cells, np.full(cells.size, term_node[t]), np.full(cells.size, g_tie)))

    n = n_cells + len(term_names)
    n_copper = sum(e[0].size for e in copper_edges)
    edges = copper_edges + tie_edges
    ea = np.concatenate([e[0] for e in edges])
    eb = np.concatenate([e[1] for e in edges])
    eg = np.concatenate([e[2] for e in edges])
    adj = sparse.coo_matrix((np.ones(ea.size), (ea, eb)), shape=(n, n))
    _, comp = csgraph.connected_components(adj, directed=False)
    ref_comp = comp[term_node[reference]]
    for t in term_names:
        if comp[term_node[t]] != ref_comp:
            raise ValueError(f"{net}: terminal {t} is not connected to {reference} through copper")
    keep = comp == ref_comp
    keep[term_node[reference]] = False          # grounded node: eliminated
    new = np.full(n, -1, dtype=np.int64)
    new[keep] = np.arange(int(keep.sum()))
    m = int(keep.sum())

    # Laplacian over the kept nodes; edges to the grounded reference only add to the diagonal
    a_new, b_new = new[ea], new[eb]
    both = (a_new >= 0) & (b_new >= 0)
    one_a = (a_new >= 0) & (b_new < 0) & (eb == term_node[reference])
    one_b = (b_new >= 0) & (a_new < 0) & (ea == term_node[reference])
    r = np.concatenate([a_new[both], b_new[both], a_new[both], b_new[both], a_new[one_a], b_new[one_b]])
    c = np.concatenate([a_new[both], b_new[both], b_new[both], a_new[both], a_new[one_a], b_new[one_b]])
    d = np.concatenate([eg[both], eg[both], -eg[both], -eg[both], eg[one_a], eg[one_b]])
    lap = sparse.coo_matrix((d, (r, c)), shape=(m, m)).tocsc()
    rhs = np.zeros(m)
    injected = {t: terminals[t][1] for t in term_names if t != reference}
    injected[reference] = -sum(injected.values())
    for t, i in injected.items():
        if t != reference:
            rhs[new[term_node[t]]] = i
    sol = spsolve(lap, rhs)
    v = np.zeros(n)
    v[keep] = sol[new[keep]]

    loss = float(np.sum(eg[:n_copper] * (v[ea[:n_copper]] - v[eb[:n_copper]]) ** 2))
    v_term = {t: float(v[term_node[t]]) for t in term_names}

    k_map, v_map, excl = {}, {}, {}
    for l in layers:
        idx = index[l]
        vm = np.full(idx.shape, np.nan)
        on = idx >= 0
        live = on & keep[np.where(on, idx, 0)]
        vm[live] = v[idx[live]]
        g = 1.0 / stack.r_sheet(l)
        ix = np.zeros(idx.shape)
        iy = np.zeros(idx.shape)
        dx = np.where(np.isnan(vm[:, :-1]) | np.isnan(vm[:, 1:]), 0.0, (vm[:, :-1] - vm[:, 1:]) * g)
        dy = np.where(np.isnan(vm[:-1, :]) | np.isnan(vm[1:, :]), 0.0, (vm[:-1, :] - vm[1:, :]) * g)
        ix[:, :-1] += dx / 2
        ix[:, 1:] += dx / 2
        iy[:-1, :] += dy / 2
        iy[1:, :] += dy / 2
        km = np.hypot(ix, iy) / h                 # A per mm of width
        km[~live] = np.nan
        k_map[l], v_map[l] = km, vm
        # cells next to pads and vias carry inherent crowding: kept out of neck statistics
        near = np.zeros(idx.shape, dtype=bool)
        for t, (pads, _) in terminals.items():
            for pid in pads:
                if l in model.pads[pid]["layers"]:
                    near |= model.pad_mask(pid, l)
        for x, y, drill, span, _ in barrels:
            if l in span:
                near |= grid.disc(x, y, drill / 2 + 0.3)
        near = ndimage.binary_dilation(near, iterations=max(1, int(round(exclude_mm / h))))
        excl[l] = near

    vias = []
    for name, x, y, segs in via_edges:
        worst = 0.0
        for la, lb, a, b, g in segs:
            worst = max(worst, abs(float(np.sum(g * (v[a] - v[b])))))
        vias.append({"name": name, "x": x, "y": y, "max_segment_current_a": worst})
    return FlowResult(net=net, terminals=injected, reference=reference, v_terminal=v_term,
                      k_map=k_map, v_map=v_map, loss_w=loss, via_currents=vias, exclusion=excl)


def pad_potential(model, flow: FlowResult, pad_id: str) -> float:
    """Mean potential of a pad's copper cells (pads that are not terminals)."""
    pad = model.pads[pad_id]
    vals = []
    for l in pad["layers"]:
        pm = model.pad_mask(pad_id, l)
        vm = flow.v_map[l][pm]
        vals.append(vm[~np.isnan(vm)])
    allv = np.concatenate(vals) if vals else np.array([])
    if allv.size == 0:
        raise ValueError(f"pad {pad_id} has no solved copper")
    return float(allv.mean())


def hot_area_k(flow: FlowResult, h: float, area_mm2: float = 0.25) -> dict:
    """Current per width exceeded over ``area_mm2`` of copper (outside pad/via crowding zones),
    and the location of the hottest such cell per layer."""
    best = {"k_a_per_mm": 0.0, "layer": None, "x_idx": None, "y_idx": None, "k_max_a_per_mm": 0.0}
    cells = []
    for l, km in flow.k_map.items():
        ok = ~np.isnan(km) & ~flow.exclusion[l]
        if not ok.any():
            continue
        vals = km[ok]
        ys, xs = np.nonzero(ok)
        cells.append((vals, l, ys, xs))
        j = int(np.argmax(vals))
        if vals[j] > best["k_max_a_per_mm"]:
            best.update(k_max_a_per_mm=float(vals[j]), layer=l, x_idx=int(xs[j]), y_idx=int(ys[j]))
    if not cells:
        return best
    allv = np.sort(np.concatenate([c[0] for c in cells]))[::-1]
    n = max(1, int(round(area_mm2 / (h * h))))
    best["k_a_per_mm"] = float(allv[min(n, allv.size) - 1])
    return best
