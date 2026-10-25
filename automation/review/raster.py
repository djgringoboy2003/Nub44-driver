"""Raster copper model of an extracted board (automation/review/layout_extract.py output).

Copper of one net on one layer becomes a boolean grid with square cells of side ``h`` mm.
Cell (i, j) covers x0 + j*h .. x0 + (j+1)*h and y0 + i*h .. y0 + (i+1)*h; a cell is copper
when its centre is inside the copper polygons (exact even-odd scanline test of cell centres;
Pillow's polygon fill rounds vertices and fills inclusively, which widens every shape by a cell).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def norm(net: str) -> str:
    """Board net name -> connectivity.yaml net name (local labels carry a leading '/')."""
    return net.lstrip("/")


@dataclass
class Grid:
    x0: float
    y0: float
    h: float
    ny: int
    nx: int

    @classmethod
    def for_bbox(cls, bbox, h: float, margin: float = 0.2) -> "Grid":
        x0, y0 = bbox[0] - margin, bbox[1] - margin
        nx = int(math.ceil((bbox[2] - bbox[0] + 2 * margin) / h))
        ny = int(math.ceil((bbox[3] - bbox[1] + 2 * margin) / h))
        return cls(x0, y0, h, ny, nx)

    def cell(self, x: float, y: float) -> tuple[int, int]:
        return int((y - self.y0) / self.h), int((x - self.x0) / self.h)

    def centres(self):
        xs = self.x0 + (np.arange(self.nx) + 0.5) * self.h
        ys = self.y0 + (np.arange(self.ny) + 0.5) * self.h
        return xs, ys

    def disc(self, x: float, y: float, r: float) -> np.ndarray:
        """Boolean mask of cells whose centres are within r of (x, y)."""
        xs, ys = self.centres()
        return (xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2 <= r * r


def fill_rings(grid: Grid, rings, mask: np.ndarray) -> None:
    """OR the even-odd interior of closed rings (outline plus holes) into mask, sampling cell centres."""
    edges = []
    for ring in rings:
        if len(ring) < 3:
            continue
        a = np.asarray(ring, dtype=float)
        b = np.roll(a, -1, axis=0)
        edges.append(np.hstack([a, b]))
    if not edges:
        return
    e = np.vstack(edges)
    x1, y1, x2, y2 = e[:, 0], e[:, 1], e[:, 2], e[:, 3]
    i0 = max(0, int(math.ceil((min(y1.min(), y2.min()) - grid.y0) / grid.h - 0.5)))
    i1 = min(grid.ny - 1, int(math.floor((max(y1.max(), y2.max()) - grid.y0) / grid.h - 0.5)))
    if i1 < i0:
        return
    yc = grid.y0 + (np.arange(i0, i1 + 1) + 0.5) * grid.h
    yy = yc[:, None]
    # half-open crossing rule: a vertex on the scanline is counted once
    cross = ((y1 <= yy) & (yy < y2)) | ((y2 <= yy) & (yy < y1))
    with np.errstate(divide="ignore", invalid="ignore"):
        xs = np.where(cross, x1 + (yy - y1) * (x2 - x1) / (y2 - y1), np.inf)
    xs.sort(axis=1)
    counts = cross.sum(axis=1)
    xc = grid.x0 + (np.arange(grid.nx) + 0.5) * grid.h
    for r, n in enumerate(counts):
        if n < 2:
            continue
        inside = np.searchsorted(xs[r, :n], xc, side="right") % 2 == 1
        mask[i0 + r] |= inside


def draw_shapes(grid: Grid, shapes, mask: np.ndarray | None = None) -> np.ndarray:
    """OR polygons ({"outline": [...], "holes": [...]}) into a boolean mask."""
    if mask is None:
        mask = np.zeros((grid.ny, grid.nx), dtype=bool)
    for s in shapes:
        # holes only remove copper of their own polygon, never overlapping copper of another item
        fill_rings(grid, [s["outline"], *s["holes"]], mask)
    return mask


class CopperModel:
    """Per-net, per-layer copper masks of one extracted board."""

    def __init__(self, geo: dict, h: float):
        self.geo = geo
        self.grid = Grid.for_bbox(geo["bbox"], h)
        self.layers = geo["copper_layers"]
        self._items: dict[tuple[str, str], list] = {}
        for p in geo["polys"]:
            self._items.setdefault((norm(p["net"]), p["layer"]), []).extend(p["polys"])
        self._cache: dict[tuple[str, str], np.ndarray] = {}
        # Pad ids are "REF.NUM"; repeated numbers (e.g. the segments of a ring contact) get "#k".
        self.pads: dict[str, dict] = {}
        for fp in geo["footprints"]:
            for pad in fp["pads"]:
                base = f"{fp['ref']}.{pad['num']}"
                key, k = base, 1
                while key in self.pads:
                    k += 1
                    key = f"{base}#{k}"
                self.pads[key] = dict(pad, ref=fp["ref"])
        self.footprints = {fp["ref"]: fp for fp in geo["footprints"]}

    def nets(self) -> set[str]:
        return {n for n, _ in self._items if n}

    def mask(self, net: str, layer: str) -> np.ndarray:
        key = (net, layer)
        if key not in self._cache:
            self._cache[key] = draw_shapes(self.grid, self._items.get(key, []))
        return self._cache[key]

    def pad_ids(self, spec: str) -> list[str]:
        """All pad ids of "REF.NUM", including repeated pad numbers."""
        return [k for k in self.pads if k == spec or k.startswith(spec + "#")]

    def pad_mask(self, ref_pad: str, layer: str) -> np.ndarray:
        key = (f"pad:{ref_pad}", layer)
        if key not in self._cache:
            self._cache[key] = draw_shapes(self.grid, self.pads[ref_pad]["shapes"].get(layer, []))
        return self._cache[key]

    def net_index(self, layer: str, order: list[str]) -> np.ndarray:
        """Integer raster: index into ``order`` + 1 for copper of that net, 0 elsewhere."""
        out = np.zeros((self.grid.ny, self.grid.nx), dtype=np.int16)
        for k, net in enumerate(order):
            out[self.mask(net, layer)] = k + 1
        return out
