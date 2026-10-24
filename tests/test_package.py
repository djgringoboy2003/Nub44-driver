"""Review archives include editable evidence and expose missing data without release claims."""
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def packager(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "automation/export/package_project.py"
    spec = importlib.util.spec_from_file_location("package_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "git_state", lambda root: {"commit": "UNKNOWN", "working_tree": "UNKNOWN"})
    root = tmp_path / "project"
    root.mkdir()
    return module, root


def write(root, relative, data="source"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def unpack_manifest(path):
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("review-bundle-manifest.json")), archive.namelist()


def test_includes_root_docs_configs_source_cad_and_evidence(packager):
    module, root = packager
    expected = ["README.md", "AGENTS.md", "PROGRESS.md", "requirements.txt", "pyproject.toml", ".gitignore",
                "engineering/design/parameters.yaml", "engineering/design/connectivity.yaml",
                "automation/nubm44/spec.py", "scripts/package.ps1", "tests/test_core.py",
                "hardware/compact-22mm/nubm44_driver.kicad_pcb", "hardware/compact-22mm/placement.yaml",
                "reports/drc-compact-22mm.json", "research/sources/manufacturing-sources.md",
                "documentation/testing/test-plan.md", "simulation/results/results.json",
                "manufacturing/pcbway/compact-22mm/compact-22mm-gerbers.zip"]
    for relative in expected:
        write(root, relative)
    result = module.build_package(root)
    manifest, names = unpack_manifest(result)
    assert set(expected).issubset(names)
    assert set(manifest["files"]) == set(expected)


def test_excludes_downloads_tools_cache_vcs_scratch_and_failed_exports(packager):
    module, root = packager
    write(root, "README.md")
    excluded = ["tools/compiler/bin/compiler.exe", ".venv/pyvenv.cfg", ".git/config", "build/result.json",
                "dist/old.zip", "research/datasheets/vendor.pdf", "research/downloads/source.txt",
                "research/vendor.pdf", "research/archive.tgz", "firmware/build/main.hex",
                "automation/__pycache__/spec.pyc", "tests/.pytest_cache/results.json",
                "hardware/compact-22mm/nubm44_driver.kicad_prl", "hardware/compact-22mm/~board.lck",
                "hardware/compact-22mm/nubm44-backups/board.kicad_pcb",
                "manufacturing/pcbway/.compact-22mm-staging-abc/assembly/CPL.csv",
                "manufacturing/pcbway/failed/board.zip", "sourcing/source-download.zip", ".env"]
    for relative in excluded:
        write(root, relative)
    _, names = unpack_manifest(module.build_package(root))
    assert not set(excluded).intersection(names)
    assert set(names) == {"README.md", "review-bundle-manifest.json", "REVIEW_BUNDLE.md"}


def test_embedded_inventory_hashes_match_exact_archived_bytes(packager):
    module, root = packager
    write(root, "README.md", "contents with unicode: \u03a9\n")
    write(root, "engineering/design/parameters.yaml", "current: 4.0\n")
    result = module.build_package(root)
    manifest, _ = unpack_manifest(result)
    with zipfile.ZipFile(result) as archive:
        for rel, info in manifest["files"].items():
            raw = archive.read(rel)
            assert len(raw) == info["bytes"]
            assert hashlib.sha256(raw).hexdigest() == info["sha256"]


def test_copies_actual_recorded_gates_and_always_labels_archive_for_review(packager):
    module, root = packager
    gates = {"A": "PASS", "F (compact-22mm)": "HELD (owner decisions: REQ-BAT-04)",
             "F (evaluation-board)": "OPEN", "G": "OPEN: requires bench data"}
    raw = json.dumps({"date": "2026-10-24", "gates": gates})
    write(root, "reports/validation-register.json", raw)
    result = module.build_package(root)
    manifest, _ = unpack_manifest(result)
    assert "DRAFT-review" in result.name
    assert manifest["validation"]["gates"] == gates
    assert manifest["validation"]["sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert manifest["validation"]["recomputed_by_packager"] is False
    assert manifest["manufacturing_release"] is False and manifest["physical_validation_claimed"] is False
    with zipfile.ZipFile(result) as archive:
        assert "not a manufacturing release" in archive.read("REVIEW_BUNDLE.md").decode()


@pytest.mark.parametrize("register,evidence", [(None, "MISSING"), ("not JSON", "MALFORMED"), ("{}", "MALFORMED")])
def test_missing_or_malformed_validation_is_explicit_without_invented_status(packager, register, evidence):
    module, root = packager
    write(root, "README.md")
    if register is not None:
        write(root, "reports/validation-register.json", register)
    manifest, _ = unpack_manifest(module.build_package(root))
    assert manifest["validation"]["evidence"] == evidence
    assert manifest["validation"]["gates"] == {}
    assert manifest["package_state"] == "DRAFT_REVIEW"
    assert "hardware/evaluation-board/nubm44_driver.kicad_pcb" in manifest["missing_review_files"]
    assert "manufacturing/pcbway/compact-22mm/reports/export-check.json" in manifest["missing_review_files"]
    assert manifest["manufacturing_export_required_to_package"] is False


def test_packaging_does_not_touch_fixed_temp_directory_or_overwrite_older_archives(packager):
    module, root = packager
    write(root, "README.md")
    first = module.build_package(root)
    previous_bytes = first.read_bytes()
    second = module.build_package(root)
    assert first != second and first.read_bytes() == previous_bytes
    assert not list((root / "dist").glob(".nubm44-review-*"))
