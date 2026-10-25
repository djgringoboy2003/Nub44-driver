"""Negotiated-congestion grid router for a placed board (venv Python; no KiCad needed).

Joins the open copper groups of chosen nets on a fine grid: A* over the routable copper layers with
through vias, against the exact copper of the placed board (pads, source tracks and vias, fanout vias
and the filled source pours). Nets are routed together in PathFinder fashion: overlaps between the new
routes of different nets are allowed but priced, every pass raises the price of contested cells, and
nets in conflict are ripped up and re-routed until no two nets come closer than the rules allow. The
result is written into placement.yaml as explicit source copper (section ``grid_routes``), which
build_pcb adds like hand-written tracks and vias. FreeRouting then sees it as fixed wiring, and KiCad
DRC remains the check of record.

  usage: grid_route.py --variant compact-22mm [--rebuild] [--nets DR1H,PG] [--write] [--plot]

--rebuild runs ``build_pcb.py --stage place`` without the current grid routes and extracts the placed
copper (automation/review/layout_extract.py) into build/<variant>/placed-geometry.json, which is the
router's input. Without --write the routes are only reported (build/<variant>/grid-routes.json).

Rules come from build_pcb.RULES (clearance, copper-to-edge, hole-to-hole) and the default via size.
A margin of a little more than half a cell diagonal covers grid quantisation against fixed copper, and
an extra ``route_margin`` covers it between two new routes; the final exact check measures every new
segment and via against every other new one. Vias never land on an SMD pad of any net. Copper of the
net being routed is free; pours of other nets are obstacles except those listed as ``soft`` (crossing
them costs more, and they refill around the new copper). Router keep-outs stay closed to other nets.

placement.yaml settings (all optional except nets):
  grid_route:
    nets: [DR1H, PG, ...]            # nets whose open groups are joined
    widths: {DR1H: 0.2}              # track width per net (default_width otherwise)
    layers: [F.Cu, In2.Cu, B.Cu]     # routable layers
    soft: [{net: VBAT, layer: In2.Cu}]
    via_cost: 1.0                    # in mm of track
    layer_cost: {F.Cu: 1.3}          # track-length multiplier per layer (default 1)
"""
from __future__ import annotations

import argparse
import heapq
import itertools
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "automation/placement"))

from build_pcb import RULES  # noqa: E402
from nubm44 import paths  # noqa: E402
from review.raster import Grid, draw_shapes, fill_rings, norm  # noqa: E402

SKIP_ENV = "NUBM44_NO_GRID_ROUTES"     # build_pcb leaves grid routes out while the router rebuilds its input
SETTINGS = {"grid": 0.05, "margin": 0.04, "route_margin": 0.04, "default_width": 0.15, "via_diameter": 0.6,
            "via_drill": 0.3, "via_cost": 1.0, "turn_cost": 0.05, "soft_cost": 3.0,
            "layers": ["F.Cu", "In2.Cu", "B.Cu"], "iterations": 40, "pres_start": 0.5, "pres_growth": 1.5,
            "hist_step": 0.5, "heuristic_weight": 1.2}
STEPS = [(-1, -1, math.sqrt(2)), (-1, 0, 1.0), (-1, 1, math.sqrt(2)), (0, -1, 1.0),
         (0, 1, 1.0), (1, -1, math.sqrt(2)), (1, 0, 1.0), (1, 1, math.sqrt(2))]


def edt_mm(blocked: np.ndarray, h: float) -> np.ndarray:
    """Distance (mm) from every cell centre to the nearest blocked cell centre (inf if none)."""
    if not blocked.any():
        return np.full(blocked.shape, np.inf)
    return ndimage.distance_transform_edt(~blocked) * h


def poly_mask(grid: Grid, polygon) -> np.ndarray:
    mask = np.zeros((grid.ny, grid.nx), dtype=bool)
    fill_rings(grid, [polygon], mask)
    return mask


def seg_mask(grid: Grid, a, b, r: float) -> np.ndarray:
    """Cells whose centres lie within r of segment a-b."""
    mask = np.zeros((grid.ny, grid.nx), dtype=bool)
    x0, x1 = min(a[0], b[0]) - r, max(a[0], b[0]) + r
    y0, y1 = min(a[1], b[1]) - r, max(a[1], b[1]) + r
    i0, j0 = grid.cell(x0, y0)
    i1, j1 = grid.cell(x1, y1)
    i0, j0 = max(i0, 0), max(j0, 0)
    i1, j1 = min(i1 + 1, grid.ny - 1), min(j1 + 1, grid.nx - 1)
    xs = grid.x0 + (np.arange(j0, j1 + 1) + 0.5) * grid.h
    ys = grid.y0 + (np.arange(i0, i1 + 1) + 0.5) * grid.h
    px, py = np.meshgrid(xs, ys)
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = np.zeros_like(px) if L2 == 0 else np.clip(((px - a[0]) * dx + (py - a[1]) * dy) / L2, 0, 1)
    d2 = (px - a[0] - t * dx) ** 2 + (py - a[1] - t * dy) ** 2
    mask[i0:i1 + 1, j0:j1 + 1] = d2 <= r * r
    return mask


