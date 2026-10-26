"""Sourcing checks: MPN decoding, voltage/power derating and stale sourcing records."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sc():
    spec = importlib.util.spec_from_file_location("check_sourcing_under_test", ROOT / "sourcing/check_sourcing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mpn, expected", [
    ("GRM033R61A104KE15D", {"size": "0201", "dielectric": "X5R", "volts": 10}),
    ("GRM1555C1H681JA01D", {"size": "0402", "dielectric": "C0G", "volts": 50}),
    ("CL21A226MOQNNNE", {"size": "0805", "dielectric": "X5R", "volts": 16}),
    ("CL05B104KO5NNNC", {"size": "0402", "dielectric": "X7R", "volts": 16}),
    ("CL10A106KP8NNNC", {"size": "0603", "dielectric": "X5R", "volts": 10}),
    ("RC0201FR-07100KL", {"size": "0201"}),
])
def test_mpn_decoding(sc, mpn, expected):
    assert sc.decode(mpn) == expected


def test_voltage_across_parts(sc):
    assert sc.across({1: "VOUT", 2: "GND"})[1] == sc.V_OUT_FAULT
    assert sc.across({1: "BOOT1", 2: "SW1"})[0] == sc.V_VCC
    normal, fault, _ = sc.across({1: "IND_OUT", 2: "IND_PAD"})
    assert normal == 0 and fault == sc.V_BAT
    assert sc.ohms("4.7k") == 4700 and sc.ohms("10m") == 0.01 and sc.ohms("220") == 220


def test_repository_sourcing_has_no_fail_findings(sc):
    result = sc.check()
    assert result["status"] == "PASS", [f for f in result["findings"] if f["severity"] == "FAIL"]
    assert any(f["check"] == "description" for f in result["findings"]), "AUD-MFG-03 mismatch must stay visible"


def test_stale_components_csv_is_a_failure(sc, monkeypatch, tmp_path):
    stale = tmp_path / "components.csv"
    stale.write_text((ROOT / "sourcing/components.csv").read_text(encoding="utf-8").replace("Yageo", "Other", 1),
                     encoding="utf-8")
    monkeypatch.setattr(sc, "OUT", tmp_path)
    result = sc.check()
    assert any(f["check"] == "stale" and f["severity"] == "FAIL" for f in result["findings"])


def test_undersized_capacitor_rating_fails(sc, monkeypatch):
    parts = [{"ref": "C99", "mpn": "GRM033R60J104KE19D", "mfr": "Murata", "footprint": "Capacitor_SMD:C_0201_0603Metric",
              "desc": "test", "value": "100n", "pins": {1: "VOUT", 2: "GND"}}]
    monkeypatch.setattr(sc.spec, "parts_for", lambda variant: parts)
    result = sc.check()
    assert any(f["ref"].endswith(":C99") and f["check"] == "capacitor voltage" and f["severity"] == "FAIL"
               for f in result["findings"])
