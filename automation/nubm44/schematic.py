"""Programmatic KiCad schematic writer.

Symbols come from real KiCad libraries (standard or project). Connectivity is made
with wires and net labels attached to exact pin endpoints, so KiCad's own ERC and
netlister see a genuine electrical schematic.

Coordinates: schematic space is millimetres, Y down. Library symbol space is Y up.
Rotation follows KiCad: positive angles rotate counter-clockwise on screen.
"""
from __future__ import annotations

import math
import uuid as _uuid
from dataclasses import dataclass, field

from . import kicad_lib
from .sexpr import S, Sym, child, children, dump

NS = _uuid.UUID("5d3c9f0e-8a51-4f7b-9c1e-0b6f1a2d4e77")
FONT = S("font", S("size", 1.27, 1.27))


def uid(*parts) -> str:
    return str(_uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def snap(v: float, g: float = 1.27) -> float:
    return round(round(v / g) * g, 4)


def xform(px: float, py: float, sx: float, sy: float, rot: float) -> tuple[float, float]:
    """Library point (Y up) -> schematic point for a symbol at (sx, sy) rotated ``rot``."""
    x, y = px, -py
    t = math.radians(rot)
    xr = x * math.cos(t) + y * math.sin(t)
    yr = -x * math.sin(t) + y * math.cos(t)
    return (round(sx + xr, 4), round(sy + yr, 4))


def screen_dir(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


LABEL_ANGLE = {"right": 0, "up": 90, "left": 180, "down": 270}
# rotation that makes a power symbol's graphic point away from the pin
GND_ROT = {"down": 0, "right": 90, "up": 180, "left": 270}
UP_ROT = {"up": 0, "left": 90, "down": 180, "right": 270}


@dataclass
class Placed:
    ref: str
    lib_id: str
    x: float
    y: float
    rot: float
    unit: int
    node: list
    pins: dict = field(default_factory=dict)


class Schematic:
    def __init__(self, project: str, title: str, *, paper: str = "A3", rev: str = "A",
                 date: str = "", company: str = "", comments: tuple[str, ...] = (),
                 version: int = 20250114, generator_version: str = "9.0"):
        self.project = project
        self.uuid = uid(project, "root-sheet")
        self.paper = paper
        self.title = title
        self.rev = rev
        self.date = date
        self.company = company
        self.comments = comments
        self.version = version
        self.generator_version = generator_version
        self.lib_symbols: dict[str, list] = {}
        self.items: list[list] = []
        self.placed: dict[str, Placed] = {}
        self._pwr = 0
        self._flags = 0
        self._wires: list[tuple] = []

    # ---------------------------------------------------------------- symbols
    def _lib(self, lib_id: str) -> list:
        if lib_id not in self.lib_symbols:
            self.lib_symbols[lib_id] = kicad_lib.get_symbol(lib_id)
        return self.lib_symbols[lib_id]

    def place(self, ref: str, lib_id: str, x: float, y: float, rot: float = 0, *,
              value: str | None = None, footprint: str = "", datasheet: str = "~",
              description: str = "", fields: dict | None = None, unit: int = 1,
              in_bom: bool = True, on_board: bool = True, dnp: bool = False,
              hide_value: bool = False, ref_offset=None, value_offset=None) -> Placed:
        sym = self._lib(lib_id)
        x, y = snap(x), snap(y)
        lib_props = {str(p[1]): p for p in children(sym, "property")}
        is_power = kicad_lib.is_power_symbol(sym)
        if value is None:
            value = str(lib_props["Value"][2]) if "Value" in lib_props else lib_id.split(":")[1]
        pins = {k: v for k, v in kicad_lib.symbol_pins(sym).items() if v["unit"] in (0, unit)}
        key = f"{ref}#{unit}"
        # Fields are written horizontal. Library fields drawn vertically (R, L, thermistor) would then
        # sit across the body and each other, so two-pin parts get stacked labels beside the body.
        ref_at = child(lib_props["Reference"], "at") if "Reference" in lib_props else None
        if (ref_offset is None and value_offset is None and len(pins) == 2 and ref_at is not None
                and len(ref_at) > 3 and round(float(ref_at[3])) % 180 == 90):
            if round(rot) % 180 == 0:            # vertical body: labels to the right
                ref_offset, value_offset = (2.54, -1.27), (2.54, 1.27)
            else:                                # horizontal body: labels above and below
                ref_offset, value_offset = (-1.27, -2.54), (-1.27, 2.54)

        def prop(name, val, offset=None, hide=False):
            if offset is not None:
                px, py = x + offset[0], y + offset[1]
                justify = S("justify", Sym("left")) if offset[0] >= 0 else S("justify", Sym("right"))
            elif name in lib_props:
                at = child(lib_props[name], "at")
                px, py = xform(float(at[1]), float(at[2]), x, y, rot)
                justify = None
            else:
                px, py, justify = x, y, None
            eff = S("effects", FONT)
            if justify is not None:
                eff.append(justify)
            if hide:
                eff.append(S("hide", Sym("yes")))
            return S("property", name, val, S("at", round(px, 4), round(py, 4), 0), eff)

        node = S("symbol", S("lib_id", lib_id), S("at", x, y, rot), S("unit", unit),
                 S("exclude_from_sim", Sym("no")), S("in_bom", Sym("yes" if in_bom else "no")),
                 S("on_board", Sym("yes" if on_board else "no")), S("dnp", Sym("yes" if dnp else "no")),
                 S("uuid", uid(self.project, "sym", key)))
        node.append(prop("Reference", ref, ref_offset, hide=is_power))
        node.append(prop("Value", value, value_offset, hide=hide_value))
        node.append(prop("Footprint", footprint, (0, 0), hide=True))
        node.append(prop("Datasheet", datasheet, (0, 0), hide=True))
        node.append(prop("Description", description, (0, 0), hide=True))
        for k, v in (fields or {}).items():
            node.append(prop(k, str(v), (0, 0), hide=True))
        for num in sorted(pins, key=_pin_sort):
            node.append(S("pin", num, S("uuid", uid(self.project, "pin", key, num))))
        node.append(S("instances", S("project", self.project,
                                     S("path", f"/{self.uuid}", S("reference", ref), S("unit", unit)))))
        self.items.append(node)
        placed = Placed(ref, lib_id, x, y, rot, unit, node, pins)
        self.placed[key] = placed
        return placed

    def _get(self, ref: str, unit: int = 1) -> Placed:
        return self.placed[f"{ref}#{unit}"]

    def pin_end(self, ref: str, pin: str, unit: int = 1) -> tuple[float, float, str]:
        """Pin connection point and the outward direction on screen."""
        p = self._get(ref, unit)
        if pin not in p.pins:
            raise KeyError(f"{ref} unit {unit} has no pin {pin}; pins: {sorted(p.pins)}")
        info = p.pins[pin]
        x0, y0 = xform(info["x"], info["y"], p.x, p.y, p.rot)
        a = math.radians(info["angle"])
        x1, y1 = xform(info["x"] - math.cos(a), info["y"] - math.sin(a), p.x, p.y, p.rot)
        return x0, y0, screen_dir(x1 - x0, y1 - y0)

    # --------------------------------------------------------------- drawing
    def wire(self, *pts: tuple[float, float]) -> None:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if (x0, y0) == (x1, y1):
                continue
            self._wires.append(((x0, y0), (x1, y1)))
            self.items.append(S("wire", S("pts", S("xy", x0, y0), S("xy", x1, y1)),
                                S("stroke", S("width", 0), S("type", Sym("default"))),
                                S("uuid", uid(self.project, "wire", x0, y0, x1, y1))))

    def junction(self, x: float, y: float) -> None:
        self.items.append(S("junction", S("at", x, y), S("diameter", 0),
                            S("color", 0, 0, 0, 0), S("uuid", uid(self.project, "junction", x, y))))

    def _stub(self, ref, pin, unit, length):
        x0, y0, d = self.pin_end(ref, pin, unit)
        dx, dy = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}[d]
        x1, y1 = round(x0 + dx * length, 4), round(y0 + dy * length, 4)
        if length:
            self.wire((x0, y0), (x1, y1))
        return x1, y1, d

    def label(self, ref: str, pin: str, net: str, *, unit: int = 1, stub: float = 2.54,
              kind: str = "label") -> None:
        x, y, d = self._stub(ref, pin, unit, stub)
        angle = LABEL_ANGLE[d]
        justify = [Sym("left"), Sym("bottom")] if angle in (0, 90) else [Sym("right"), Sym("bottom")]
        node = S(kind, net)
        if kind == "global_label":
            node.append(S("shape", Sym("passive")))
        node += [S("at", x, y, angle), S("fields_autoplaced", Sym("yes")),
                 S("effects", FONT, S("justify", *justify)),
                 S("uuid", uid(self.project, kind, ref, unit, pin, net))]
        self.items.append(node)

    def power(self, ref: str, pin: str, lib_id: str = "power:GND", *, unit: int = 1,
              stub: float = 2.54) -> None:
        x, y, d = self._stub(ref, pin, unit, stub)
        sym = self._lib(lib_id)
        graphic_down = lib_id.endswith(("GND", "GNDA", "GNDD", "GNDPWR", "Earth"))
        rot = (GND_ROT if graphic_down else UP_ROT)[d]
        if lib_id == "power:PWR_FLAG":
            self._flags += 1
            pref = f"#FLG{self._flags:02d}"
        else:
            self._pwr += 1
            pref = f"#PWR{self._pwr:03d}"
        self.place(pref, lib_id, x, y, rot)

    def flag(self, x: float, y: float, direction: str = "up") -> None:
        self._flags += 1
        self.place(f"#FLG{self._flags:02d}", "power:PWR_FLAG", x, y, UP_ROT[direction])

    def no_connect(self, ref: str, pin: str, unit: int = 1) -> None:
        x, y, _ = self.pin_end(ref, pin, unit)
        self.items.append(S("no_connect", S("at", x, y), S("uuid", uid(self.project, "nc", ref, unit, pin))))

    def text(self, s: str, x: float, y: float, size: float = 1.27, bold: bool = False) -> None:
        font = S("font", S("size", size, size))
        if bold:
            font.append(S("bold", Sym("yes")))
        self.items.append(S("text", s, S("exclude_from_sim", Sym("no")), S("at", x, y, 0),
                            S("effects", font, S("justify", Sym("left"), Sym("top"))),
                            S("uuid", uid(self.project, "text", s[:40], x, y))))

    def rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.items.append(S("rectangle", S("start", x0, y0), S("end", x1, y1),
                            S("stroke", S("width", 0.254), S("type", Sym("dash"))),
                            S("fill", S("type", Sym("none"))),
                            S("uuid", uid(self.project, "rect", x0, y0, x1, y1))))

    # ---------------------------------------------------------------- output
    def to_node(self) -> list:
        tb = S("title_block", S("title", self.title), S("date", self.date), S("rev", self.rev),
               S("company", self.company))
        for i, c in enumerate(self.comments, start=1):
            tb.append(S("comment", i, c))
        root = S("kicad_sch", S("version", self.version), S("generator", "eeschema"),
                 S("generator_version", self.generator_version), S("uuid", self.uuid),
                 S("paper", self.paper), tb,
                 S("lib_symbols", *self.lib_symbols.values()))
        root += self.items
        root.append(S("sheet_instances", S("path", "/", S("page", "1"))))
        root.append(S("embedded_fonts", Sym("no")))
        return root

    def write(self, path) -> None:
        dump(self.to_node(), path)


def _pin_sort(k: str):
    return (0, int(k), "") if k.isdigit() else (1, 0, k)
