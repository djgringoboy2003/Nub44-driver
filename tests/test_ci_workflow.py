"""The CI workflow stays consistent with the local toolchain pins and runs meaningful checks."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github/workflows/ci.yml"


def test_ci_toolchain_pins_match_setup_script():
    setup = (ROOT / "scripts/setup.ps1").read_text(encoding="utf-8")
    ci = CI.read_text(encoding="utf-8")
    setup_pins = dict(re.findall(r"Get-Verified '(https://[^']+)'[\s`]+\$\w+ '([0-9A-F]{64})'", setup))
    ci_pins = dict(re.findall(r"Get-Pinned '(https://[^']+)'[\s`]+'[^']+' '([0-9A-F]{64})'", ci))
    assert ci_pins, "CI downloads no pinned toolchain"
    for url, sha in ci_pins.items():
        assert setup_pins.get(url) == sha, f"{url}: CI pin differs from scripts/setup.ps1"


def test_ci_runs_the_real_checks():
    wf = yaml.safe_load(CI.read_text(encoding="utf-8"))
    runs = " ".join(step.get("run", "") for job in wf["jobs"].values() for step in job["steps"])
    for needed in ("pytest tests", "firmware/build.py --host-only --mutation", "validate.py --mode fast",
                   "firmware/build.py --mutation"):
        assert needed in runs, needed
    assert "continue-on-error" not in CI.read_text(encoding="utf-8"), "no step may be allowed to fail silently"
