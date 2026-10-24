"""Netlist extraction and comparison.

``read_kicad_netlist`` parses the ``kicadsexpr`` netlist written by
``kicad-cli sch export netlist``. ``compare`` checks it against the design
specification's intended connectivity, pin by pin.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .sexpr import child, children, load

Pin = tuple[str, str]  # (reference, pin number)


def read_kicad_netlist(path: Path) -> dict:
    root = load(path)
    comps = {}
    for comp in children(child(root, "components"), "comp"):
        ref = str(child(comp, "ref")[1])
        val = child(comp, "value")
        fp = child(comp, "footprint")
        fields = {}
        f_node = child(comp, "fields")
        if f_node:
            for fld in children(f_node, "field"):
                name = child(fld, "name")
                fields[str(name[1])] = str(fld[-1]) if len(fld) > 2 else ""
        comps[ref] = {
            "value": str(val[1]) if val else "",
            "footprint": str(fp[1]) if fp else "",
            "fields": fields,
        }
    nets: dict[str, set[Pin]] = {}
    for net in children(child(root, "nets"), "net"):
        name = str(child(net, "name")[1])
        pins = set()
        for node in children(net, "node"):
            pins.add((str(child(node, "ref")[1]), str(child(node, "pin")[1])))
        nets[name] = pins
    return {"components": comps, "nets": nets}


def pin_to_net(nets: dict[str, set[Pin]]) -> dict[Pin, str]:
    out = {}
    for name, pins in nets.items():
        for p in pins:
            out[p] = name
    return out


def is_unconnected_name(name: str) -> bool:
    return name.startswith("unconnected-") or name.startswith("Net-(")


def compare(intended: dict[str, set[Pin]], actual: dict[str, set[Pin]],
            ignore_refs: set[str] = frozenset()) -> list[str]:
    """Return human-readable differences (empty list means identical connectivity).

    ``intended`` nets with a single pin are treated as "must be unconnected"
    (KiCad gives such pins an auto-generated ``unconnected-`` net).
    """
    problems: list[str] = []
    a_map = pin_to_net(actual)
    i_map = pin_to_net(intended)

    for pin in sorted(set(i_map) | set(a_map)):
        if pin[0] in ignore_refs:
            continue
        if pin not in a_map:
            problems.append(f"{pin[0]}.{pin[1]}: in spec (net {i_map[pin]}) but missing from schematic")
        elif pin not in i_map:
            problems.append(f"{pin[0]}.{pin[1]}: in schematic (net {a_map[pin]}) but not in spec")

    for name, pins in sorted(intended.items()):
        pins = {p for p in pins if p[0] not in ignore_refs}
        if not pins:
            continue
        nets_seen = {a_map.get(p) for p in pins}
        if len(pins) == 1:
            (p,) = pins
            got = a_map.get(p)
            if got is not None and not is_unconnected_name(got) and len(actual[got]) > 1:
                problems.append(f"net {name}: {p[0]}.{p[1]} should be alone but shares {got}")
            continue
        if len(nets_seen) != 1 or None in nets_seen:
            problems.append(f"net {name}: pins split across schematic nets {sorted(map(str, nets_seen))}")
            continue
        got = nets_seen.pop()
        extra = {p for p in actual[got] if p[0] not in ignore_refs} - pins
        if extra:
            problems.append(f"net {name}: schematic net {got} has extra pins {sorted(extra)}")
        if got != name and not is_unconnected_name(got):
            problems.append(f"net {name}: named '{got}' in the schematic")
    return problems


def nets_from_spec(parts: list[dict]) -> dict[str, set[Pin]]:
    nets: dict[str, set[Pin]] = defaultdict(set)
    for part in parts:
        for pin, net in part.get("pins", {}).items():
            if net in (None, "NC"):
                nets[f"__nc__{part['ref']}.{pin}"].add((part["ref"], str(pin)))
            else:
                nets[net].add((part["ref"], str(pin)))
    return dict(nets)
