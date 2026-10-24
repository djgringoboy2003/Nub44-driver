"""Custom footprint compatibility and failure handling for schematic generation."""
import copy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
sys.path.insert(0, str(ROOT / "automation/schematic"))
sys.path.insert(0, str(ROOT / "automation/setup"))

import build_library  # noqa: E402
import build_schematic  # noqa: E402
from nubm44 import kicad_lib, spec as spec_mod  # noqa: E402
from nubm44.schematic import Schematic  # noqa: E402
from nubm44.sexpr import child, children  # noqa: E402


def filters(symbol):
    return next(str(p[2]) for p in children(symbol, "property")
                if p[1] == "ki_fp_filters")


@pytest.fixture(scope="module")
def project_symbols():
    try:
        symbols = build_library.footprint_symbols()
    except FileNotFoundError:
        pytest.skip("KiCad source symbol libraries are required")
    return {str(symbol[1]): symbol for symbol in symbols}


def test_native_project_symbols_keep_pin_maps_and_inherited_filter_options(project_symbols):
    for name, base_id in build_library.FOOTPRINT_SYMBOL_BASES.items():
        base = kicad_lib.get_symbol(base_id)
        derived = project_symbols[name]
        assert child(derived, "extends") is None
        assert kicad_lib.symbol_pins(derived) == kicad_lib.symbol_pins(base)
        assert set(filters(base).split()) <= set(filters(derived).split())
        assert all(str(unit[1]).startswith(name + "_") for unit in children(derived, "symbol"))


def test_native_filters_include_exact_authoritative_footprints_for_both_variants(project_symbols):
    used = set()
    for variant in spec_mod.VARIANTS:
        for part in spec_mod.parts_for(variant):
            name = part["lib"].removeprefix("nubm44:")
            if name in project_symbols:
                assert part["footprint"] in filters(project_symbols[name]).split(), (variant, part["ref"])
                used.add(name)
    assert used == set(build_library.FOOTPRINT_SYMBOL_BASES)


def test_schematic_embedding_does_not_modify_project_library_symbol(project_symbols, monkeypatch):
    lib_id = "nubm44:Battery_Contact"
    source = copy.deepcopy(project_symbols["Battery_Contact"])
    source[1] = lib_id  # get_symbol supplies a library-qualified root name.
    monkeypatch.setattr(kicad_lib, "get_symbol", lambda _: copy.deepcopy(source))
    sch = Schematic("fixture", "Filter fixture")
    for part in spec_mod.parts_for("compact-22mm"):
        if part["lib"] == lib_id:
            sch.place(part["ref"], lib_id, 0, 0, value=str(part["value"]), footprint=part["footprint"])
    assert sch.lib_symbols[lib_id] == source


def test_project_connector_and_testpoint_ground_pins_keep_net_labels(project_symbols, monkeypatch):
    original_get_symbol = kicad_lib.get_symbol

    def get_symbol(lib_id):
        name = lib_id.removeprefix("nubm44:")
        if name not in project_symbols:
            return original_get_symbol(lib_id)
        sym = copy.deepcopy(project_symbols[name])
        sym[1] = lib_id
        return sym

    monkeypatch.setattr(kicad_lib, "get_symbol", get_symbol)
    sch = Schematic("fixture", "External pad labels")
    parts = [p for p in spec_mod.parts_for("compact-22mm") if p["ref"] in ("J2", "J3", "TP8")]
    for i, part in enumerate(parts):
        build_schematic._place(sch, part, 30.48 + i * 30.48, 30.48, 0, {})
    assert sch._pwr == 0
    assert sum(str(label[1]) == "GND" for label in sch.items if label[0] == "label") == 3


@pytest.mark.parametrize("failed_stage", ["upgrade", "erc", "export"])
def test_cli_failure_cannot_reuse_previous_passing_evidence(monkeypatch, tmp_path, failed_stage):
    reports = tmp_path / "reports"
    reports.mkdir()
    sch_path = tmp_path / "driver.kicad_sch"
    sch_path.write_text("fixture", encoding="utf-8")
    artifacts = [reports / "erc-compact-22mm.json", reports / "schematic-compact-22mm.json",
                 sch_path.with_suffix(".net")]
    for artifact in artifacts:
        artifact.write_text('{"status":"PASS"}', encoding="utf-8")
    monkeypatch.setattr(build_schematic.paths, "REPORTS", reports)
    monkeypatch.setattr(build_schematic.paths, "kicad_cli", lambda: Path("fixture-cli"))
    calls = []

    def run(args, **kwargs):
        assert kwargs.get("check") is True
        stage = args[2]
        calls.append(stage)
        if stage == failed_stage:
            raise subprocess.CalledProcessError(7, args, output="fixture failure")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(build_schematic.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        build_schematic.verify("compact-22mm", {}, sch_path)
    assert calls[-1] == failed_stage
    assert all(not artifact.exists() for artifact in artifacts)
