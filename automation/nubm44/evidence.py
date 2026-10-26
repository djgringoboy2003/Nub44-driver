"""Evidence manifests: bind generated results to the exact inputs and tools that produced them.

A manifest records SHA-256 hashes of every input file, the hash of each output it describes and the versions
of the tools used. Validation recomputes the hashes: a changed input, a changed output or a missing file makes
the evidence stale, whatever the file modification times say (audit AUD-VAL-01/02/08).
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "nubm44-evidence-manifest.v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path, root: Path = ROOT) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def file_hashes(paths: Iterable[Path], root: Path = ROOT) -> dict[str, str]:
    return {rel(p, root): sha256_file(p) for p in sorted(set(paths), key=lambda p: rel(p, root))}


def python_tools(packages: Iterable[str] = ()) -> dict[str, str]:
    tools = {"python": platform.python_version()}
    for name in packages:
        try:
            tools[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            tools[name] = "UNKNOWN"
    return tools


def command_version(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        for line in (r.stdout + r.stderr).splitlines():
            if line.strip():
                return line.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "UNKNOWN"


def _generator(root: Path) -> str:
    try:
        return rel(Path(sys.argv[0]), root)
    except (ValueError, OSError):
        return Path(sys.argv[0]).name


def build(kind: str, inputs: Iterable[Path], outputs: Iterable[Path], tools: dict[str, str],
          root: Path = ROOT, **extra) -> dict:
    return {"schema": SCHEMA, "kind": kind, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "generator": _generator(root), "inputs": file_hashes(inputs, root), "outputs": file_hashes(outputs, root),
            "tools": tools, **extra}


def write(manifest: dict, path: Path) -> None:
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def problems(manifest, root: Path = ROOT, expected_kind: str | None = None,
             required_inputs: Iterable[str] = ()) -> list[str]:
    """Reasons the evidence cannot be trusted; empty when every hash still matches."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        return ["missing or malformed evidence manifest"]
    out = []
    if expected_kind and manifest.get("kind") != expected_kind:
        out.append(f"evidence manifest kind {manifest.get('kind')!r}, expected {expected_kind!r}")
    for section in ("inputs", "outputs"):
        entries = manifest.get(section)
        if not isinstance(entries, dict) or not entries:
            out.append(f"evidence manifest has no {section}")
            continue
        for key, digest in sorted(entries.items()):
            p = root / key
            if not p.is_file():
                out.append(f"{section[:-1]} missing: {key}")
            elif sha256_file(p) != digest:
                out.append(f"stale evidence: {key} changed since it was generated" if section == "inputs"
                           else f"output {key} differs from its manifest")
    recorded = manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
    for key in required_inputs:
        if key not in recorded:
            out.append(f"evidence manifest does not cover required input {key}")
    if not isinstance(manifest.get("tools"), dict) or not manifest["tools"]:
        out.append("evidence manifest records no tool versions")
    return out


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
