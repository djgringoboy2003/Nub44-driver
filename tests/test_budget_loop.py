"""Check the preliminary model's sensitivity, margin handling and tool failures."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location("budget_loop", ROOT / "automation/budget/loop_model.py")
loop = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(loop)


@pytest.fixture
def params():
    return yaml.safe_load(loop.PARAMETERS.read_text(encoding="utf-8"))


def test_assumed_sensitivity_corners_meet_only_model_criteria(params):
    r = loop.sweep(params)
    assert r["case_count"] == 243
    assert r["screen_pass_count"] == 243
    assert r["minimum_phase_margin_deg"] >= params["loop"]["minimum_phase_margin_deg"]
    assert r["minimum_gain_margin_db"] >= params["loop"]["minimum_gain_margin_db"]
    assert "ASSUM" in r["qualification"].upper() or "assumed" in r["qualification"]


def test_excess_compensation_gain_reveals_failed_corners(params):
    p = copy.deepcopy(params)
    p["loop"]["compensation_r_ohm"] = 330
    r = loop.sweep(p)
    assert r["screen_pass_count"] < r["case_count"]
    assert r["minimum_gain_margin_db"] < p["loop"]["minimum_gain_margin_db"]


def test_no_crossing_is_not_infinite_margin_or_pass():
    f = np.geomspace(1, 1e6, 1000)
    r = loop.margins(f, np.full(len(f), 0.1 + 0j))
    assert r["phase_margin_deg"] is None
    assert r["gain_margin_db"] is None
    assert not r["unity_crossings_hz"]


def test_known_three_pole_response_margin():
    # L = 8 / (1+j*f/1000)^3: |L|=1 at sqrt(3)*1000,
    # phase -180 deg there, so both margins are zero.
    f = np.geomspace(1, 1e7, 10000)
    response = 8 / (1 + 1j * f / 1000) ** 3
    r = loop.margins(f, response)
    assert r["unity_crossings_hz"][0] == pytest.approx(np.sqrt(3) * 1000, rel=1e-5)
    assert r["phase_margin_deg"] == pytest.approx(0, abs=0.001)
    assert r["gain_margin_db"] == pytest.approx(0, abs=0.001)


@pytest.mark.parametrize("f,h", [([0, 1, 2], [1, 1, 1]), ([1, 1, 2], [1, 1, 1]),
                                  ([1, 2, 3], [1, np.nan, 1]), ([1, 2, 3], [1, 0, 1]),
                                  ([1, 2], [1, 1])])
def test_bad_frequency_data_rejected(f, h):
    with pytest.raises(ValueError):
        loop.margins(f, h)


def test_sensor_delay_changes_phase_and_cannot_be_omitted(params):
    f = np.array([10000.0])
    fast = loop.transfer(params, f, cout=100e-6, rd=0.2, sensor_hz=60000)
    slow = loop.transfer(params, f, cout=100e-6, rd=0.2, sensor_hz=20000)
    assert np.angle(slow)[0] < np.angle(fast)[0]
    assert np.abs(slow)[0] < np.abs(fast)[0]


def test_failed_ngspice_cannot_reuse_previous_raw_pass(tmp_path, monkeypatch, params):
    raw = tmp_path / "loop-ac.txt"
    raw.write_text("old passing data", encoding="utf-8")
    monkeypatch.setattr(loop, "OUT", tmp_path)
    monkeypatch.setattr(loop.paths, "ngspice", lambda: Path("ngspice-not-run"))
    monkeypatch.setattr(loop.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="ngspice failed"):
        loop.run_ngspice(params)
    assert not raw.exists()


def test_netlist_is_parameter_derived_not_a_saved_passing_result(params):
    p = copy.deepcopy(params)
    p["loop"]["compensation_r_ohm"] = 123
    net = loop.ngspice_netlist(p)
    assert "RCOMP COMP CZ 123" in net
    assert "GEA 0 COMP EXC 0" in net
    assert "GMOD 0 OUT CMD_F 0" in net
    assert "ac dec" in net
