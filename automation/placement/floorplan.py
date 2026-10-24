"""Fast floorplan checker for placement.yaml (no KiCad run needed after the geometry cache exists).

Draws both sides in top-view coordinates (the same frame as placement.yaml), with courtyards, pads,
net names and per-net ratsnest (minimum spanning tree), and reports:
  - courtyard overlaps on each side, courtyards outside placement_radius / placement_box
  - copper closer than 0.3 mm to a circular board edge
  - total ratsnest length and the longest connections

The geometry cache (build/<variant>/fpgeom.json) comes from
  build_pcb.py --variant <v> --stage geometry
and is regenerated automatically when missing. Parts placed by "auto" are drawn where the last
place stage put them (build/<variant>/placement-report.json) or at their anchor.

Usage: .venv\\Scripts\\python.exe automation\\placement\\floorplan.py --variant compact-22mm
Output: build/<variant>/floorplan.png
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths  # noqa: E402

SKIP_RATS = {"GND"}            # plane net: every pad gets its own via (fanout), no ratsnest needed


def xform(x, y, px, py, rot, mirror):
    a = math.radians(rot)
    xr = x * math.cos(a) + y * math.sin(a)
    yr = -x * math.sin(a) + y * math.cos(a)
    if mirror:
        xr = -xr
    return px + xr, py + yr


def geometry_cache_is_current(geo):
    meta = geo.get("__meta__", {})
    if meta.get("format_version") != 2 or not meta.get("sources"):
        return False
    for source in meta["sources"]:
        try:
            stat = Path(source["path"]).stat()
        except OSError:
            return False
        if stat.st_mtime_ns != source["mtime_ns"] or stat.st_size != source["size"]:
            return False
    return True


def load(variant):
    vdir = paths.HARDWARE / variant
    place = yaml.safe_load((vdir / "placement.yaml").read_text(encoding="utf-8"))
    geo_path = paths.BUILD / variant / "fpgeom.json"
    try:
        geo = json.loads(geo_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        geo = {}
    if not geometry_cache_is_current(geo):
        subprocess.run([sys.executable, str(ROOT / "automation/placement/build_pcb.py"), "--variant", variant,
                        "--stage", "geometry"], check=True)
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    rep_path = paths.BUILD / variant / "placement-report.json"
    rep = json.loads(rep_path.read_text(encoding="utf-8"))["placements"] if rep_path.exists() else {}
    return place, geo, rep


def resolve(place, geo, rep):
    parts = {}
    for ref, cfg in place["parts"].items():
        g = geo[ref]
        if "pos" in cfg:
            x, y, rot = cfg["pos"]
            side, auto = cfg["side"], False
        else:
            a = cfg["auto"]
            side, auto = a["side"], True
            if ref in rep:
                x, y, rot = rep[ref]
            elif isinstance(a["anchor"], list):
                (x, y), rot = a["anchor"], 0
            else:
                x, y, rot = 0.0, 0.0, 0
        mirror = (side == "B") != g["native_back"]
        pads = []
        for p in g["pads"]:
            kind = p["kind"]
            if mirror and kind != "THT":
                kind = "B" if kind == "F" else "F"
            cx, cy = xform(p["x"], p["y"], x, y, rot, mirror)
            outline = [xform(u, v, x, y, rot, mirror) for u, v in p["outline"]]
            pads.append({"num": p["num"], "net": p["net"], "x": cx, "y": cy, "kind": kind, "outline": outline})
        x0, y0, x1, y1 = g["courtyard"]
        corners = [xform(u, v, x, y, rot, mirror) for u, v in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
        box = (min(c[0] for c in corners), min(c[1] for c in corners),
               max(c[0] for c in corners), max(c[1] for c in corners))
        parts[ref] = {"x": x, "y": y, "rot": rot, "side": side, "auto": auto, "pads": pads, "box": box,
                      "no_courtyard": cfg.get("no_courtyard", False), "both_sides": cfg.get("both_sides", False)}
    return parts


def checks(place, parts):
    problems = []
    gap = place.get("courtyard_gap", 0.0)
    r_max = place.get("placement_radius")
    pbox = place.get("placement_box")
    sides = {"F": [], "B": []}
    for ref, p in parts.items():
        if p["no_courtyard"]:
            continue
        sides[p["side"]].append(ref)
        if p["both_sides"]:
            sides["B" if p["side"] == "F" else "F"].append(ref)
        b = p["box"]
        if pbox:
            if b[0] < pbox[0] or b[1] < pbox[1] or b[2] > pbox[2] or b[3] > pbox[3]:
                problems.append(f"{ref}: courtyard outside placement_box")
        elif r_max:
            far = max(math.hypot(cx, cy) for cx in (b[0], b[2]) for cy in (b[1], b[3]))
            if far > r_max + 1e-6:
                problems.append(f"{ref}: courtyard corner at r={far:.2f} > {r_max}")
    for side, refs in sides.items():
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                A, B = parts[a]["box"], parts[b]["box"]
                if not (A[2] + gap <= B[0] or B[2] + gap <= A[0] or A[3] + gap <= B[1] or B[3] + gap <= A[1]):
                    ox = min(A[2], B[2]) - max(A[0], B[0])
                    oy = min(A[3], B[3]) - max(A[1], B[1])
                    problems.append(f"{side}: {a} overlaps {b} by {ox:.2f} x {oy:.2f} mm")
    outline = place["board"]["outline"]
    if outline["type"] == "circle":
        R = outline["radius"]
        for ref, p in parts.items():
            for pad in p["pads"]:
                rr = max((math.hypot(u, v) for u, v in pad["outline"]), default=0.0)
                if rr > R - 0.3 - 0.025:
                    problems.append(f"{ref}.{pad['num']}: copper at r={rr:.3f} (edge clearance {R - rr - 0.025:.3f} mm)")
    return problems


def mst_edges(points):
    """Prim's MST over [(x, y, side, label)] -> list of (i, j, length)."""
    n = len(points)
    if n < 2:
        return []
    in_tree = [False] * n
    dist = [math.inf] * n
    link = [-1] * n
    dist[0] = 0.0
    edges = []
    for _ in range(n):
        u = min((d, i) for i, d in enumerate(dist) if not in_tree[i])[1]
        in_tree[u] = True
        if link[u] >= 0:
            edges.append((link[u], u, dist[u]))
        for v in range(n):
            if not in_tree[v]:
                d = math.hypot(points[u][0] - points[v][0], points[u][1] - points[v][1])
                if d < dist[v]:
                    dist[v], link[v] = d, u
    return edges


