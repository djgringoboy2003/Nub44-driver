"""JLCPCB upload files are derived exactly from the verified PCBWay package; the footprint review pack is complete."""
import csv
import importlib.util
import shutil
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workspace(tmp_path):
    for rel in ("manufacturing/pcbway/evaluation-board", "manufacturing/pcbway/compact-22mm"):
        shutil.copytree(ROOT / rel, tmp_path / rel)
    (tmp_path / "sourcing").mkdir()
    shutil.copyfile(ROOT / "sourcing/components.csv", tmp_path / "sourcing/components.csv")
    return tmp_path


def rows(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_jlcpcb_files_match_the_pcbway_package(workspace):
    jlc = load("automation/export/export_jlcpcb.py", "jlc_ok")
    r = jlc.build("evaluation-board", workspace)
    assert r["status"] == "PASS", r["problems"]
    out = workspace / "manufacturing/jlcpcb/evaluation-board"
    pkg = workspace / "manufacturing/pcbway/evaluation-board"
    with zipfile.ZipFile(out / "evaluation-board-jlcpcb-gerbers.zip") as z:
        names = set(z.namelist())
        assert all("/" not in n for n in names), "flat ZIP"
        assert not any(n.endswith((".pdf", ".gbrjob")) for n in names)
        for g in (pkg / "gerbers").glob("*.g*"):
            if g.suffix != ".gbrjob":
                assert z.read(g.name) == g.read_bytes(), "Gerber bytes identical to the PCBWay package"
    pcb = {r["designator"]: r for r in rows(pkg / "assembly/CPL_PCBWay.csv")}
    for c in rows(out / "CPL_JLCPCB.csv"):
        assert (c["Mid X"], c["Mid Y"]) == (pcb[c["Designator"]]["pos_x"], pcb[c["Designator"]]["pos_y"])
        assert 0 <= float(c["Rotation"]) < 360 and c["Layer"] == "Top"
    bom_refs = sorted(x for b in rows(out / "BOM_JLCPCB.csv") for x in b["Designator"].split(","))
    assert bom_refs == sorted(pcb) and "J1" not in bom_refs
    assert jlc.check_problems("evaluation-board", workspace) == []


def test_changed_pcbway_package_makes_jlcpcb_files_stale(workspace):
    jlc = load("automation/export/export_jlcpcb.py", "jlc_stale")
    assert jlc.build("evaluation-board", workspace)["status"] == "PASS"
    cpl = workspace / "manufacturing/pcbway/evaluation-board/assembly/CPL_PCBWay.csv"
    cpl.write_text(cpl.read_text(encoding="utf-8-sig").replace("-10.5000", "-10.6000", 1), encoding="utf-8")
    assert any("stale" in p for p in jlc.check_problems("evaluation-board", workspace))
    assert jlc.build("evaluation-board", workspace)["status"] == "FAIL", "a modified source package is refused"


def test_incomplete_board_gets_no_jlcpcb_files(workspace):
    jlc = load("automation/export/export_jlcpcb.py", "jlc_incomplete")
    r = jlc.build("compact-22mm", workspace)
    assert r["status"] == "FAIL" and any("not complete" in p for p in r["problems"])
    assert not (workspace / "manufacturing/jlcpcb/compact-22mm").exists()


def test_footprint_review_pack_covers_every_prototype_review():
    import yaml
    page = load("automation/review/footprint_report.py", "fp_report").build()
    reviews = yaml.safe_load((ROOT / "engineering/release/design-reviews.yaml").read_text(encoding="utf-8"))["reviews"]
    for r in reviews:
        if r["level"] == "PROTOTYPE_CANDIDATE":
            assert f"## {r['id']}:" in page, r["id"]
    assert "| 25 | smd |" in page and "SW2" in page
    assert "custom polygon, extent" in page, "custom pads report their real outline, not the anchor"