def seg_dist(a, b, c, d) -> float:
    """Shortest distance between segments a-b and c-d."""
    def pt(p, u, v):
        dx, dy = v[0] - u[0], v[1] - u[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - u[0]) * dx + (p[1] - u[1]) * dy) / L2))
        return math.hypot(p[0] - u[0] - t * dx, p[1] - u[1] - t * dy)

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0):
        return 0.0
    return min(pt(a, c, d), pt(b, c, d), pt(c, a, b), pt(d, a, b))


class Board:
    """Rasterised fixed copper of a placed board plus the rules the router must keep."""

    def __init__(self, geo: dict, place: dict, cfg: dict):
        self.cfg = cfg
        self.h = cfg["grid"]
        self.grid = Grid.for_bbox(geo["bbox"], self.h)
        self.copper = geo["copper_layers"]
        self.layers = [l for l in cfg["layers"] if l in self.copper]
        self.nets = sorted({norm(p["net"]) for p in geo["polys"] if p["net"]})
        self.idx = {n: k for k, n in enumerate(self.nets)}
        shape = (self.grid.ny, self.grid.nx)
        self.item = {l: np.full(shape, -1, dtype=np.int16) for l in self.copper}     # pads, tracks, vias
        self.zone = {l: np.full(shape, -1, dtype=np.int16) for l in self.copper}     # filled pours
        for p in geo["polys"]:
            if not p["net"] or p["layer"] not in self.copper:
                continue
            m = draw_shapes(self.grid, p["polys"])
            (self.zone if p["kind"] == "zone" else self.item)[p["layer"]][m] = self.idx[norm(p["net"])]
        # holes (vias and plated pads, every net) and SMD pads (no via may land on one)
        self.holes = np.zeros(shape, dtype=bool)
        self.smd = np.zeros(shape, dtype=bool)
        self.hole_pts = []                      # (net, x, y)
        self.via_pts = []
        for v in geo["vias"]:
            self.holes |= self.grid.disc(v["x"], v["y"], v["drill"] / 2)
            self.hole_pts.append((norm(v["net"]), v["x"], v["y"]))
            self.via_pts.append((norm(v["net"]), v["x"], v["y"]))
        for fp in geo["footprints"]:
            for pad in fp["pads"]:
                if pad["drill"] > 0:
                    self.holes |= self.grid.disc(pad["x"], pad["y"], pad["drill"] / 2)
                    self.hole_pts.append((norm(pad["net"]), pad["x"], pad["y"]))
                else:
                    for shapes in pad["shapes"].values():
                        self.smd |= draw_shapes(self.grid, shapes)
        xs, ys = self.grid.centres()
        self.rr = np.hypot(xs[None, :], ys[:, None])
        self.radius = place["board"]["outline"]["radius"]
        # router keep-outs: closed to every net but the one whose pour they protect
        self.keepouts = [(k["layer"], norm(k.get("net", "")), poly_mask(self.grid, k["polygon"]))
                         for k in place.get("router_keepouts") or []]
        self.soft = {(norm(s["net"]), s["layer"]) for s in cfg.get("soft") or []}
        self.tracks = [(norm(t["net"]), t["layer"], tuple(t["a"]), tuple(t["b"]), t["w"]) for t in geo["tracks"]]

    def own(self, net: str, layer: str) -> np.ndarray:
        n = self.idx[net]
        return (self.item[layer] == n) | (self.zone[layer] == n)

    def foreign(self, net: str, layer: str) -> np.ndarray:
        n = self.idx.get(net, -2)
        f = (self.item[layer] >= 0) & (self.item[layer] != n)
        z = (self.zone[layer] >= 0) & (self.zone[layer] != n)
        for s_net, s_layer in self.soft:
            if s_layer == layer and s_net != net and s_net in self.idx:
                z &= self.zone[layer] != self.idx[s_net]
        return f | z

    def soft_cells(self, net: str, layer: str) -> np.ndarray:
        m = np.zeros((self.grid.ny, self.grid.nx), dtype=bool)
        for s_net, s_layer in self.soft:
            if s_layer == layer and s_net != net and s_net in self.idx:
                m |= self.zone[layer] == self.idx[s_net]
        return m

    def keepout_other(self, net: str, layer: str | None = None) -> np.ndarray:
        m = np.zeros((self.grid.ny, self.grid.nx), dtype=bool)
        for l, k_net, mask in self.keepouts:
            if k_net != net and (layer is None or l == layer):
                m |= mask
        return m

    def legality(self, net: str, width: float):
        """Track-legal cells per routable layer and via-legal cells for this net (fixed copper only)."""
        c, mg = RULES["min_clearance"], self.cfg["margin"]
        vr = self.cfg["via_diameter"] / 2
        edge = self.radius - RULES["min_copper_edge_clearance"]
        track_ok, via_ok = {}, self.rr <= edge - vr - mg
        for l in self.copper:
            if l in self.layers:
                d = edt_mm(self.foreign(net, l), self.h)
                track_ok[l] = ((d >= width / 2 + c + mg) & (self.rr <= edge - width / 2 - mg)
                               & ~self.keepout_other(net, l))
                via_ok &= d >= vr + c + mg
            else:                                   # plane layers: only other holes' copper matters
                items = (self.item[l] >= 0) & (self.item[l] != self.idx.get(net, -2))
                via_ok &= edt_mm(items, self.h) >= vr + c + mg
        via_ok &= edt_mm(self.holes, self.h) >= self.cfg["via_drill"] / 2 + RULES["min_hole_to_hole"] + mg
        via_ok &= edt_mm(self.smd, self.h) >= vr + 0.05
        via_ok &= ~self.keepout_other(net)
        return track_ok, via_ok

    def components(self, net: str, extra=None):
        """Connected copper groups of a net (fixed copper plus ``extra`` masks): list of {layer: mask}."""
        labels, parent = {}, {}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        eight = np.ones((3, 3), dtype=bool)
        for l in self.copper:
            own = self.own(net, l)
            if extra is not None:
                own = own | extra[l]
            lab, n = ndimage.label(own, structure=eight)
            labels[l] = lab
            for k in range(1, n + 1):
                parent[(l, k)] = (l, k)
        holes = [(x, y) for h_net, x, y in self.hole_pts if h_net == net]
        holes += (extra or {}).get("vias", [])
        for x, y in holes:
            i, j = self.grid.cell(x, y)
            keys = [(l, int(labels[l][i, j])) for l in self.copper if labels[l][i, j]]
            for a, b in zip(keys, keys[1:]):
                parent[find(a)] = find(b)
        groups = {}
        for key in parent:
            groups.setdefault(find(key), []).append(key)
        comps = []
        for keys in groups.values():
            comp = {l: np.zeros_like(labels[l], dtype=bool) for l in self.copper}
            for l, k in keys:
                comp[l] |= labels[l] == k
            comps.append(comp)
        comps.sort(key=lambda c: -sum(int(m.sum()) for m in c.values()))
        return comps


