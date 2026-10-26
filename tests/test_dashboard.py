"""The dashboard is generated from evidence files only and reflects their content."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("dashboard_under_test", ROOT / "automation/dashboard/build_dashboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_reflects_readiness_and_gates():
    page = load().build()
    readiness = json.loads((ROOT / "reports/release-readiness.json").read_text(encoding="utf-8"))["variants"]
    for variant, r in readiness.items():
        assert variant in page and r["level"] in page
    assert "Gate G" in page and "(prediction)" in page, "predictions are labelled as such"
    assert page.count("<svg") >= 2, "efficiency and loop charts present"
    assert "<script src=" not in page and "http://" not in page and "https://" not in page, "self-contained page"


def test_missing_evidence_is_shown_not_invented(monkeypatch, tmp_path):
    module = load()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    page = module.build()
    assert "UNKNOWN" in page
    assert 'class="badge good"' not in page, "no PASS badge without evidence"
