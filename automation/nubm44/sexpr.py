"""Minimal S-expression reader/writer for KiCad files.

Representation
--------------
* a list node is a Python ``list`` whose first element is usually a ``Sym``
* ``Sym`` is a bare token (``kicad_sch``, ``yes``, ``smd``)
* ``str`` is a quoted string
* ``int`` / ``float`` are numbers

Numbers read from a file are kept as ``Sym`` so that round-tripping a library
item never changes its text.
"""
from __future__ import annotations

import math
from typing import Iterable, Iterator


class Sym(str):
    """A bare (unquoted) S-expression token."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Sym({str.__repr__(self)})"


Node = list


# --------------------------------------------------------------------------- read

_OPEN = object()
_CLOSE = object()


def _tokens(text: str) -> Iterator[object]:
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            yield _OPEN
            i += 1
        elif c == ")":
            yield _CLOSE
            i += 1
        elif c == '"':
            i += 1
            buf = []
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
                    i += 2
                elif c == '"':
                    i += 1
                    break
                else:
                    buf.append(c)
                    i += 1
            else:
                raise ValueError("unterminated string")
            yield "".join(buf)
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            yield Sym(text[i:j])
            i = j


def loads(text: str) -> Node:
    """Parse one top-level S-expression."""
    stack: list[list] = []
    root = None
    for tok in _tokens(text):
        if tok is _OPEN:
            stack.append([])
        elif tok is _CLOSE:
            node = stack.pop()
            if stack:
                stack[-1].append(node)
            else:
                root = node
                break
        else:
            if not stack:
                raise ValueError("atom outside list")
            stack[-1].append(tok)
    if root is None:
        raise ValueError("no complete expression found")
    return root


def load(path) -> Node:
    with open(path, encoding="utf-8") as f:
        return loads(f.read())


# -------------------------------------------------------------------------- write

def fmt_num(v: float) -> str:
    """Format a number the way KiCad does: no exponent, trailing zeros removed."""
    if isinstance(v, bool):
        raise TypeError("bool is not a number here")
    if isinstance(v, int):
        return str(v)
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"cannot write {v}")
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _atom(a) -> str:
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, str):
        esc = a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{esc}"'
    if isinstance(a, (int, float)):
        return fmt_num(a)
    raise TypeError(f"unsupported atom {a!r}")


# Nodes that KiCad writes on one line; keeps generated files compact and diffable.
_INLINE = {
    "at", "xy", "size", "start", "end", "mid", "center", "pts", "layers", "net",
    "uuid", "width", "type", "stroke", "fill", "font", "justify", "effects",
    "offset", "length", "name", "number", "color", "drill", "rect_delta",
    "roundrect_rratio", "thickness", "layer", "version", "generator",
    "generator_version", "paper", "lib_id", "unit", "in_bom", "on_board", "dnp",
    "exclude_from_sim", "fields_autoplaced", "property_hide", "hide", "tstamp",
    "clearance", "min_thickness", "filled_areas_thickness", "connect_pads",
    "thermal_gap", "thermal_bridge_width", "path", "reference", "value",
    "footprint", "page", "radius", "angle", "solder_mask_margin",
    "solder_paste_margin", "zone_connect", "pintype", "pinfunction", "remove_unused_layers",
    "keep_end_layers", "die_length", "teardrops", "embedded_fonts", "autoplace",
    "via_dielectric", "min_width", "island_removal_mode", "island_area_min",
}


def dumps(node: Node, indent: int = 0) -> str:
    """Serialise a node with KiCad-style indentation (tabs)."""
    out: list[str] = []
    _dump(node, indent, out)
    return "".join(out)


def _is_simple(node: Node) -> bool:
    return all(not isinstance(x, list) for x in node)


def _dump(node: Node, indent: int, out: list[str]) -> None:
    head = node[0] if node and isinstance(node[0], str) else ""
    pad = "\t" * indent
    if _is_simple(node) or head in _INLINE:
        out.append(pad + _inline(node))
        return
    # head plus leading atoms on the first line, child lists below
    first = [x for x in node if not isinstance(x, list)]
    out.append(pad + "(" + " ".join(_atom(a) for a in first))
    for child in node:
        if isinstance(child, list):
            out.append("\n")
            _dump(child, indent + 1, out)
    out.append("\n" + pad + ")")


def _inline(node: Node) -> str:
    parts = []
    for x in node:
        parts.append(_inline(x) if isinstance(x, list) else _atom(x))
    return "(" + " ".join(parts) + ")"


def dump(node: Node, path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(node))
        f.write("\n")


# ------------------------------------------------------------------------ helpers

def head(node) -> str | None:
    if isinstance(node, list) and node and isinstance(node[0], str):
        return str(node[0])
    return None


def children(node: Node, name: str) -> list[Node]:
    return [c for c in node if isinstance(c, list) and head(c) == name]


def child(node: Node, name: str) -> Node | None:
    for c in node:
        if isinstance(c, list) and head(c) == name:
            return c
    return None


def walk(node: Node) -> Iterable[Node]:
    """Depth-first iteration over every list node."""
    yield node
    for c in node:
        if isinstance(c, list):
            yield from walk(c)


def num(a) -> float:
    return float(a)


def S(*items) -> Node:
    """Build a node; the first item becomes a bare head symbol."""
    if not items:
        return []
    h, *rest = items
    return [Sym(h) if isinstance(h, str) and not isinstance(h, Sym) else h, *rest]
