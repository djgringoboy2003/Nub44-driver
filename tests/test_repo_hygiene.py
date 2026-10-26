"""Repository hygiene: tracked text sources must not contain control characters (audit AUD-DOC-01: shell heredocs once
turned path backslashes into BEL/BS/TAB bytes in AGENTS.md)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (".md", ".py", ".yaml", ".yml", ".c", ".h", ".ps1", ".txt", ".toml", ".json")
BAD = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def tracked_files():
    r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, timeout=60)
    files = [ROOT / f for f in r.stdout.decode("utf-8").split("\0") if f] if r.returncode == 0 else []
    return [f for f in files if f.suffix.lower() in TEXT and f.is_file()]


def test_no_control_characters_in_text_sources():
    offenders = []
    for f in tracked_files():
        data = f.read_bytes()
        m = BAD.search(data)
        if m:
            line = data[:m.start()].count(b"\n") + 1
            offenders.append(f"{f.relative_to(ROOT)}:{line} byte 0x{m.group()[0]:02x}")
    assert not offenders, offenders


def test_text_sources_are_utf8():
    bad = []
    for f in tracked_files():
        try:
            f.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            bad.append(str(f.relative_to(ROOT)))
    assert not bad, bad