def ratsnest(parts):
    nets = {}
    for ref, p in parts.items():
        for pad in p["pads"]:
            if pad["net"] and not pad["net"].startswith("unconnected"):
                nets.setdefault(pad["net"], []).append((pad["x"], pad["y"], pad["kind"], f"{ref}.{pad['num']}"))
    out = []
    for net, pts in nets.items():
        if net.lstrip("/") in SKIP_RATS:
            continue
        for i, j, d in mst_edges(pts):
            out.append((net, pts[i], pts[j], d))
    return out


def draw(place, parts, rats, png, title):
    fig, axes = plt.subplots(1, 2, figsize=(22, 11.5))
    outline = place["board"]["outline"]
    for ax, side, name in ((axes[0], "F", "TOP (F.Cu)"), (axes[1], "B", "BOTTOM (B.Cu), seen from the top")):
        if outline["type"] == "circle":
            ax.add_patch(Circle((0, 0), outline["radius"], fill=False, lw=1.2, color="k"))
            lim = outline["radius"] + 0.5
            ax.set_xlim(-lim, lim); ax.set_ylim(lim, -lim)
        else:
            w, h = outline["w"], outline["h"]
            ax.add_patch(Rectangle((-w / 2, -h / 2), w, h, fill=False, lw=1.2, color="k"))
            ax.set_xlim(-w / 2 - 0.5, w / 2 + 0.5); ax.set_ylim(h / 2 + 0.5, -h / 2 - 0.5)
        if place.get("placement_radius") and outline["type"] == "circle":
            ax.add_patch(Circle((0, 0), place["placement_radius"], fill=False, lw=0.5, ls=":", color="grey"))
        ax.set_aspect("equal")
        ax.set_title(name)
        ax.grid(True, lw=0.3, alpha=0.4)
        ax.set_xticks(range(-12, 13)); ax.set_yticks(range(-12, 13))
        for ref, p in parts.items():
            on_side = p["side"] == side or p["both_sides"]
            for pad in p["pads"]:
                if pad["kind"] == side or pad["kind"] == "THT":
                    col = "#c03030" if side == "F" else "#3060c0"
                    if pad["kind"] == "THT":
                        col = "#a08020"
                    if pad["outline"]:
                        ax.add_patch(Polygon(pad["outline"], closed=True, fc=col, ec="none", alpha=0.75))
                    if pad["net"] and ref not in ("J2",):
                        ax.text(pad["x"], pad["y"], pad["net"].lstrip("/")[:8], fontsize=3.2, ha="center",
                                va="center", color="white")
            if on_side and not p["no_courtyard"]:
                b = p["box"]
                ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fill=False, lw=0.6,
                                       ec="#d000d0" if p["side"] == side else "#999999",
                                       ls="--" if p["auto"] else "-"))
                ax.text(b[0], b[1] - 0.05, ref, fontsize=5, color="k", va="bottom")
        for net, a, b, d in rats:
            sides = {a[2], b[2]}
            if side in sides or "THT" in sides:
                cross = len(sides - {"THT"}) > 1
                ax.plot([a[0], b[0]], [a[1], b[1]], lw=0.5, color="#00a000" if not cross else "#e08000",
                        ls="--" if cross else "-")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="compact-22mm")
    ap.add_argument("--top", type=int, default=15, help="list this many longest connections")
    args = ap.parse_args()
    place, geo, rep = load(args.variant)
    parts = resolve(place, geo, rep)
    problems = checks(place, parts)
    rats = ratsnest(parts)
    total = sum(r[3] for r in rats)
    cross = sum(1 for r in rats if len({r[1][2], r[2][2]} - {"THT"}) > 1)
    png = paths.BUILD / args.variant / "floorplan.png"
    draw(place, parts, rats, png, f"{args.variant}: ratsnest {total:.1f} mm (GND excluded), "
                                  f"{len(rats)} connections, {cross} change side; problems {len(problems)}")
    print(f"ratsnest {total:.1f} mm over {len(rats)} connections ({cross} change side)")
    for net, a, b, d in sorted(rats, key=lambda r: -r[3])[:args.top]:
        print(f"  {d:5.2f} mm  {net:12s} {a[3]:>8s} -> {b[3]}")
    print(f"{len(problems)} problems")
    for p in problems:
        print("  " + p)
    print(f"image: {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
