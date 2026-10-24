"""Generate KiCad schematic symbols from datasheet pin tables.

Pin tables live in ``hardware/libraries/symbols/*.yaml``. Each entry cites the
datasheet revision and page so every pin assignment is traceable. Pins sharing a
name on the same side are stacked at one position (first visible, rest hidden
and passive), which is KiCad's library convention for multi-pad power pins.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .sexpr import S, Sym, dump

GRID = 2.54
PIN_LEN = 2.54
FONT = S("font", S("size", 1.27, 1.27))
VALID_TYPES = {"input", "output", "bidirectional", "tri_state", "passive", "free",
               "unspecified", "power_in", "power_out", "open_collector",
               "open_emitter", "no_connect"}


def _yes(flag: bool) -> Sym:
    return Sym("yes" if flag else "no")


def _prop(name: str, value: str, x: float, y: float, hide: bool = False, justify=None):
    eff = S("effects", FONT)
    if justify:
        eff.append(S("justify", *[Sym(j) for j in justify]))
    if hide:
        eff.append(S("hide", Sym("yes")))
    return S("property", name, value, S("at", x, y, 0), eff)


def _pin(number: str, name: str, ptype: str, x: float, y: float, angle: float, hidden: bool):
    if ptype not in VALID_TYPES:
        raise ValueError(f"pin {number}: invalid type {ptype}")
    node = S("pin", Sym(ptype), Sym("line"), S("at", x, y, angle), S("length", PIN_LEN))
    if hidden:
        node.append(S("hide", Sym("yes")))
    node.append(S("name", name, S("effects", FONT)))
    node.append(S("number", str(number), S("effects", FONT)))
    return node


def _side_slots(entries: list[dict]) -> list[list[dict]]:
    """Group consecutive entries that share a name into stacked slots."""
    slots: list[list[dict]] = []
    by_name: dict[str, list[dict]] = {}
    for e in entries:
        if e.get("gap"):
            slots.append([])
            continue
        key = e["name"]
        if key in by_name and e.get("stack", True):
            by_name[key].append(e)
        else:
            group = [e]
            by_name[key] = group
            slots.append(group)
    return slots


def build_symbol(spec: dict) -> list:
    name = spec["name"]
    sides = {s: spec.get("pins", {}).get(s, []) for s in ("left", "right", "top", "bottom")}
    slots = {s: _side_slots(v) for s, v in sides.items()}
    n_lr = max(len(slots["left"]), len(slots["right"]), 1)
    n_tb = max(len(slots["top"]), len(slots["bottom"]), 0)
    longest = max([len(e["name"]) for v in sides.values() for e in v if not e.get("gap")] or [4])
    width = spec.get("width") or max(
        GRID * (n_tb + 1),
        GRID * round((longest * 1.27 * 2 + 2 * GRID) / GRID),
        GRID * 4)
    height = spec.get("height") or GRID * (n_lr + 1)
    hw = round(width / 2 / GRID) * GRID
    hh = round(height / 2 / GRID) * GRID

    pins = []

    def place(side, idx, count, group):
        if side in ("left", "right"):
            y0 = (count - 1) * GRID / 2
            y = round((y0 - idx * GRID) / 1.27) * 1.27
            x = -hw - PIN_LEN if side == "left" else hw + PIN_LEN
            angle = 0 if side == "left" else 180
        else:
            x0 = -(count - 1) * GRID / 2
            x = round((x0 + idx * GRID) / 1.27) * 1.27
            y = hh + PIN_LEN if side == "top" else -hh - PIN_LEN
            angle = 270 if side == "top" else 90
        for k, e in enumerate(group):
            ptype = e["type"] if k == 0 else "passive"
            pins.append(_pin(e["number"], e["name"], ptype, x, y, angle, hidden=k > 0))

    for side in ("left", "right", "top", "bottom"):
        groups = slots[side]
        for i, g in enumerate(groups):
            if g:
                place(side, i, len(groups), g)

    ref = spec.get("reference", "U")
    sym = S("symbol", name,
            S("exclude_from_sim", _yes(False)),
            S("in_bom", _yes(True)),
            S("on_board", _yes(True)),
            _prop("Reference", ref, -hw, hh + 1.27, justify=["left", "bottom"]),
            _prop("Value", spec.get("value", name), hw, hh + 1.27, justify=["right", "bottom"]),
            _prop("Footprint", spec.get("footprint", ""), 0, -hh - 5.08, hide=True),
            _prop("Datasheet", spec.get("datasheet", "~"), 0, -hh - 7.62, hide=True),
            _prop("Description", spec.get("description", ""), 0, -hh - 10.16, hide=True),
            _prop("ki_keywords", spec.get("keywords", ""), 0, 0, hide=True),
            _prop("ki_fp_filters", spec.get("fp_filters", ""), 0, 0, hide=True),
            S("symbol", f"{name}_0_1",
              S("rectangle", S("start", -hw, hh), S("end", hw, -hh),
                S("stroke", S("width", 0.254), S("type", Sym("default"))),
                S("fill", S("type", Sym("background"))))),
            S("symbol", f"{name}_1_1", *pins))
    if spec.get("pin_names_offset") is not None:
        sym.insert(2, S("pin_names", S("offset", spec["pin_names_offset"])))
    return sym


def build_library(spec_dir: Path, out_file: Path, version: int, generator_version: str) -> list[str]:
    """Build every ``*.yaml`` symbol spec in ``spec_dir`` into one ``.kicad_sym`` file."""
    syms, names = [], []
    for f in sorted(spec_dir.glob("*.yaml")):
        spec = yaml.safe_load(f.read_text(encoding="utf-8"))
        syms.append(build_symbol(spec))
        names.append(spec["name"])
    lib = S("kicad_symbol_lib", S("version", version), S("generator", "nubm44_symgen"),
            S("generator_version", generator_version), *syms)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    dump(lib, out_file)
    return names
