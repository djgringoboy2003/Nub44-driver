"""Placement optimiser for the small parts of a variant (simulated annealing, no KiCad needed).

Moves the listed parts to minimise weighted net length while keeping every hard rule the build checks:
no courtyard overlap on a side (both_sides parts count on both), courtyards inside placement_radius,
and clear of source vias, via-field polygons and the placement.yaml keep-out boxes (a through via blocks
both sides). Pads on plane nets are scored by their distance to that net's plane polygons instead of
by net length: GND is a solid inner plane (free), VBAT and VOUT have pours listed in zones_pre.

  usage: python place_opt.py --variant compact-22mm --refs R10,R11,... [--flip R5,R6] [--iters 60000] [--write]

Parts named in --flip may also change side. Courtyards also stay off the source tracks of their side
(width plus clearance) and off the power pours and router keep-outs of that side.

placement.yaml may add "place_opt: {near: {REF: [x, y] | "REF.PAD", ...}, near_weight: 3}" to tie parts such as
decoupling capacitors to the pin or via they serve (cost = weight x centre distance to the target).

Without --write it prints the result and the score change. With --write the parts become manual "pos"
entries in placement.yaml (tagged "place_opt"), so the outcome stays explicit and reviewable; rerun the
floorplan checker and the KiCad build afterwards, as for any placement edit.
"""
from __future__ import annotations

import argparse
import math
import random
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "automation/placement"))

import floorplan  # noqa: E402
from nubm44 import paths  # noqa: E402

PLANE_NETS = {"GND"}                       # solid In1 plane: a fanout via reaches it anywhere
POUR_NETS = ("VBAT", "VOUT")               # reached at their zones_pre pours (distance cost)
WEIGHT = {"FB": 4.0, "COMP": 4.0, "COMP_RC": 3.0, "ILIM": 3.0, "FSW": 3.0, "ISP_K": 3.0, "ISN_K": 3.0,
          "EN_UVLO": 1.5, "CS_OUT": 1.5}
VIA_R = 0.30


def norm(n: str) -> str:
    return n.lstrip("/")


def rect_seg_dist(box, a, b):
    """Distance between an axis-aligned rectangle and a segment (0 when they touch)."""
    x0, y0, x1, y1 = box
    def inside(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    if inside(a) or inside(b):
        return 0.0
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    edges = list(zip(corners, corners[1:] + corners[:1]))
    best = math.inf
    for c, d in edges:
        best = min(best, seg_seg(a, b, c, d))
    return best


def seg_seg(a, b, c, d):
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(seg_pt(a, c, d), seg_pt(b, c, d), seg_pt(c, a, b), seg_pt(d, a, b))


def seg_pt(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def rect_poly_overlap(box, poly):
    x0, y0, x1, y1 = box
    if any(x0 <= px <= x1 and y0 <= py <= y1 for px, py in poly):
        return True
    if any(point_poly_dist(cx, cy, poly) == 0.0 for cx in (x0, x1) for cy in (y0, y1)):
        return True
    return any(rect_seg_dist(box, a, b) == 0.0 for a, b in zip(poly, poly[1:] + poly[:1]))


def point_poly_dist(x, y, poly):
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    if inside:
        return 0.0
    best = math.inf
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / L2))
        best = min(best, math.hypot(x - x0 - t * dx, y - y0 - t * dy))
    return best


