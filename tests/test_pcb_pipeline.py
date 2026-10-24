"""PCB evidence producers must reject failed tools and stale routing inputs."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

VARIANT = "compact-22mm"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[1] / "automation/placement/build_pcb.py"
    spec = importlib.util.spec_from_file_location("pcb_pipeline_under_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    for key, subdir in (("HARDWARE", "hardware"), ("BUILD", "build"), ("REPORTS", "reports")):
        target = tmp_path / subdir
        target.mkdir()
        monkeypatch.setattr(module.paths, key, target)
    (module.paths.BUILD / VARIANT).mkdir()
    vdir = module.paths.HARDWARE / VARIANT
    vdir.mkdir()
    for suffix in ("kicad_pcb", "kicad_sch", "kicad_pro"):
        (vdir / f"{module.PROJECT}.{suffix}").write_text(f"original {suffix}", encoding="utf-8")
    sources = [vdir / "placement.yaml", tmp_path / "engineering/design/connectivity.yaml",
               tmp_path / "engineering/design/parameters.yaml"]
    for source_path in sources:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f"original {source_path.name}", encoding="utf-8")
    monkeypatch.setattr(module.paths, "kicad_cli", lambda: Path("fixture-kicad-cli"))
    monkeypatch.setattr(module.paths, "kicad_python", lambda: Path("fixture-kicad-python"))
    monkeypatch.setattr(module.paths, "freerouting_cmd", lambda: ["fixture-java", "-jar", "fixture-router.jar"])
    return module


def drc_paths(p):
    return (p.paths.REPORTS / f"drc-{VARIANT}.json",
            p.paths.REPORTS / f"drc-{VARIANT}-evidence.json")


def drc_data():
    return {"violations": [], "unconnected_items": [], "schematic_parity": []}


@pytest.mark.parametrize("returncode,writes_report", [(7, False), (7, True), (0, False)])
def test_failed_or_missing_drc_output_cannot_reuse_passing_evidence(pipeline, monkeypatch,
                                                                  returncode, writes_report):
    p = pipeline
    report, evidence = drc_paths(p)
    write_json(report, drc_data())
    write_json(evidence, {"report_sha256": sha256(report)})

    def run(cmd):
        assert not report.exists() and not evidence.exists()
        if writes_report:
            write_json(report, drc_data())
        return subprocess.CompletedProcess(cmd, returncode, "fixture output", "fixture error"), 0.1

    monkeypatch.setattr(p, "run", run)
    with pytest.raises(RuntimeError, match="KiCad DRC failed"):
        p.stage_drc(VARIANT)
    assert not evidence.exists()


def test_drc_manifest_binds_board_after_save_board_and_preserves_findings(pipeline, monkeypatch):
    p = pipeline
    report, evidence = drc_paths(p)
    board = p.paths.HARDWARE / VARIANT / f"{p.PROJECT}.kicad_pcb"
    initial_hash = sha256(board)
    observed = []
    data = drc_data()
    data["violations"] = [{"type": "clearance", "severity": "error"},
                          {"type": "track_dangling", "severity": "warning"}]
    data["unconnected_items"] = [{"type": "unconnected_items", "severity": "error"}]
    data["schematic_parity"] = [{"type": "footprint_symbol_field_mismatch", "severity": "warning"}]

    def run(cmd):
        observed.extend(str(arg) for arg in cmd)
        # KiCad --save-board changes the input while producing its report.
        board.write_text("board after zone refill and save", encoding="utf-8")
        write_json(report, data)
        return subprocess.CompletedProcess(cmd, 0, "checked fixture", ""), 0.1

    monkeypatch.setattr(p, "run", run)
    result = p.stage_drc(VARIANT)
    manifest = json.loads(evidence.read_text(encoding="utf-8"))
    assert {"--save-board", "--refill-zones", "--schematic-parity", "--severity-all"} <= set(observed)
    assert manifest["report_sha256"] == sha256(report)
    assert manifest["inputs"][board.relative_to(p.ROOT).as_posix()] == sha256(board) != initial_hash
    expected_inputs = {path.relative_to(p.ROOT).as_posix(): sha256(path) for path in (
        board, board.with_suffix(".kicad_sch"), board.with_suffix(".kicad_pro"), board.parent / "placement.yaml",
        p.ROOT / "engineering/design/connectivity.yaml", p.ROOT / "engineering/design/parameters.yaml")}
    assert manifest["inputs"] == expected_inputs
    assert manifest["schematic_parity"] is True and manifest["severity_all"] is True
    assert result == {"errors": 1, "warnings": 1, "unconnected": 1, "parity": 1,
                      "by_type": {"clearance": 1, "track_dangling": 1}}


def test_source_edit_during_drc_cannot_certify_unchanged_cad(pipeline, monkeypatch):
    p = pipeline
    report, evidence = drc_paths(p)
    placement = p.paths.HARDWARE / VARIANT / "placement.yaml"

    def run(cmd):
        placement.write_text("edited placement while DRC runs", encoding="utf-8")
        write_json(report, drc_data())
        return subprocess.CompletedProcess(cmd, 0, "fixture checked", ""), 0.1

    monkeypatch.setattr(p, "run", run)
    with pytest.raises(RuntimeError, match="design source changed during DRC"):
        p.stage_drc(VARIANT)
    assert not evidence.exists()


@pytest.mark.parametrize("missing", ["violations", "unconnected_items", "schematic_parity"])
def test_incomplete_drc_report_is_not_certified(pipeline, monkeypatch, missing):
    p = pipeline
    report, evidence = drc_paths(p)
    data = drc_data()
    del data[missing]

    def run(cmd):
        write_json(report, data)
        return subprocess.CompletedProcess(cmd, 0, "", ""), 0.1

    monkeypatch.setattr(p, "run", run)
    with pytest.raises(ValueError, match="Malformed DRC report"):
        p.stage_drc(VARIANT)
    assert not evidence.exists()


def routing_fixture(p):
    build = p.paths.BUILD / VARIANT
    dsn, ses = (build / f"{p.PROJECT}.{suffix}" for suffix in ("dsn", "ses"))
    dsn.write_text("fixture placed design", encoding="utf-8")
    ses.write_text("fixture routed session", encoding="utf-8")
    manifest = build / "routing-evidence.json"
    write_json(manifest, {"dsn_sha256": sha256(dsn), "ses_sha256": sha256(ses)})
    return {"mode": "finish", "dsn": str(dsn), "ses": str(ses)}, manifest


@pytest.mark.parametrize("fault", ["missing_manifest", "invalid_manifest", "changed_dsn", "changed_ses",
                                   "missing_dsn", "missing_ses"])
def test_finish_rejects_stale_or_missing_dsn_session_evidence(pipeline, monkeypatch, fault):
    p = pipeline
    job, manifest = routing_fixture(p)
    if fault == "missing_manifest":
        manifest.unlink()
    elif fault == "invalid_manifest":
        manifest.write_text("invalid JSON", encoding="utf-8")
    else:
        action, key = fault.split("_")
        source = Path(job[key])
        if action == "missing":
            source.unlink()
        else:
            source.write_text("edited after routing", encoding="utf-8")

    def unexpected_run(*args, **kwargs):
        pytest.fail("KiCad must not import a session with stale input evidence")

    monkeypatch.setattr(p, "run", unexpected_run)
    with pytest.raises((RuntimeError, ValueError)):
        p.kicad_py(job, VARIANT)
    assert not (p.paths.BUILD / VARIANT / "job-finish.json").exists()


def test_finish_accepts_matching_session_evidence(pipeline, monkeypatch):
    p = pipeline
    job, _ = routing_fixture(p)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert json.loads(Path(cmd[-1]).read_text(encoding="utf-8")) == job
        return subprocess.CompletedProcess(cmd, 0, "fixture imported", ""), 0.1

    monkeypatch.setattr(p, "run", run)
    p.kicad_py(job, VARIANT)
    assert len(calls) == 1


def test_route_command_preserves_width_and_ground_plane_and_hashes_session(pipeline, monkeypatch):
    p = pipeline
    job, evidence = routing_fixture(p)
    observed = []

    def run(cmd, timeout):
        assert not Path(job["ses"]).exists() and not evidence.exists()
        observed.extend(cmd)
        assert timeout == 123
        Path(job["ses"]).write_text("new session from fixture router", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "Auto-routing stage completed: 2 unrouted", ""), 0.2

    monkeypatch.setattr(p, "run", run)
    result = p.stage_route(VARIANT, passes=47, timeout=123)
    assert "--router.autorouter.max_passes=47" in observed
    assert "--router.automatic_neckdown=false" in observed
    assert f"--router.neck_width_um={int(p.RULES['min_track_width'] * 1000)}" in observed
    assert "--router.layers.routable=true,false,true,true" in observed
    manifest = json.loads(evidence.read_text(encoding="utf-8"))
    assert manifest["dsn_sha256"] == sha256(Path(job["dsn"]))
    assert manifest["ses_sha256"] == sha256(Path(job["ses"]))
    assert manifest["command"] == [str(arg) for arg in observed]
    assert result["rc"] == 0


@pytest.mark.parametrize("returncode,session", [(9, "partial session"), (0, ""), (0, None)])
def test_failed_route_cannot_certify_a_partial_or_old_session(pipeline, monkeypatch, returncode, session):
    p = pipeline
    job, evidence = routing_fixture(p)

    def run(cmd, **kwargs):
        assert not Path(job["ses"]).exists() and not evidence.exists()
        if session is not None:
            Path(job["ses"]).write_text(session, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode, "fixture router", "fixture error"), 0.1

    monkeypatch.setattr(p, "run", run)
    with pytest.raises(RuntimeError, match="FreeRouting failed"):
        p.stage_route(VARIANT, passes=2, timeout=10)
    assert not evidence.exists()


def test_dsn_changed_during_routing_cannot_be_bound_to_session(pipeline, monkeypatch):
    p = pipeline
    job, evidence = routing_fixture(p)

    def run(cmd, **kwargs):
        Path(job["dsn"]).write_text("different placement while router runs", encoding="utf-8")
        Path(job["ses"]).write_text("session for original placement", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "fixture completed", ""), 0.1

    monkeypatch.setattr(p, "run", run)
    with pytest.raises(RuntimeError, match="DSN changed during routing"):
        p.stage_route(VARIANT, passes=2, timeout=10)
    assert not evidence.exists()


def test_route_timeout_preserves_diagnostics_without_session_evidence(pipeline, monkeypatch):
    p = pipeline
    _, evidence = routing_fixture(p)

    def run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10, output=b"partial router output", stderr=b"partial error")

    monkeypatch.setattr(p, "run", run)
    with pytest.raises(RuntimeError, match="FreeRouting timed out"):
        p.stage_route(VARIANT, passes=2, timeout=10)
    log = (p.paths.BUILD / VARIANT / "freerouting.log").read_text(encoding="utf-8")
    assert "partial router output" in log and "partial error" in log
    assert not evidence.exists()