def astar(board: Board, sources, targets, ok, mult, via, via_mult, free_via):
    """Multi-source, multi-target A* over (layer, cell); costs are per-state multipliers of the step
    length (``mult``) and per-cell via costs (``via_mult``). Returns [(layer, i, j), ...] or None."""
    g_ = board.grid
    nx, NN = g_.nx, g_.nx * g_.ny
    L = board.layers
    nL = len(L)
    h = board.h
    tgt2d = np.zeros((g_.ny, g_.nx), dtype=bool)
    is_target = np.zeros(nL * NN, dtype=bool)
    for k, l in enumerate(L):
        m = targets[l].ravel() & np.asarray(ok[k * NN:(k + 1) * NN], dtype=bool)
        tgt2d |= m.reshape(g_.ny, g_.nx)
        is_target[k * NN:(k + 1) * NN] = m
    if not tgt2d.any():
        return None
    heur = (edt_mm(tgt2d, h) * board.cfg["heuristic_weight"]).ravel().tolist()
    is_target = is_target.tolist()
    turn_cost = board.cfg["turn_cost"]
    INF = float("inf")
    g, parent, heap = {}, {}, []
    for k, l in enumerate(L):
        for idx in np.flatnonzero(sources[l].ravel()).tolist():
            s = k * NN + idx
            if ok[s]:
                g[s] = 0.0
                parent[s] = -1
                heapq.heappush(heap, (heur[idx], 0.0, s))
    steps = [(di * nx + dj, c * h) for di, dj, c in STEPS]
    closed = set()
    while heap:
        f, gs, s = heapq.heappop(heap)
        if s in closed:
            continue
        closed.add(s)
        if is_target[s]:
            path = []
            while s != -1:
                k, idx = divmod(s, NN)
                path.append((L[k], *divmod(idx, nx)))
                s = parent[s]
            return path[::-1]
        k, idx = divmod(s, NN)
        p = parent[s]
        d_in = (s - p) if p != -1 and p // NN == k else None
        base = k * NN
        for d, c in steps:
            t = s + d
            if not ok[t]:
                continue
            ng = gs + c * mult[t] + (turn_cost if d_in is not None and d != d_in else 0.0)
            if ng < g.get(t, INF):
                g[t] = ng
                parent[t] = s
                heapq.heappush(heap, (ng + heur[t - base], ng, t))
        if via[idx]:
            cost = 0.0 if free_via[idx] else via_mult[idx]
            for k2 in range(nL):
                if k2 == k:
                    continue
                t = k2 * NN + idx
                if not ok[t]:
                    continue
                ng = gs + cost
                if ng < g.get(t, INF):
                    g[t] = ng
                    parent[t] = s
                    heapq.heappush(heap, (ng + heur[idx], ng, t))
    return None