class Model:
    def __init__(self, variant: str, refs: list[str]):
        self.place, self.geo, rep = floorplan.load(variant)
        self.parts = floorplan.resolve(self.place, self.geo, rep)
        self.refs = refs
        self.gap = self.place.get("courtyard_gap", 0.0) + 0.01   # margin: written positions are rounded
        self.r_max = self.place.get("placement_radius", 1e9)
        clr = 0.15
        self.blocks = {"F": [], "B": []}       # keep-out boxes per side
        for v in self.place.get("vias") or []:
            r = VIA_R + clr
            for s in "FB":
                self.blocks[s].append((v["x"] - r, v["y"] - r, v["x"] + r, v["y"] + r))
        for vf in self.place.get("via_fields") or []:
            xs = [p[0] for p in vf["polygon"]]
            ys = [p[1] for p in vf["polygon"]]
            for s in "FB":
                self.blocks[s].append((min(xs), min(ys), max(xs), max(ys)))
        for s, boxes in (self.place.get("keepouts") or {}).items():
            self.blocks[s].extend(tuple(b) for b in boxes)
        layer_side = {"F.Cu": "F", "B.Cu": "B"}
        self.track_blocks = {"F": [], "B": []}       # (a, b, keep-away distance)
        for t in (self.place.get("tracks") or []) + (self.place.get("tracks_post") or []):
            if t["layer"] in layer_side:
                for a, b in zip(t["pts"], t["pts"][1:]):
                    self.track_blocks[layer_side[t["layer"]]].append((tuple(a), tuple(b), t["width"] / 2 + clr))
        self.poly_blocks = {"F": [], "B": []}
        for z in (self.place.get("zones_pre") or []) + (self.place.get("router_keepouts") or []):
            if z["layer"] in layer_side and "polygon" in z:
                self.poly_blocks[layer_side[z["layer"]]].append([tuple(p) for p in z["polygon"]])
        self.pours = {n: [] for n in POUR_NETS}
        for z in self.place.get("zones_pre") or []:
            if norm(z["net"]) in self.pours and "polygon" in z:
                self.pours[norm(z["net"])].append([tuple(p) for p in z["polygon"]])
        self.via_points = {}
        for v in self.place.get("vias") or []:
            self.via_points.setdefault(v["net"], []).append((v["x"], v["y"]))
        self.state = {r: (self.parts[r]["x"], self.parts[r]["y"], self.parts[r]["rot"], self.parts[r]["side"])
                      for r in refs}
        opt = self.place.get("place_opt") or {}
        self.near_weight = opt.get("near_weight", 3.0)
        self.near = {}
        for ref, target in (opt.get("near") or {}).items():
            if isinstance(target, str):
                tref, tpad = target.split(".")
                pad = next(q for q in self.parts[tref]["pads"] if q["num"] == tpad)
                self.near[ref] = (pad["x"], pad["y"])
            else:
                self.near[ref] = tuple(target)
        self.nets = {}
        for ref, p in self.parts.items():
            for pad in p["pads"]:
                n = norm(pad["net"])
                if n and not n.startswith("unconnected") and n not in PLANE_NETS:
                    self.nets.setdefault(n, set()).add(ref)

    def placed(self, ref, st=None):
        """Courtyard box and pads of ref at state st (default: current)."""
        if ref not in self.state:
            p = self.parts[ref]
            return p["box"], [(norm(q["net"]), q["x"], q["y"]) for q in p["pads"]]
        x, y, rot, side = st or self.state[ref]
        g = self.geo[ref]
        mirror = (side == "B") != g["native_back"]
        x0, y0, x1, y1 = g["courtyard"]
        cs = [floorplan.xform(u, v, x, y, rot, mirror) for u, v in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
        box = (min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs))
        pads = [(norm(q["net"]), *floorplan.xform(q["x"], q["y"], x, y, rot, mirror)) for q in g["pads"]]
        return box, pads

    def sides(self, ref, st=None):
        side = (st or self.state[ref])[3] if ref in self.state else self.parts[ref]["side"]
        both = self.parts[ref]["both_sides"]
        return {"F", "B"} if both else {side}

    def feasible(self, ref, st) -> bool:
        box, _ = self.placed(ref, st)
        if max(math.hypot(cx, cy) for cx in (box[0], box[2]) for cy in (box[1], box[3])) > self.r_max:
            return False
        g = self.gap
        for s in self.sides(ref, st):
            for b in self.blocks[s]:
                if not (box[2] <= b[0] or b[2] <= box[0] or box[3] <= b[1] or b[3] <= box[1]):
                    return False
            for a, b, keep in self.track_blocks[s]:
                if rect_seg_dist(box, a, b) < keep:
                    return False
            for poly in self.poly_blocks[s]:
                if rect_poly_overlap(box, poly):
                    return False
        for other, p in self.parts.items():
            if other == ref or p["no_courtyard"]:
                continue
            if not (self.sides(ref, st) & self.sides(other)):
                continue
            ob, _ = self.placed(other)
            if not (box[2] + g <= ob[0] or ob[2] + g <= box[0] or box[3] + g <= ob[1] or ob[3] + g <= box[1]):
                return False
        return True

    def net_cost(self, net) -> float:
        pts = list(self.via_points.get(net, []))
        for ref in self.nets.get(net, ()):
            _, pads = self.placed(ref)
            pts += [(x, y) for n, x, y in pads if n == net]
        if net in self.pours:
            # pads reach the pour: cost = distance of each pad to its nearest pour polygon
            return sum(min((point_poly_dist(x, y, poly) for poly in self.pours[net]), default=0.0) for x, y in pts)
        if len(pts) < 2:
            return 0.0
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return WEIGHT.get(net, 1.0) * ((max(xs) - min(xs)) + (max(ys) - min(ys)))

    def nets_of(self, ref):
        return {n for n, members in self.nets.items() if ref in members} | ({f"near:{ref}"} if ref in self.near else set())

    def cost_of(self, key) -> float:
        if key.startswith("near:"):
            ref = key[5:]
            x, y = self.state[ref][:2] if ref in self.state else (self.parts[ref]["x"], self.parts[ref]["y"])
            tx, ty = self.near[ref]
            return self.near_weight * math.hypot(x - tx, y - ty)
        return self.net_cost(key)

    def keys(self):
        return list(self.nets) + [f"near:{r}" for r in self.near]

    def total(self) -> float:
        return sum(self.cost_of(k) for k in self.keys())


