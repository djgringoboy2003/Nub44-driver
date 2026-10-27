"""Firmware build driver and host register model stay consistent with the sources and the real AVR header."""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "firmware"
MOCK = FW / "tests" / "mock" / "avr" / "io.h"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("firmware_build", FW / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _constants(text: str) -> dict[str, int]:
    values = {}
    for m in re.finditer(r"#define\s+(\w+_(?:bm|gc|gm))\s+\(?(0x[0-9A-Fa-f]+|\d+)\)?\s", text):
        values[m[1]] = int(m[2], 0)
    for m in re.finditer(r"#define\s+(\w+_(?:bm|gc|gm))\s+\(1<<(\d+)\)", text):
        values[m[1]] = 1 << int(m[2])
    for m in re.finditer(r"^\s+(\w+_gc)\s*=\s*\((0x[0-9A-Fa-f]+)<<(\d+)\)", text, re.M):
        values[m[1]] = int(m[2], 16) << int(m[3])
    return values


def test_mock_register_constants_match_the_real_header():
    header = next((ROOT / "tools" / "avr-gcc").rglob("iotn1616.h"), None) if (ROOT / "tools" / "avr-gcc").is_dir() else None
    if header is None:
        pytest.skip("avr-gcc toolchain not installed (scripts/setup.ps1)")
    real = _constants(header.read_text(encoding="utf-8"))
    mock = _constants(MOCK.read_text(encoding="utf-8"))
    assert len(mock) > 50
    wrong = {k: (v, real.get(k)) for k, v in mock.items() if real.get(k) != v}
    assert not wrong, f"mock constants differ from iotn1616.h: {wrong}"


def test_every_hal_register_constant_is_modelled():
    used = set(re.findall(r"\b([A-Z][A-Z0-9]*_\w*_(?:bm|gc|gm))\b", (FW / "src" / "hal_avr.c").read_text(encoding="utf-8")))
    assert used <= set(_constants(MOCK.read_text(encoding="utf-8")))


def test_every_c_test_file_belongs_to_a_suite(build):
    in_suites = {src for _, sources in build.SUITES.values() for src in sources if src.startswith("tests/")}
    on_disk = {p.relative_to(FW).as_posix() for p in (FW / "tests").glob("*.c")}
    assert on_disk <= in_suites, f"test files not run by firmware/build.py: {on_disk - in_suites}"


def test_every_target_source_is_built(build):
    assert all(src.startswith("src/") or src.startswith("tests/") for _, s in build.SUITES.values() for src in s)
    assert "-Werror" in build.TARGET_FLAGS and "-mmcu=attiny1616" in build.TARGET_FLAGS


def test_mutation_patterns_still_match_the_sources(build):
    for name, rel, old, _new, suite in build.MUTANTS:
        assert old in (FW / rel).read_text(encoding="utf-8"), f"{name}: pattern no longer in {rel}"
        assert suite in build.SUITES


def test_host_suites_pass_when_a_compiler_exists(build):
    if build.host_compiler() is None:
        pytest.skip("no host C compiler")
    results, compiler = build.host_tests(FW / "build" / "pytest-host")
    failing = [f"{r['suite']}: {r['status']} {r.get('stage', '')} {r.get('detail', '')}" for r in results
               if r["status"] != "PASS"]
    assert results and not failing, f"{compiler}: " + " | ".join(failing)