class Router:
    """PathFinder-style negotiation between the nets' new routes."""

    def __init__(self, board: Board, nets: list[str], cfg: dict, log=print):
        self.b, self.cfg, self.log = board, cfg, log
        self.nets = [n for n in nets if n in board.idx]
        for n in nets:
            if n not in board.idx:
                log(f"{n}: no copper on the board")
        widths = cfg.get("widths") or {}
        self.width = {n: widths.get(n, cfg["default_width"]) for n in self.nets}
        g = board.grid
        self.NN = g.ny * g.nx
        self.L = board.layers
        self.vr = cfg["via_diameter"] / 2
        self.classes = sorted(set(self.width.values())) + ["via"]
        self.hw = {k: (self.vr if k == "via" else k / 2) for k in self.classes}
        # between two new routes only their own centreline quantisation matters (half a cell diagonal);
        # exact_check() measures the real segments afterwards
        self.sep = RULES["min_clearance"] + cfg["route_margin"]
        self.count = {k: {l: np.zeros(self.NN, np.int16) for l in self.L} for k in self.classes}
        self.hist = {l: np.zeros(self.NN, np.float32) for l in self.L}
        self.pres = cfg["pres_start"]
        self.state: dict[str, dict] = {}
        self.cache: dict[str, tuple] = {}
        layer_cost = cfg.get("layer_cost") or {}
        self.layer_mult = {l: layer_cost.get(l, 1.0) for l in self.L}

    # ---------------------------------------------------------------- per-net fixed data
    def prepare(self, net):
        if net not in self.cache:
            track_ok, via_ok = self.b.legality(net, self.width[net])
            own_hole = np.zeros_like(via_ok)
            for h_net, x, y in self.b.hole_pts:
                if h_net == net:
                    own_hole |= self.b.grid.disc(x, y, 0.1)
            ok = np.concatenate([track_ok[l].ravel() for l in self.L])
            base = np.concatenate([np.where(self.b.soft_cells(net, l), self.cfg["soft_cost"], 1.0).ravel()
                                   * self.layer_mult[l] for l in self.L])
            own_fixed = {l: self.b.own(net, l).ravel() for l in self.L}
            self.cache[net] = (track_ok, (via_ok | own_hole).ravel().tolist(), own_hole, ok.tolist(), base,
                               self.b.components(net), self.regions(track_ok, via_ok | own_hole), own_fixed)
        return self.cache[net]

    def regions(self, track_ok, via_ok):
        """Connected regions of the legal (layer, cell) graph: label arrays per layer, equal labels where
        a legal via joins two layers. Congestion never blocks, so different labels mean unreachable."""
        eight = np.ones((3, 3), dtype=bool)
        labels, offset = {}, 0
        for l in self.L:
            lab, n = ndimage.label(track_ok[l], structure=eight)
            labels[l] = np.where(lab > 0, lab + offset, 0)
            offset += n
        parent = np.arange(offset + 1)

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for a_l, b_l in itertools.combinations(self.L, 2):     # a through via joins every pair
            both = via_ok & (labels[a_l] > 0) & (labels[b_l] > 0)
            for x, y in set(zip(labels[a_l][both].tolist(), labels[b_l][both].tolist())):
                parent[find(x)] = find(y)
        roots = np.array([find(k) for k in range(offset + 1)])
        return {l: roots[labels[l]] * (labels[l] > 0) for l in self.L}

    @staticmethod
    def reachable(reg, src, tgt, track_ok) -> bool:
        s = set()
        t = set()
        for l in reg:
            s |= set(np.unique(reg[l][src[l] & track_ok[l]]).tolist())
            t |= set(np.unique(reg[l][tgt[l] & track_ok[l]]).tolist())
        s.discard(0)
        return bool(s & t)

    # ---------------------------------------------------------------- congestion bookkeeping
    def contributions(self, net, cl: dict, via_cells: list):
        """Cells where another net's track (per width class) or via would come too close to this route."""
        g = self.b.grid
        cells = [c for l in self.L for c in cl[l]] + list(via_cells)
        if not cells:
            return []
        rows, cols = np.divmod(np.asarray(cells), g.nx)
        hw = self.width[net] / 2
        rmax = max(hw, self.vr) + self.sep + max(self.hw.values())
        pad = int(math.ceil(rmax / g.h)) + 2
        i0, i1 = max(rows.min() - pad, 0), min(rows.max() + pad, g.ny - 1)
        j0, j1 = max(cols.min() - pad, 0), min(cols.max() + pad, g.nx - 1)
        shape = (i1 - i0 + 1, j1 - j0 + 1)
        vmask = np.zeros(shape, dtype=bool)
        for c in via_cells:
            vmask[c // g.nx - i0, c % g.nx - j0] = True
        d_via = edt_mm(vmask, g.h)
        out = []
        ii, jj = np.mgrid[i0:i1 + 1, j0:j1 + 1]
        flat = (ii * g.nx + jj)
        for l in self.L:
            m = np.zeros(shape, dtype=bool)
            for c in cl[l]:
                m[c // g.nx - i0, c % g.nx - j0] = True
            d_cl = edt_mm(m, g.h)
            for k in self.classes:
                near = (d_cl <= hw + self.sep + self.hw[k]) | (d_via <= self.vr + self.sep + self.hw[k])
                out.append((k, l, flat[near]))
        return out

    def apply(self, contrib, sign):
        for k, l, idx in contrib:
            self.count[k][l][idx] += sign

    # ---------------------------------------------------------------- routing
    def route_net(self, net):
        st = self.state.get(net)
        if st:
            self.apply(st["contrib"], -1)
        track_ok, via, own_hole, ok, base, comps, reg, own_fixed = self.prepare(net)
        k = self.width[net]
        cl = {l: [] for l in self.L}
        via_cells, polylines, vias_xy, opens = [], [], [], []
        if len(comps) > 1:
            cnt = np.concatenate([self.count[k][l] for l in self.L]).astype(np.float64)
            hist = np.concatenate([self.hist[l] for l in self.L]).astype(np.float64)
            mult = (base * (1 + hist) * (1 + self.pres * cnt)).tolist()
            cv = sum(self.count["via"][l].astype(np.float64) for l in self.L)
            hv = sum(self.hist[l].astype(np.float64) for l in self.L) / len(self.L)
            via_mult = (self.cfg["via_cost"] * (1 + self.pres * cv) * (1 + hv)).tolist()
            free_via = own_hole.ravel().tolist()
            g = self.b.grid
            extra = {l: np.zeros((g.ny, g.nx), dtype=bool) for l in self.b.copper}
            extra["vias"] = []
            while len(comps) > 1:
                src = {l: comps[0][l] | extra[l] for l in self.b.copper}
                tgt = {l: np.zeros((g.ny, g.nx), dtype=bool) for l in self.b.copper}
                for c in comps[1:]:
                    for l in self.b.copper:
                        tgt[l] |= c[l]
                path = None
                if self.reachable(reg, src, tgt, track_ok):
                    path = astar(self.b, src, tgt, ok, mult, via, via_mult, free_via)
                if path is None:
                    opens = comps[1:]
                    break
                path = self.trim(net, path, extra)
                for layer, pts, cells in self.runs(path):
                    polylines.append((layer, pts))
                    cl[layer] += cells
                    for a, b in zip(pts, pts[1:]):
                        extra[layer] |= seg_mask(g, a, b, self.width[net] / 2)
                for (i, j) in self.layer_changes(path, own_hole):
                    x, y = g.x0 + (j + 0.5) * g.h, g.y0 + (i + 0.5) * g.h
                    vias_xy.append((round(x, 4), round(y, 4)))
                    via_cells.append(i * g.nx + j)
                    disc = g.disc(x, y, self.vr)
                    for l in self.b.copper:
                        extra[l] |= disc
                    extra["vias"].append((x, y))
                comps = self.b.components(net, extra)
        # a route's cells inside its own pads add nothing to the pads' fixed (legal) spacing; counting them
        # would make every pair of routes that leave neighbouring pads of different nets clash forever
        cl = {l: [c for c in cl[l] if not own_fixed[l][c]] for l in self.L}
        contrib = self.contributions(net, cl, via_cells)
        self.apply(contrib, +1)
        self.state[net] = {"cl": cl, "vias": via_cells, "contrib": contrib, "polylines": polylines,
                           "vias_xy": vias_xy, "open": opens}

    def trim(self, net, path, extra):
        """Drop the path cells inside the copper being joined at both ends (same layer)."""
        own = {l: self.b.own(net, l) | extra[l] for l in self.L}
        a = 0
        while a + 1 < len(path) and path[a + 1][0] == path[a][0] and own[path[a + 1][0]][path[a + 1][1:]]:
            a += 1
        b = len(path) - 1
        while b - 1 > a and path[b - 1][0] == path[b][0] and own[path[b - 1][0]][path[b - 1][1:]]:
            b -= 1
        return path[a:b + 1]

    def runs(self, path):
        """Same-layer runs of a path -> (layer, simplified points in mm, flat cell indices)."""
        g = self.b.grid
        xy = lambda i, j: (round(g.x0 + (j + 0.5) * g.h, 4), round(g.y0 + (i + 0.5) * g.h, 4))
        out, cur = [], [path[0]]
        for prev, node in zip(path, path[1:]):
            if node[0] != prev[0]:
                out.append(cur)
                cur = [node]
            else:
                cur.append(node)
        out.append(cur)
        res = []
        for run in out:
            if len(run) < 2:
                continue
            pts = [run[0]]
            for u, v, w in zip(run, run[1:], run[2:]):
                if (v[1] - u[1], v[2] - u[2]) != (w[1] - v[1], w[2] - v[2]):
                    pts.append(v)
            pts.append(run[-1])
            res.append((run[0][0], [xy(p[1], p[2]) for p in pts], [p[1] * g.nx + p[2] for p in run]))
        return res

    @staticmethod
    def layer_changes(path, own_hole):
        return [(prev[1], prev[2]) for prev, node in zip(path, path[1:])
                if node[0] != prev[0] and not own_hole[prev[1], prev[2]]]

    def conflicts(self, net):
        """Cells of this net's route that another net's route comes too close to."""
        st = self.state[net]
        self.apply(st["contrib"], -1)
        k = self.width[net]
        bad = {}
        for l in self.L:
            idx = np.asarray(st["cl"][l], dtype=np.int64)
            if len(idx):
                hit = idx[self.count[k][l][idx] > 0]
                if len(hit):
                    bad[l] = hit
        v = np.asarray(st["vias"], dtype=np.int64)
        if len(v):
            for l in self.L:
                hit = v[self.count["via"][l][v] > 0]
                if len(hit):
                    bad[l] = np.concatenate([bad.get(l, np.zeros(0, np.int64)), hit])
        self.apply(st["contrib"], +1)
        return bad

    def run(self):
        todo = list(self.nets)
        for it in range(self.cfg["iterations"]):
            for net in todo:
                t0 = time.perf_counter()
                self.route_net(net)
                dt = time.perf_counter() - t0
                if dt > 5:
                    self.log(f"  {net}: {dt:.0f} s")
            bad = {n: c for n in self.nets if (c := self.conflicts(n))}
            opens = sum(len(self.state[n]["open"]) for n in self.nets)
            self.log(f"pass {it + 1}: {len(todo)} nets routed, {len(bad)} in conflict, {opens} open groups")
            if not bad:
                return True
            if (it + 1) % 4 == 0:
                self.report(bad)
            for cells in bad.values():
                for l, idx in cells.items():
                    self.hist[l][idx] += self.cfg["hist_step"]
            self.pres *= self.cfg["pres_growth"]
            todo = [n for n in self.nets if n in bad]
        self.report(bad)
        return False

    def report(self, bad):
        """Name the nets each conflicted route clashes with, and where."""
        g = self.b.grid
        for net, cells in bad.items():
            k = self.width[net]
            hits = {}
            for other in self.nets:
                if other == net:
                    continue
                for kk, l, idx in self.state[other]["contrib"]:
                    if kk != k or l not in cells:
                        continue
                    common = np.intersect1d(idx, cells[l])
                    if len(common):
                        i, j = divmod(int(common[0]), g.nx)
                        hits[other] = (l, round(g.x0 + (j + 0.5) * g.h, 2), round(g.y0 + (i + 0.5) * g.h, 2))
            self.log(f"  conflict {net}: " + "; ".join(f"{o} on {l} at ({x}, {y})" for o, (l, x, y) in hits.items()))

    def drop_conflicts(self) -> list[str]:
        """Rip up nets until no two new routes clash: always the net with the most conflicting cells.
        Returns the nets left unrouted (their connections are then reported open)."""
        dropped = []
        while True:
            bad = {n: sum(len(v) for v in c.values()) for n in self.nets if n not in dropped
                   for c in [self.conflicts(n)] if c}
            if not bad:
                return dropped
            worst = max(bad, key=lambda n: (bad[n], n))
            st = self.state[worst]
            self.apply(st["contrib"], -1)
            self.state[worst] = {"cl": {l: [] for l in self.L}, "vias": [], "contrib": [], "polylines": [],
                                 "vias_xy": [], "open": self.prepare(worst)[5][1:]}
            dropped.append(worst)

    # ---------------------------------------------------------------- output
    def results(self):
        tracks, vias = [], []
        for net in self.nets:
            st = self.state[net]
            for layer, pts in st["polylines"]:
                pts = list(pts)
                pts[0] = self.snap(net, layer, pts[0])
                pts[-1] = self.snap(net, layer, pts[-1])
                tracks.append({"net": net, "layer": layer, "width": self.width[net], "pts": [list(p) for p in pts]})
            for x, y in st["vias_xy"]:
                vias.append({"net": net, "x": x, "y": y})
        return tracks, vias

    def snap(self, net, layer, pt):
        """Move an end point onto the centre of an own via it lies in, or onto the centreline of a fixed own
        track (KiCad connectivity, and no "track not centred on via" findings)."""
        r = self.cfg["via_diameter"] / 2
        vias = [(x, y) for n, x, y in self.b.via_pts if n == net]
        vias += [v for st in [self.state.get(net)] if st for v in st["vias_xy"]]
        for x, y in vias:
            if math.hypot(pt[0] - x, pt[1] - y) <= r:
                return (round(x, 4), round(y, 4))
        best = None
        for t_net, t_layer, a, b, w in self.b.tracks:
            if t_net != net or t_layer != layer:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / L2))
            q = (a[0] + t * dx, a[1] + t * dy)
            d = math.hypot(pt[0] - q[0], pt[1] - q[1])
            if d <= w / 2 and (best is None or d < best[0]):
                best = (d, (round(q[0], 4), round(q[1], 4)))
        return best[1] if best else pt