def repair(model: Model, seed: int, flip=()) -> list[str]:
    """Move parts that start infeasible to the nearest feasible spot (spiral search, all rotations)."""
    rng = random.Random(seed)
    stuck = []
    for ref in model.refs:
        x, y, rot, side = model.state[ref]
        if model.feasible(ref, model.state[ref]):
            continue
        found = None
        sides = (side, "F" if side == "B" else "B") if ref in flip else (side,)
        for ring in range(1, 120):
            r = 0.1 * ring
            for _ in range(24):
                a = rng.random() * 2 * math.pi
                for dr in (0, 90, 180, 270):
                    for sd in sides:
                        st = (round(x + r * math.cos(a), 3), round(y + r * math.sin(a), 3), (rot + dr) % 360, sd)
                        if model.feasible(ref, st):
                            found = st
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
        if found:
            model.state[ref] = found
        else:
            stuck.append(ref)
    return stuck


def anneal(model: Model, iters: int, seed: int, step0: float = 2.0, flip=()) -> float:
    rng = random.Random(seed)
    cost = {k: model.cost_of(k) for k in model.keys()}
    current = sum(cost.values())
    t0, t1 = 2.0, 0.01
    refs = model.refs
    for k in range(iters):
        frac = k / max(1, iters - 1)
        temp = t0 * (t1 / t0) ** frac
        step = max(0.1, step0 * (1 - frac))
        if rng.random() < 0.15 and len(refs) > 1:
            a, b = rng.sample(refs, 2)
            sa, sb = model.state[a], model.state[b]
            if sa[3] != sb[3]:
                continue
            na = (sb[0], sb[1], sa[2], sa[3])
            nb = (sa[0], sa[1], sb[2], sb[3])
            old = (sa, sb)
            model.state[a], model.state[b] = na, nb
            ok = model.feasible(a, na) and model.feasible(b, nb)
            moved = (a, b)
        else:
            a = rng.choice(refs)
            sa = model.state[a]
            u = rng.random()
            if a in flip and u < 0.05:
                na = (sa[0], sa[1], sa[2], "F" if sa[3] == "B" else "B")
            elif u < 0.2:
                na = (sa[0], sa[1], (sa[2] + rng.choice((90, 180, 270))) % 360, sa[3])
            elif u < 0.3:
                # teleport anywhere in the placement disc: lets large parts leave crowded or distant spots
                a_, r_ = rng.random() * 2 * math.pi, model.r_max * math.sqrt(rng.random())
                na = (round(r_ * math.cos(a_), 3), round(r_ * math.sin(a_), 3), rng.choice((0, 90, 180, 270)), sa[3])
            else:
                na = (round(sa[0] + rng.gauss(0, step), 3), round(sa[1] + rng.gauss(0, step), 3), sa[2], sa[3])
            old = (sa,)
            model.state[a] = na
            ok = model.feasible(a, na)
            moved = (a,)
        if not ok:
            for r, s in zip(moved, old):
                model.state[r] = s
            continue
        touched = set().union(*(model.nets_of(r) for r in moved))
        new = {n: model.cost_of(n) for n in touched}
        delta = sum(new.values()) - sum(cost[n] for n in touched)
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            cost.update(new)
            current += delta
        else:
            for r, s in zip(moved, old):
                model.state[r] = s
    return current


def write_back(variant: str, model: Model) -> None:
    path = paths.HARDWARE / variant / "placement.yaml"
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    for ref in model.refs:
        x, y, rot, side = model.state[ref]
        rot = int(round(rot)) % 360
        entry = f"  {ref}: {{pos: [{x:.3f}, {y:.3f}, {rot}], side: {side}}}"
        pat = re.compile(rf"^  {re.escape(ref)}: \{{")
        idx = next(i for i, ln in enumerate(lines) if pat.match(ln))
        comment = lines[idx].split("#", 1)[1].strip() if "#" in lines[idx] else ""
        comment = re.sub(r"^place_opt;?\s*", "", comment)
        lines[idx] = entry + f"   # place_opt{'; ' + comment if comment else ''}"
    path.write_bytes(eol.join(lines).encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="compact-22mm")
    ap.add_argument("--refs", required=True, help="comma-separated parts to move")
    ap.add_argument("--flip", default="", help="comma-separated parts that may change side")
    ap.add_argument("--iters", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    refs = [r.strip() for r in args.refs.split(",") if r.strip()]
    model = Model(args.variant, refs)
    flip = {r.strip() for r in args.flip.split(",") if r.strip()}
    stuck = repair(model, args.seed, flip)
    if stuck:
        print(f"no feasible position found for {stuck}; they keep their start positions")
    before = model.total()
    after = anneal(model, args.iters, args.seed, flip=flip)
    print(f"weighted length {before:.1f} -> {after:.1f} mm")
    for r in refs:
        x, y, rot, side = model.state[r]
        flag = "" if model.feasible(r, model.state[r]) else "   INFEASIBLE"
        print(f"  {r}: ({x:.2f}, {y:.2f}) rot {int(rot) % 360} {side}{flag}")
    if args.write:
        write_back(args.variant, model)
        print("placement.yaml updated (place_opt entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
