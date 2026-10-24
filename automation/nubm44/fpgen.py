"""Project footprint generator (writes hardware/libraries/nubm44.pretty).

Every footprint cites its dimensional source. Coordinates are millimetres, KiCad
footprint convention (Y down, pin 1 at top-left for ICs).
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path

from .sexpr import S, Sym, dump

NS = uuid.UUID("0b8a6f8e-6d9c-4c1e-9c55-7f3e8a2b9d10")
FP_VERSION = 20241229          # KiCad 9 format; KiCad 10 reads it (upgrade with `kicad-cli fp upgrade`)


def _uid(*p) -> str:
    return str(uuid.uuid5(NS, "/".join(map(str, p))))


def _text(kind, value, x, y, layer, size=0.8, hide=False):
    eff = S("effects", S("font", S("size", size, size), S("thickness", round(size * 0.15, 3))))
    node = S("property", kind, value, S("at", x, y, 0), S("layer", layer))
    if hide:
        node.append(S("hide", Sym("yes")))
    node += [S("uuid", _uid("prop", kind, value, x, y)), eff]
    return node


def _line(x0, y0, x1, y1, layer, w):
    return S("fp_line", S("start", x0, y0), S("end", x1, y1),
             S("stroke", S("width", w), S("type", Sym("solid"))), S("layer", layer),
             S("uuid", _uid("line", x0, y0, x1, y1, layer)))


def _rect(x0, y0, x1, y1, layer, w):
    return S("fp_rect", S("start", x0, y0), S("end", x1, y1),
             S("stroke", S("width", w), S("type", Sym("solid"))), S("fill", Sym("no")), S("layer", layer),
             S("uuid", _uid("rect", x0, y0, x1, y1, layer)))


def _circle(cx, cy, r, layer, w, fill=False):
    return S("fp_circle", S("center", cx, cy), S("end", cx + r, cy),
             S("stroke", S("width", w), S("type", Sym("solid"))), S("fill", Sym("yes" if fill else "no")),
             S("layer", layer), S("uuid", _uid("circle", cx, cy, r, layer)))


def _fp_text(text, x, y, layer, size=0.6):
    return S("fp_text", Sym("user"), text, S("at", x, y, 0), S("layer", layer),
             S("uuid", _uid("fptext", text, x, y, layer)),
             S("effects", S("font", S("size", size, size), S("thickness", round(size * 0.15, 3)))))


def smd_rr(num, x, y, w, h, r=0.05, side="F", paste=True, mask_margin=None):
    layers = [f"{side}.Cu", f"{side}.Mask"] + ([f"{side}.Paste"] if paste else [])
    node = S("pad", str(num), Sym("smd"), Sym("roundrect"), S("at", x, y), S("size", w, h),
             S("layers", *layers), S("roundrect_rratio", round(min(0.5, r / min(w, h)), 4)))
    if mask_margin is not None:
        node.append(S("solder_mask_margin", mask_margin))
    node.append(S("uuid", _uid("pad", num, x, y, side)))
    return node


def smd_custom(num, poly, anchor, side="F", anchor_size=0.2):
    """Custom-shape SMD pad. ``poly`` is in footprint coordinates. ``anchor`` must lie inside the copper
    with at least ``anchor_size``/2 clearance to every edge, because the anchor shape is copper too."""
    ax, ay = anchor
    rel = [(round(x - ax, 4), round(y - ay, 4)) for x, y in poly]
    return S("pad", str(num), Sym("smd"), Sym("custom"), S("at", round(ax, 4), round(ay, 4)),
             S("size", anchor_size, anchor_size),
             S("layers", f"{side}.Cu", f"{side}.Mask", f"{side}.Paste"),
             S("options", S("clearance", Sym("outline")), S("anchor", Sym("rect"))),
             S("primitives", S("gr_poly", S("pts", *[S("xy", x, y) for x, y in rel]),
                                S("width", 0), S("fill", Sym("yes")))),
             S("uuid", _uid("cpad", num, ax, ay, side)))


def tht_circle(num, x, y, size, drill, layers=("*.Cu", "*.Mask")):
    return S("pad", str(num), Sym("thru_hole"), Sym("circle"), S("at", x, y), S("size", size, size),
             S("drill", drill), S("layers", *layers), S("remove_unused_layers", Sym("no")),
             S("uuid", _uid("tht", num, x, y)))


def footprint(name, descr, tags, items, attr="smd", layer="F.Cu", ref_y=-3.0, val_y=3.0, model=None):
    node = S("footprint", name, S("version", FP_VERSION), S("generator", "nubm44_fpgen"),
             S("generator_version", "1.0"), S("layer", layer), S("descr", descr), S("tags", tags),
             _text("Reference", "REF**", 0, ref_y, "F.SilkS"),
             _text("Value", name, 0, val_y, "F.Fab"),
             _text("Datasheet", "", 0, 0, "F.Fab", hide=True),
             _text("Description", descr, 0, 0, "F.Fab", hide=True),
             S("attr", Sym(attr)))
    node += items
    node.append(S("embedded_fonts", Sym("no")))
    if model:
        node.append(S("model", model, S("offset", S("xyz", 0, 0, 0)), S("scale", S("xyz", 1, 1, 1)),
                      S("rotate", S("xyz", 0, 0, 0))))
    return node


# ---------------------------------------------------------------------- TPS552882 RPM0026A
# Pad geometry extracted from the vector land-pattern drawing on SLVSFC5 p.39 (drawing 4224618/A 10/2018),
# scale calibrated with the printed 0.625/0.375/1.425 mm dimensions (factor 1.0339 on the nominal 20X).
# Verified against printed dimensions 1.4875, 0.225, 0.4, 0.35, 0.6, 0.725, 1.6375, 1.05, 1.125.

def tps552882_rpm0026a():
    items = []
    # left column, pins 2..6 (pin 1 and 7 are L-shaped)
    for pin, y in zip(range(2, 7), (-1.0, -0.5, 0.0, 0.5, 1.0)):
        w = 0.6 if pin in (2, 6) else 0.725
        items.append(smd_rr(pin, -2.2 + w / 2, y, w, 0.25))
    # bottom row, pins 8..12
    for pin, x in zip(range(8, 13), (-1.125, -0.625, -0.125, 0.625, 1.125)):
        items.append(smd_rr(pin, x, 1.6375, 0.25, 0.625))
    # right column, pins 14..18 (bottom to top)
    for pin, y in zip(range(14, 19), (1.0, 0.5, 0.0, -0.5, -1.0)):
        w = 0.6 if pin in (14, 18) else 0.725
        items.append(smd_rr(pin, 2.2 - w / 2, y, w, 0.25))
    # top row, pins 20..23 (right to left)
    for pin, x, h in ((20, 1.05, 0.675), (21, 0.25, 0.6), (22, -0.25, 0.6), (23, -1.05, 0.675)):
        items.append(smd_rr(pin, x, -1.95 + h / 2, 0.25, h))
    # centre pads 24 PGND, 25 SW2, 26 VOUT
    for pin, x in ((24, -0.625), (25, 0.0), (26, 0.625)):
        items.append(smd_rr(pin, x, 0.0, 0.375, 1.425))
    # L-shaped corner pads
    # anchors sit at the centre of each L's horizontal arm (arm height 0.225 mm > anchor 0.2 mm)
    items.append(smd_custom(1, [(-2.2, -1.6), (-1.825, -1.6), (-1.825, -1.95), (-1.425, -1.95),
                                (-1.425, -1.375), (-2.2, -1.375)], anchor=(-1.8125, -1.4875)))
    items.append(smd_custom(19, [(1.425, -1.375), (1.425, -1.95), (1.825, -1.95), (1.825, -1.6),
                                 (2.2, -1.6), (2.2, -1.375)], anchor=(1.8125, -1.4875)))
    items.append(smd_custom(7, [(-2.2, 1.375), (-1.5, 1.375), (-1.5, 1.95), (-1.85, 1.95),
                                (-1.85, 1.6), (-2.2, 1.6)], anchor=(-1.85, 1.4875)))
    items.append(smd_custom(13, [(1.5, 1.375), (2.2, 1.375), (2.2, 1.6), (1.85, 1.6),
                                 (1.85, 1.95), (1.5, 1.95)], anchor=(1.85, 1.4875)))
    # body 4.0 x 3.5, courtyard 0.25 beyond the land pattern
    items += [_rect(-2.0, -1.75, 2.0, 1.75, "F.Fab", 0.1), _rect(-2.45, -2.2, 2.45, 2.2, "F.CrtYd", 0.05)]
    items += [_line(-2.11, -2.11, -2.4, -2.11, "F.SilkS", 0.12), _circle(-2.45, -2.45, 0.1, "F.SilkS", 0.12, True),
              _line(2.11, 2.11, 2.4, 2.11, "F.SilkS", 0.12), _line(2.11, -2.11, 2.4, -2.11, "F.SilkS", 0.12),
              _line(-2.11, 2.11, -2.4, 2.11, "F.SilkS", 0.12),
              _line(-2.0, -1.25, -1.5, -1.75, "F.Fab", 0.1), _fp_text("${REFERENCE}", 0, 0, "F.Fab", 0.5)]
    return footprint("TI_RPM0026A_VQFN-HR-26_4x3.5mm_P0.5mm",
                     "TI RPM0026A VQFN-HR 26-pin 4.0x3.5 mm (TPS552882/TPS55288). Land pattern per SLVSFC5 p.39, "
                     "drawing 4224618/A; pads extracted from vector geometry.",
                     "VQFN-HR TPS552882 TPS55288 RPM0026A", items, ref_y=-3.0, val_y=3.0,
                     model="${KIPRJMOD}/../models/TI_RPM0026A.wrl")


# ---------------------------------------------------------------------- contacts and pads

def spring_pad(diameter=6.0, side="B"):
    """Centre battery-spring pad (battery side). No vias inside the pad; stitching vias are placed by the
    layout script around it so solder does not wick away from the spring joint."""
    items = [S("pad", "1", Sym("smd"), Sym("circle"), S("at", 0, 0), S("size", diameter, diameter),
               S("layers", f"{side}.Cu", f"{side}.Mask"), S("uuid", _uid("spring", diameter)))]
    items += [_circle(0, 0, diameter / 2 + 0.25, f"{side}.CrtYd", 0.05),
              _circle(0, 0, diameter / 2 - 0.3, f"{side}.Fab", 0.1),
              _fp_text("B+ SPRING", 0, 0, f"{side}.Fab", 0.6)]
    fp = footprint(f"Contact_Spring_Pad_D{diameter:.1f}mm",
                   f"Battery centre-spring solder pad, {diameter} mm, hand-soldered spring (manual assembly)",
                   "battery spring contact flashlight driver", items, layer=f"{side}.Cu", ref_y=0, val_y=0)
    return _flip_texts(fp, side)


def ring_contact(r_mid=10.20, width=0.8, n_seg=20, via_drill=0.3, via_size=0.6, segment_gap=0.7):
    """Perimeter battery-negative contact ring on both sides (pad "1" everywhere).

    Built from ``n_seg`` tangential arc-segment pads per side with a plated stitching via in each
    gap, plus a continuous solder-mask opening so the whole ring is exposed contact surface.
    A single annular custom pad is avoided on purpose: Specctra DSN cannot describe the hole, so the
    autorouter would see a solid disc covering the board. The GND copper pour closes the gaps after
    routing."""
    items = []
    seg_angle = 360.0 / n_seg
    arc_len = 2 * math.pi * r_mid / n_seg
    pad_len = round(arc_len - segment_gap, 3)
    for k in range(n_seg):
        a = math.radians(k * seg_angle)
        x, y = round(r_mid * math.cos(a), 4), round(r_mid * math.sin(a), 4)
        for side in ("F", "B"):
            # long axis tangential; KiCad pad angles are counter-clockwise on screen (Y down)
            items.append(S("pad", "1", Sym("smd"), Sym("roundrect"), S("at", x, y, round(-k * seg_angle + 90, 3)),
                           S("size", pad_len, width), S("layers", f"{side}.Cu"),
                           S("roundrect_rratio", 0.25), S("uuid", _uid("ringseg", side, k))))
        av = math.radians((k + 0.5) * seg_angle)
        items.append(tht_circle("1", round(r_mid * math.cos(av), 4), round(r_mid * math.sin(av), 4),
                                via_size, via_drill))
    for side in ("F", "B"):
        items.append(S("fp_circle", S("center", 0, 0), S("end", r_mid, 0),
                       S("stroke", S("width", width), S("type", Sym("solid"))), S("fill", Sym("no")),
                       S("layer", f"{side}.Mask"), S("uuid", _uid("ringmask", side))))
    # No courtyard: a closed courtyard circle would be treated as covering the whole board interior.
    items += [_circle(0, 0, r_mid, "F.Fab", 0.1)]
    fp = footprint(f"Contact_Ring_R{r_mid:.2f}_W{width:.2f}mm",
                   "Perimeter B- contact ring, both sides: segmented pads + stitching vias + continuous mask "
                   "opening (PCB feature, no part)",
                   "battery ring contact driver", items, attr="through_hole", ref_y=-(r_mid - 1.5), val_y=r_mid - 1.5)
    attr = next(n for n in fp if isinstance(n, list) and n and n[0] == "attr")
    attr += [Sym("exclude_from_pos_files"), Sym("exclude_from_bom"), Sym("allow_missing_courtyard")]
    return fp


def laser_pads(pitch=4.0, drill=1.1, size=2.2):
    items = [tht_circle(1, -pitch / 2, 0, size, drill), tht_circle(2, pitch / 2, 0, size, drill)]
    items += [_rect(-pitch / 2 - size / 2 - 0.25, -size / 2 - 0.25, pitch / 2 + size / 2 + 0.25, size / 2 + 0.25,
                    "F.CrtYd", 0.05),
              _fp_text("LD+", -pitch / 2, -size / 2 - 0.7, "F.SilkS", 0.7),
              _fp_text("LD-", pitch / 2, -size / 2 - 0.7, "F.SilkS", 0.7)]
    return footprint(f"Laser_Pads_2x_PTH_P{pitch:.1f}mm_D{drill:.1f}mm",
                     f"Laser diode wire pads: 1 = LD+ (anode), 2 = LD- (cathode/GND); {drill} mm plated holes for 20 AWG",
                     "laser diode wire pad", items, attr="through_hole", ref_y=-2.2, val_y=2.2)


def wire_pad(drill=1.3, size=2.6, label=""):
    items = [tht_circle(1, 0, 0, size, drill), _circle(0, 0, size / 2 + 0.25, "F.CrtYd", 0.05)]
    if label:
        items.append(_fp_text(label, 0, -size / 2 - 0.7, "F.SilkS", 0.8))
    return footprint(f"Wire_Pad_PTH_D{drill:.1f}mm", f"Plated wire pad, {drill} mm hole", "wire pad",
                     items, attr="through_hole", ref_y=-2.0, val_y=2.0)


def smd_pad(diameter=1.0, side="F", label_layer=None):
    items = [S("pad", "1", Sym("smd"), Sym("circle"), S("at", 0, 0), S("size", diameter, diameter),
               S("layers", f"{side}.Cu", f"{side}.Mask"), S("uuid", _uid("smdpad", diameter, side))),
             _circle(0, 0, diameter / 2 + 0.2, f"{side}.CrtYd", 0.05)]
    fp = footprint(f"Pad_SMD_D{diameter:.1f}mm_{side}", f"Round SMD test/wire pad, {diameter} mm, {side} side",
                   "test point pad", items, layer=f"{side}.Cu", ref_y=-1.2, val_y=1.2)
    return _flip_texts(fp, side)


def _flip_texts(fp, side):
    if side == "F":
        return fp
    for node in fp:
        if isinstance(node, list) and node and node[0] in ("property", "fp_text"):
            for c in node:
                if isinstance(c, list) and c and c[0] == "layer":
                    c[1] = str(c[1]).replace("F.", "B.")
                if isinstance(c, list) and c and c[0] == "effects":     # back-side text reads mirrored
                    c.append(S("justify", Sym("mirror")))
    return fp


def kelvin_1206():
    """1206 current shunt with Kelvin sense pads (net tie).

    Pads 1 and 4 copy KiCad's R_1206_3216Metric current pads (+-1.4625 mm, 1.125 x 1.75 mm).
    Pads 2 and 3 are copper-only sense pads 0.2 mm inside each current pad's inner edge, joined to it
    by a 0.25 mm net-tie bridge. Pin numbering follows the KiCad Device:R_Shunt symbol
    (1 = current A, 2 = sense A, 3 = sense B, 4 = current B)."""
    items = [smd_rr(1, -1.4625, 0, 1.125, 1.75, r=0.25), smd_rr(4, 1.4625, 0, 1.125, 1.75, r=0.25)]
    for num, x in ((2, -0.55), (3, 0.55)):
        items.append(S("pad", str(num), Sym("smd"), Sym("rect"), S("at", x, 0), S("size", 0.3, 0.3),
                       S("layers", "F.Cu"), S("uuid", _uid("kelvin", num))))
    for x0, x1 in ((-0.95, -0.55), (0.55, 0.95)):
        items.append(S("fp_rect", S("start", x0, -0.125), S("end", x1, 0.125),
                       S("stroke", S("width", 0), S("type", Sym("solid"))), S("fill", Sym("yes")),
                       S("layer", "F.Cu"), S("uuid", _uid("nettie", x0))))
    items += [_rect(-2.28, -1.13, 2.28, 1.13, "F.CrtYd", 0.05), _rect(-1.6, -0.8, 1.6, 0.8, "F.Fab", 0.1),
              _line(-0.727, -0.91, 0.727, -0.91, "F.SilkS", 0.12), _line(-0.727, 0.91, 0.727, 0.91, "F.SilkS", 0.12),
              _fp_text("${REFERENCE}", 0, 0, "F.Fab", 0.5)]
    fp = footprint("R_1206_3216Metric_Kelvin",
                   "1206 current-sense resistor with Kelvin sense pads (net tie 1-2, 3-4); current pads per "
                   "KiCad R_1206_3216Metric", "shunt kelvin 4-terminal net tie", items, ref_y=-1.8, val_y=1.8,
                   model="${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_1206_3216Metric.step")
    # net-tie declaration must precede graphics in the file; insert after (attr ...)
    idx = next(i for i, n in enumerate(fp) if isinstance(n, list) and n and n[0] == "attr")
    fp.insert(idx + 1, S("net_tie_pad_groups", "1,2", "3,4"))
    return fp


def build_all(out_dir: Path) -> list[str]:
    import yaml
    from . import paths

    pcb = yaml.safe_load((paths.DESIGN / "parameters.yaml").read_text(encoding="utf-8"))["pcb"]
    out_dir.mkdir(parents=True, exist_ok=True)
    ring = ring_contact(r_mid=pcb["ring_mid_radius_mm"], width=pcb["ring_width_mm"],
                        n_seg=pcb["ring_segments"], segment_gap=pcb["ring_segment_gap_mm"],
                        via_size=pcb["via_diameter_mm"], via_drill=pcb["via_drill_mm"])
    fps = [tps552882_rpm0026a(), kelvin_1206(), spring_pad(5.0, "B"), ring, laser_pads(),
           wire_pad(1.3, 2.6), smd_pad(1.0, "F"), smd_pad(1.0, "B"), smd_pad(1.4, "F"), smd_pad(0.8, "B")]
    names = []
    for fp in fps:
        name = str(fp[1])
        dump(fp, out_dir / f"{name}.kicad_mod")
        names.append(name)
    return names