def exact_check(tracks: list, vias: list, via_d: float) -> list[str]:
    """Clearance between every pair of new items of different nets, measured on the real geometry."""
    clr = RULES["min_clearance"]
    segs = [(t["net"], t["layer"], tuple(a), tuple(b), t["width"]) for t in tracks
            for a, b in zip(t["pts"], t["pts"][1:])]
    out = []
    for i, (n1, l1, a1, b1, w1) in enumerate(segs):
        for n2, l2, a2, b2, w2 in segs[i + 1:]:
            if n1 == n2 or l1 != l2:
                continue
            gap = seg_dist(a1, b1, a2, b2) - (w1 + w2) / 2
            if gap < clr - 1e-6:
                out.append(f"{n1}/{n2} tracks on {l1}: gap {gap:.3f} mm near {a1}")
        for v in vias:
            if v["net"] == n1:
                continue
            gap = seg_dist(a1, b1, (v["x"], v["y"]), (v["x"], v["y"])) - (w1 + via_d) / 2
            if gap < clr - 1e-6:
                out.append(f"{n1} track / {v['net']} via: gap {gap:.3f} mm at ({v['x']}, {v['y']})")
    for i, v1 in enumerate(vias):
        for v2 in vias[i + 1:]:
            if v1["net"] != v2["net"]:
                gap = math.hypot(v1["x"] - v2["x"], v1["y"] - v2["y"]) - via_d
                if gap < clr - 1e-6:
                    out.append(f"{v1['net']}/{v2['net']} vias: gap {gap:.3f} mm at ({v1['x']}, {v1['y']})")
    return out


