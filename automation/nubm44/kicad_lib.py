"""Access to KiCad symbol and footprint libraries (standard + project).

Library identifiers use KiCad's ``Nickname:Item`` form. Standard libraries are read
from the KiCad install; the project library nickname is ``nubm44`` and lives in
``hardware/libraries``.
"""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

from . import paths
from .sexpr import Sym, child, children, head, load, loads

PROJECT_LIB = "nubm44"


# ---------------------------------------------------------------------- symbols

def _symbol_lib_location(nickname: str) -> Path:
    if nickname == PROJECT_LIB:
        return paths.LIBRARIES / f"{PROJECT_LIB}.kicad_sym"
    base = paths.kicad_symbols_dir()
    for cand in (base / f"{nickname}.kicad_sym", base / f"{nickname}.kicad_symdir"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"symbol library '{nickname}' not found under {base}")


@lru_cache(maxsize=None)
def _symbol_table(nickname: str) -> dict[str, list]:
    loc = _symbol_lib_location(nickname)
    table: dict[str, list] = {}
    files = sorted(loc.glob("*.kicad_sym")) if loc.is_dir() else [loc]
    for f in files:
        root = load(f)
        for sym in children(root, "symbol"):
            table[str(sym[1])] = sym
    return table


def _rename_units(sym: list, old: str, new: str) -> None:
    for unit in children(sym, "symbol"):
        name = str(unit[1])
        if name.startswith(old + "_"):
            unit[1] = new + name[len(old):]


def get_symbol(lib_id: str) -> list:
    """Return a flattened deep copy of a library symbol, named ``lib_id``."""
    nickname, name = lib_id.split(":", 1)
    table = _symbol_table(nickname)
    if name not in table:
        raise KeyError(f"symbol '{name}' not in library '{nickname}'")
    sym = copy.deepcopy(table[name])
    ext = child(sym, "extends")
    if ext is not None:
        parent_name = str(ext[1])
        parent = get_symbol(f"{nickname}:{parent_name}")
        # parent graphics/pins + child's properties
        child_props = {str(p[1]): p for p in children(sym, "property")}
        flat = [Sym("symbol"), name]
        for item in parent[2:]:
            if head(item) == "property" and str(item[1]) in child_props:
                flat.append(child_props.pop(str(item[1])))
            else:
                flat.append(item)
        for p in child_props.values():
            flat.append(p)
        _rename_units(flat, parent_name, name)
        sym = flat
    sym[1] = lib_id
    return sym


def symbol_pins(sym: list) -> dict[str, dict]:
    """Map pin number -> {name, type, x, y, angle, length, unit} (library coords, Y up)."""
    pins: dict[str, dict] = {}
    for unit in children(sym, "symbol"):
        uname = str(unit[1])
        try:
            unit_no = int(uname.rsplit("_", 2)[-2])
        except (ValueError, IndexError):
            unit_no = 0
        for pin in children(unit, "pin"):
            at = child(pin, "at")
            num = child(pin, "number")
            nm = child(pin, "name")
            ln = child(pin, "length")
            pins[str(num[1])] = {
                "name": str(nm[1]) if nm else "",
                "type": str(pin[1]),
                "x": float(at[1]), "y": float(at[2]),
                "angle": float(at[3]) if len(at) > 3 else 0.0,
                "length": float(ln[1]) if ln else 2.54,
                "unit": unit_no,
            }
    return pins


def is_power_symbol(sym: list) -> bool:
    return child(sym, "power") is not None


# ------------------------------------------------------------------- footprints

def _footprint_dir(nickname: str) -> Path:
    if nickname == PROJECT_LIB:
        return paths.LIBRARIES / f"{PROJECT_LIB}.pretty"
    d = paths.kicad_footprints_dir() / f"{nickname}.pretty"
    if not d.exists():
        raise FileNotFoundError(f"footprint library '{nickname}' not found at {d}")
    return d


def footprint_path(fp_id: str) -> Path:
    nickname, name = fp_id.split(":", 1)
    return _footprint_dir(nickname) / f"{name}.kicad_mod"


@lru_cache(maxsize=None)
def _footprint_cached(fp_id: str) -> list:
    path = footprint_path(fp_id)
    if not path.exists():
        raise FileNotFoundError(f"footprint '{fp_id}' not found ({path})")
    return load(path)


def get_footprint(fp_id: str) -> list:
    """Deep copy of a library footprint (module) node."""
    return copy.deepcopy(_footprint_cached(fp_id))


def footprint_pads(fp: list) -> list[dict]:
    out = []
    for pad in children(fp, "pad"):
        at = child(pad, "at")
        size = child(pad, "size")
        out.append({
            "number": str(pad[1]),
            "kind": str(pad[2]),
            "shape": str(pad[3]),
            "x": float(at[1]), "y": float(at[2]),
            "angle": float(at[3]) if len(at) > 3 else 0.0,
            "w": float(size[1]), "h": float(size[2]),
            "layers": [str(x) for x in child(pad, "layers")[1:]],
        })
    return out


def parse_text(text: str) -> list:
    return loads(text)
