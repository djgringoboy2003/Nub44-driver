"""Manufacturing export checks must detect wrong parts, coordinates and missing outputs."""
import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def exporter(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "automation/export/export_pcbway.py"
    spec = importlib.util.spec_from_file_location("export_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.paths, "HARDWARE", tmp_path / "hardware")
    monkeypatch.setattr(module.paths, "MANUFACTURING", tmp_path / "manufacturing")
    monkeypatch.setattr(module.paths, "kicad_python", lambda: "test-kicad-python")
    board = tmp_path / "hardware/compact-22mm/nubm44_driver.kicad_pcb"
    board.parent.mkdir(parents=True)
    board.write_text('''(kicad_pcb (setup (aux_axis_origin 100 100))
      (footprint "Resistor:R0402" (layer "F.Cu") (at 98 97 90)
        (property "Reference" "R1") (property "Value" "10k")
        (property "MPN" "PART-R") (property "Manufacturer" "Maker") (attr smd) (pad "1" smd rect))
      (footprint "Resistor:R0402" (layer "F.Cu") (at 101 102)
        (property "Reference" "R2") (property "Value" "10k")
        (property "MPN" "PART-R") (property "Manufacturer" "Maker") (attr smd) (pad "1" smd rect))
      (footprint "Package:QFN" (layer "B.Cu") (at 104 105 270)
        (property "Reference" "U1") (property "Value" "Controller")
        (property "MPN" "PART-U") (property "Manufacturer" "Maker") (attr smd) (pad "1" smd rect))
      (footprint "Custom:Spring" (layer "B.Cu") (at 100 100)
        (property "Reference" "J1") (property "Value" "Spring")
        (attr smd dnp exclude_from_pos_files) (pad "1" smd circle))
      (footprint "Custom:TestPad" (layer "F.Cu") (at 106 106)
        (property "Reference" "TP1") (property "Value" "GND")
        (attr smd exclude_from_bom exclude_from_pos_files) (pad "1" smd circle)))''', encoding="utf-8")
    board.with_suffix(".kicad_sch").write_text("schematic", encoding="utf-8")
    board.with_suffix(".kicad_pro").write_text("{}", encoding="utf-8")
    note = tmp_path / "documentation/stack-up.md"
    note.parent.mkdir(parents=True)
    note.write_text("Four layers, 1.6 mm nominal; review note.", encoding="utf-8")
    for relative in ("hardware/compact-22mm/placement.yaml", "engineering/design/connectivity.yaml",
                     "engineering/design/parameters.yaml"):
        source = tmp_path / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("source: fixture", encoding="utf-8")
    tool = tmp_path / "tools/ibom/InteractiveHtmlBom/generate_interactive_bom.py"
    tool.parent.mkdir(parents=True)
    tool.write_text("# mocked tool", encoding="utf-8")
    return module, board


def native_positions(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
        writer.writerows([("R1", "10k", "R0402", -2, 3, 90, "top"),
                          ("R2", "10k", "R0402", 1, -2, 0, "top"),
                          ("U1", "Controller", "QFN", 4, -5, -90, "bottom")])


def assembly_fixture(module, board):
    out = module.ROOT / "assembly-check"
    (out / "assembly").mkdir(parents=True)
    (out / "reports").mkdir()
    fps, origin = module.board_footprints(board)
    module.write_assembly(out, fps, origin)
    native_positions(out / "reports/kicad_pos.csv")
    return out


def mutate_csv(path, action):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns, rows = reader.fieldnames, list(reader)
    action(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fake_tools(module, monkeypatch, failure=None, change_source=None):
    calls = []

    def fake_cli(*args):
        calls.append(tuple(map(str, args)))
        if failure and failure in args:
            raise RuntimeError(f"injected {failure} failure")
        output = Path(args[args.index("-o") + 1])
        if args[:3] == ("pcb", "export", "gerbers"):
            for layer, ext in module.GERBER_EXTENSIONS.items():
                (output / f"nubm44_driver-{layer.replace('.', '_')}.{ext}").write_text("gerber", encoding="utf-8")
        elif args[:3] == ("pcb", "export", "drill"):
            for kind in ("PTH", "NPTH"):
                for suffix in (".drl", "-drl_map.pdf"):
                    (output / f"nubm44_driver-{kind}{suffix}").write_text("drill", encoding="utf-8")
        elif args[:3] == ("pcb", "export", "pos"):
            native_positions(output)
        else:
            output.write_text("generated drawing", encoding="utf-8")
        if change_source and "render" in args:
            change_source.write_text(change_source.read_text(encoding="utf-8") + " ", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_subprocess(args, **kwargs):
        out = Path(args[args.index("--dest-dir") + 1])
        (out / "ibom.html").write_text("<html>interactive BOM</html>", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module, "cli", fake_cli)
    monkeypatch.setattr(module.subprocess, "run", fake_subprocess)
    return calls


def test_assembly_rechecks_written_files_against_board(exporter):
    module, board = exporter
    assert module.check_assembly(assembly_fixture(module, board), board) == []


@pytest.mark.parametrize("column,value", [("pos_x", "-4"), ("pos_y", "5"),
                                          ("rotation", "90"), ("side", "top"), ("pos_x", "nan")])
def test_bottom_centroid_sign_side_and_rotation_errors_are_detected(exporter, column, value):
    module, board = exporter
    out = assembly_fixture(module, board)
    mutate_csv(out / "assembly/CPL_PCBWay.csv",
               lambda rows: next(r for r in rows if r["designator"] == "U1").update({column: value}))
    assert any(column in problem for problem in module.check_assembly(out, board))


def test_native_export_bottom_mirroring_is_not_hidden_by_absolute_value(exporter):
    module, board = exporter
    out = assembly_fixture(module, board)
    mutate_csv(out / "reports/kicad_pos.csv",
               lambda rows: next(r for r in rows if r["Ref"] == "U1").update(PosX="-4"))
    assert any("kicad_pos.csv: U1 PosX" in problem for problem in module.check_assembly(out, board))


@pytest.mark.parametrize("filename,ref_column,qty_column", [
    ("BOM_PCBWay_template.csv", "*Designator", "*Qty"),
    ("BOM_PCBWay_plugin.csv", "Designator", "Quantity")])
def test_bom_duplicate_designators_and_wrong_quantities_fail(exporter, filename, ref_column, qty_column):
    module, board = exporter
    out = assembly_fixture(module, board)
    mutate_csv(out / "assembly" / filename,
               lambda rows: next(r for r in rows if "R1" in r[ref_column]).update({ref_column: "R1,R1", qty_column: "9"}))
    problems = module.check_assembly(out, board)
    assert any("duplicate designators" in p for p in problems)
    assert any("quantity differs" in p for p in problems)
    assert any("missing ['R2']" in p for p in problems)


def test_missing_centroid_and_duplicate_native_rows_fail(exporter):
    module, board = exporter
    out = assembly_fixture(module, board)
    mutate_csv(out / "assembly/CPL_PCBWay.csv", lambda rows: rows.pop())
    mutate_csv(out / "reports/kicad_pos.csv", lambda rows: rows.append(dict(rows[0])))
    problems = module.check_assembly(out, board)
    assert any("CPL_PCBWay.csv: designator counts differ" in p for p in problems)
    assert any("kicad_pos.csv: duplicate designators" in p for p in problems)


def test_matching_gerber_count_cannot_hide_missing_layer(exporter):
    module, _ = exporter
    out = module.ROOT / "complete"
    for rel in module.required_files("compact-22mm"):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("output", encoding="utf-8")
    copper = out / "gerbers/nubm44_driver-In1_Cu.g1"
    copper.rename(copper.with_name("unrelated.gbr"))
    assert any("In1_Cu.g1" in p for p in module.output_problems(out, "compact-22mm"))


def test_failed_export_keeps_prior_package_and_reviewable_draft(exporter, monkeypatch):
    module, _ = exporter
    calls = fake_tools(module, monkeypatch, failure="render")
    old = module.paths.MANUFACTURING / "pcbway/compact-22mm/previous.txt"
    old.parent.mkdir(parents=True)
    old.write_text("previous package", encoding="utf-8")
    result = module.export("compact-22mm")
    assert result["status"] == "FAIL" and old.read_text(encoding="utf-8") == "previous package"
    report = module.ROOT / result["output_directory"] / "reports/export-check.json"
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "FAIL"
    assert any("render" in arg for call in calls for arg in call)


def test_missing_ibom_tool_cannot_produce_passing_package(exporter, monkeypatch):
    module, _ = exporter
    fake_tools(module, monkeypatch)
    (module.ROOT / "tools/ibom/InteractiveHtmlBom/generate_interactive_bom.py").unlink()
    result = module.export("compact-22mm")
    assert result["status"] == "FAIL"
    assert any("InteractiveHtmlBom is required" in p for p in result["problems"])


def test_success_exit_without_required_render_fails_completeness(exporter, monkeypatch):
    module, _ = exporter
    fake_tools(module, monkeypatch)
    original = module.cli

    def skip_one_render(*args):
        if any(str(a).endswith("render_bottom.png") for a in args):
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return original(*args)

    monkeypatch.setattr(module, "cli", skip_one_render)
    result = module.export("compact-22mm")
    assert result["status"] == "FAIL"
    assert any("missing or empty required output: drawings/render_bottom.png" in p for p in result["problems"])


def test_ibom_nonzero_exit_fails_export(exporter, monkeypatch):
    module, _ = exporter
    fake_tools(module, monkeypatch)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=1, stdout="", stderr="injected iBOM error"))
    result = module.export("compact-22mm")
    assert result["status"] == "FAIL"
    assert any("InteractiveHtmlBom failed" in p for p in result["problems"])


def test_complete_export_promotes_checked_files_and_hash_manifest(exporter, monkeypatch):
    module, _ = exporter
    calls = fake_tools(module, monkeypatch)
    result = module.export("compact-22mm")
    assert result["status"] == "PASS", result["problems"]
    assert result["release_status"] == "DRAFT_REVIEW" and result["manufacturing_release"] is False
    package = module.ROOT / result["output_directory"]
    assert "not been released for manufacturing" in (package / "REVIEW_ONLY.md").read_text(encoding="utf-8")
    assert result["bom_parts"] == 4 and result["cpl_parts"] == 3
    assert (package / "drawings/stack-up.md").read_bytes() == (module.ROOT / "documentation/stack-up.md").read_bytes()
    assert result["inputs"]["documentation/stack-up.md"] == module.sha256(module.ROOT / "documentation/stack-up.md")
    assert len(result["inputs"]) == 7
    assert all(module.sha256(package / rel) == digest for rel, digest in result["file_sha256"].items())
    assert not list(package.parent.glob(".*-staging-*"))
    assert any("--use-drill-file-origin" in call for call in calls if "gerbers" in call)
    assert any("--drill-origin" in call and "plot" in call for call in calls if "drill" in call)
    assert any("--rotate" in call and "325,0,30" in call for call in calls)
    assert all(call[call.index("--quality") + 1] == "basic" for call in calls if "render" in call)


@pytest.mark.parametrize("source", ["board", "stack-up", "placement", "connectivity", "parameters"])
def test_source_change_during_export_fails_and_prevents_promotion(exporter, monkeypatch, source):
    module, board = exporter
    changed = {"board": board, "stack-up": module.ROOT / "documentation/stack-up.md",
               "placement": board.parent / "placement.yaml",
               "connectivity": module.ROOT / "engineering/design/connectivity.yaml",
               "parameters": module.ROOT / "engineering/design/parameters.yaml"}[source]
    fake_tools(module, monkeypatch, change_source=changed)
    result = module.export("compact-22mm")
    assert result["status"] == "FAIL"
    assert any("CAD input changed during export" in p for p in result["problems"])
    assert not (module.paths.MANUFACTURING / "pcbway/compact-22mm").exists()


def test_promotion_restores_previous_package_if_rename_fails(exporter, monkeypatch):
    module, _ = exporter
    parent = module.ROOT / "promotion"
    staged, destination = parent / ".staged", parent / "compact-22mm"
    staged.mkdir(parents=True)
    destination.mkdir()
    (destination / "old.txt").write_text("old", encoding="utf-8")
    original = Path.replace

    def fail_staging_rename(self, target):
        if self == staged:
            raise OSError("injected rename failure")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", fail_staging_rename)
    with pytest.raises(OSError, match="injected"):
        module.promote(staged, destination)
    assert (destination / "old.txt").read_text(encoding="utf-8") == "old"