def describe(board: Board, geo: dict, comp) -> list[str]:
    names = []
    for fp in geo["footprints"]:
        for pad in fp["pads"]:
            i, j = board.grid.cell(pad["x"], pad["y"])
            if any(comp[l][i, j] for l in pad["layers"] if l in comp):
                names.append(f"{fp['ref']}.{pad['num']}")
    return names


def rebuild_geometry(variant: str) -> Path:
    env = dict(os.environ, **{SKIP_ENV: "1"})
    subprocess.run([sys.executable, str(ROOT / "automation/placement/build_pcb.py"), "--variant", variant,
                    "--stage", "place"], check=True, env=env)
    out = paths.BUILD / variant / "placed-geometry.json"
    board = paths.HARDWARE / variant / "nubm44_driver.kicad_pcb"
    subprocess.run([str(paths.kicad_python()), "-I", str(ROOT / "automation/review/layout_extract.py"),
                    str(board), str(out)], check=True)
    return out


def write_routes(variant: str, tracks: list, vias: list) -> None:
    """Replace the generated grid_routes section of placement.yaml (kept last in the file)."""
    p = paths.HARDWARE / variant / "placement.yaml"
    raw = p.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    marker = "\n# ---- grid routes (generated by automation/placement/grid_route.py; rerun it, do not edit)"
    text = text.split(marker)[0].rstrip("\n") + "\n"

    def fmt(v):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    lines = [marker.lstrip("\n"), "grid_routes:", "  tracks:"]
    for t in tracks:
        pts = ", ".join(f"[{fmt(x)}, {fmt(y)}]" for x, y in t["pts"])
        lines.append(f"    - {{net: {t['net']}, layer: {t['layer']}, width: {fmt(t['width'])}, pts: [{pts}]}}")
    lines.append("  vias:")
    for v in vias:
        lines.append(f"    - {{net: {v['net']}, x: {fmt(v['x'])}, y: {fmt(v['y'])}}}")
    text = text + "\n" + "\n".join(lines) + "\n"
    p.write_bytes(text.replace("\n", nl).encode("utf-8"))


