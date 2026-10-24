"""The connectivity checker must flag real wiring faults (guards against a checker that always passes)."""
import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import netlist  # noqa: E402

SPEC = ROOT / "engineering/design/connectivity.yaml"
NET = ROOT / "hardware/compact-22mm/nubm44_driver.net"


@pytest.fixture(scope="module")
def data():
    if not NET.exists():
        pytest.skip("netlist not generated yet (run automation/schematic/build_schematic.py)")
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    actual = netlist.read_kicad_netlist(NET)
    nets = {k.lstrip("/"): v for k, v in actual["nets"].items()}
    return spec, nets


def test_generated_schematic_matches_spec(data):
    spec, nets = data
    assert netlist.compare(netlist.nets_from_spec(spec["parts"]), nets) == []


@pytest.mark.parametrize("ref,pin,net", [("U1", 13, "VOUT"), ("U2", 4, "LD_P"), ("Q2", 5, "SW1"), ("D1", 1, "GND")])
def test_single_pin_fault_is_detected(data, ref, pin, net):
    spec, nets = data
    bad = copy.deepcopy(spec)
    for p in bad["parts"]:
        if p["ref"] == ref:
            p["pins"][pin] = net
    assert netlist.compare(netlist.nets_from_spec(bad["parts"]), nets), f"{ref}.{pin} fault not detected"


def test_swapped_gate_drain_is_detected(data):
    spec, nets = data
    bad = copy.deepcopy(spec)
    for p in bad["parts"]:
        if p["ref"] == "Q1":
            p["pins"][4], p["pins"][5] = p["pins"][5], p["pins"][4]
    assert netlist.compare(netlist.nets_from_spec(bad["parts"]), nets)