def plot(board: Board, geo: dict, tracks: list, vias: list, opens: list, out_dir: Path) -> None:
    """One review image per routable layer: fixed copper grey, new tracks coloured, open pads red."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g_ = board.grid
    ext = [g_.x0, g_.x0 + g_.nx * g_.h, g_.y0 + g_.ny * g_.h, g_.y0]
    cmap = plt.get_cmap("tab20")
    nets = sorted({t["net"] for t in tracks})
    for layer in board.layers:
        fig, ax = plt.subplots(figsize=(13, 13))
        base = np.zeros((g_.ny, g_.nx, 3)) + 1.0
        base[board.zone[layer] >= 0] = (0.80, 0.90, 0.80)
        base[board.item[layer] >= 0] = (0.65, 0.65, 0.65)
        ax.imshow(base, extent=ext, interpolation="nearest")
        for fp in geo["footprints"]:
            for pad in fp["pads"]:
                if layer in pad["layers"]:
                    ax.text(pad["x"], pad["y"], f"{fp['ref']}.{pad['num']}", fontsize=4, ha="center", va="center")
        for t in tracks:
            if t["layer"] != layer:
                continue
            xs, ys = zip(*t["pts"])
            ax.plot(xs, ys, lw=2.0 * t["width"] / 0.15, solid_capstyle="round",
                    color=cmap(nets.index(t["net"]) % 20), alpha=0.9)
            ax.text(xs[len(xs) // 2], ys[len(ys) // 2], t["net"], fontsize=5, color="k")
        for v in vias:
            ax.add_patch(plt.Circle((v["x"], v["y"]), 0.3, color="orange", alpha=0.9))
        for _, ref in opens:
            fp = next(f for f in geo["footprints"] if f["ref"] == ref.split(".")[0])
            pad = next(q for q in fp["pads"] if q["num"] == ref.split(".")[1])
            ax.add_patch(plt.Circle((pad["x"], pad["y"]), 0.35, fill=False, color="red", lw=1.5))
        ax.add_patch(plt.Circle((0, 0), board.radius, fill=False, color="k"))
        ax.set_xlim(-11.2, 11.2)
        ax.set_ylim(11.2, -11.2)
        ax.set_title(f"grid routes on {layer} (top view); red circles: open pads")
        fig.savefig(out_dir / f"grid-route-{layer.replace('.', '_')}.png", dpi=110, bbox_inches="tight")
        plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="compact-22mm")
    ap.add_argument("--rebuild", action="store_true", help="re-place without grid routes and re-extract copper")
    ap.add_argument("--nets", default="", help="comma-separated subset of grid_route.nets")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--plot", action="store_true", help="write build/<variant>/grid-route-<layer>.png")
    ap.add_argument("--iterations", type=int, help="negotiation passes (default: grid_route.iterations or 40)")
    ap.add_argument("--partial", action="store_true",
                    help="if negotiation does not converge, rip up the clashing nets and keep the rest")
    args = ap.parse_args()
    place = yaml.safe_load((paths.HARDWARE / args.variant / "placement.yaml").read_text(encoding="utf-8"))
    cfg = dict(SETTINGS, **(place.get("grid_route") or {}))
    if args.iterations:
        cfg["iterations"] = args.iterations
    geo_path = rebuild_geometry(args.variant) if args.rebuild else paths.BUILD / args.variant / "placed-geometry.json"
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    board = Board(geo, place, cfg)
    nets = [n for n in cfg.get("nets", []) if not args.nets or n in args.nets.split(",")]
    router = Router(board, nets, cfg, log=lambda m: print(m, flush=True))
    converged = router.run()
    dropped = []
    if not converged and args.partial:
        dropped = router.drop_conflicts()
        converged = True
        print("ripped up (left for the autorouter): " + ", ".join(dropped))
    tracks, vias = router.results()
    problems, opens = [], []
    for net in router.nets:
        for comp in router.state[net]["open"]:
            names = describe(board, geo, comp)
            problems.append(f"OPEN {net}: {', '.join(names) or '(track or via only)'}")
            opens += [(net, n) for n in names]
    if not converged:
        problems.append("routes still in conflict after the last pass")
    problems = [p for p in problems if not any(p.startswith(f"OPEN {n}:") for n in dropped)]
    problems += [f"CLEARANCE {p}" for p in exact_check(tracks, vias, cfg["via_diameter"])]
    print(f"routed {len(tracks)} track runs and {len(vias)} vias; problems: {len(problems)}")
    for p in problems:
        print("  " + p)
    out = paths.BUILD / args.variant
    (out / "grid-routes.json").write_text(json.dumps({"tracks": tracks, "vias": vias, "problems": problems},
                                                     indent=1) + "\n", encoding="utf-8")
    if args.plot:
        plot(board, geo, tracks, vias, opens, out)
    if args.write:
        write_routes(args.variant, tracks, vias)
        print("placement.yaml grid_routes updated; rerun build_pcb.py --stage place")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
