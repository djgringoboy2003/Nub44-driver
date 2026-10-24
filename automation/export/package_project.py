"""Create a DRAFT review archive directly from the workspace, without copying/deleting a temp tree.

The embedded manifest inventories the exact archived bytes and copies recorded
validation gates. Packaging does not run validation or grant a release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("automation", "documentation", "engineering", "firmware", "hardware", "manufacturing",
               "reports", "research", "scripts", "simulation", "sourcing", "tests")
VARIANTS = ("compact-22mm", "evaluation-board")
EXCLUDED_DIRS = {"tools", ".venv", "venv", "build", "dist", "downloads", "download", "datasheets",
                 "node_modules", "__pycache__", "cache", "caches", ".git", ".hg", ".svn"}
EXCLUDED_SUFFIXES = {".exe", ".dll", ".pyd", ".jar", ".msi", ".whl", ".pyc", ".pyo", ".o", ".obj",
                     ".elf", ".a", ".7z", ".rar", ".tar", ".tgz", ".gz", ".bz2", ".tbz2", ".xz", ".zst",
                     ".cab", ".dmg", ".iso", ".bak", ".tmp", ".lck", ".kicad_prl"}
ROOT_SUFFIXES = {".md", ".txt", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".lock"}
ROOT_NAMES = {".gitignore", ".gitattributes", ".editorconfig", "LICENSE", "NOTICE"}
CORE_REVIEW_FILES = ("AGENTS.md", "README.md", "PROGRESS.md", "requirements.txt", "engineering/requirements.md",
                     "engineering/design/parameters.yaml", "engineering/design/connectivity.yaml",
                     "reports/validation-register.json", "reports/validation-register.md",
                     "documentation/testing/test-plan.md")
VALIDATION_PATH = "reports/validation-register.json"


def excluded(relative: Path, directory=False) -> bool:
    """Never traverse downloads, local tools, VCS, caches or failed export drafts."""
    for part in relative.parts:
        low = part.lower()
        if low in EXCLUDED_DIRS or (part.startswith(".") and relative.as_posix() not in ROOT_NAMES):
            return True
        if low.endswith("-backups") or "-staging-" in low or low in {"staging", "failed", "failed-exports"}:
            return True
    if directory:
        return False
    name, suffix = relative.name, relative.suffix.lower()
    if name.startswith(("~", "_autosave-", "#auto_saved_files#")) or suffix in EXCLUDED_SUFFIXES:
        return True
    if relative.parts[0] == "research" and suffix in {".pdf", ".zip"}:
        return True
    if suffix == ".zip":
        return not (len(relative.parts) == 4 and relative.parts[:2] == ("manufacturing", "pcbway")
                    and relative.parts[2] in VARIANTS and name == f"{relative.parts[2]}-gerbers.zip")
    return False


def source_files(root: Path) -> list[Path]:
    files = []
    for p in root.iterdir():
        if p.is_file() and not p.is_symlink() and (p.suffix.lower() in ROOT_SUFFIXES or p.name in ROOT_NAMES):
            files.append(p)
    for name in SOURCE_DIRS:
        folder = root / name
        if not folder.is_dir() or folder.is_symlink() or not folder.resolve().is_relative_to(root):
            continue
        for current, dirs, names in os.walk(folder, followlinks=False):
            current = Path(current)
            dirs[:] = [name for name in sorted(dirs)
                       if not excluded((current / name).relative_to(root), directory=True)
                       and not (current / name).is_symlink()
                       and (current / name).resolve().is_relative_to(root)]
            for name in sorted(names):
                p = current / name
                if not p.is_symlink() and p.is_file() and p.resolve().is_relative_to(root) and not excluded(p.relative_to(root)):
                    files.append(p)
    return sorted(set(files), key=lambda p: p.relative_to(root).as_posix())


def git_state(root: Path) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=10)
        return {"commit": commit.stdout.strip() if commit.returncode == 0 else "UNKNOWN",
                "working_tree": ("DIRTY" if status.stdout.strip() else "CLEAN") if status.returncode == 0 else "UNKNOWN"}
    except (OSError, subprocess.SubprocessError):
        return {"commit": "UNKNOWN", "working_tree": "UNKNOWN"}


def validation_snapshot(raw: bytes | None) -> dict:
    result = {"source": VALIDATION_PATH, "recomputed_by_packager": False, "gates": {}}
    if raw is None:
        return dict(result, evidence="MISSING", detail="Validation register was not available; no gate status is asserted.")
    result["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("gates"), dict) or not data["gates"] or any(
                not isinstance(k, str) or not isinstance(value, str) for k, value in data["gates"].items()):
            raise ValueError("missing or malformed gate mapping")
        return dict(result, evidence="RECORDED", date=data.get("date", "UNKNOWN"), gates=data["gates"],
                    detail="Copied from the archived register; packaging does not rerun its checks.")
    except (ValueError, UnicodeError) as exc:
        return dict(result, evidence="MALFORMED", detail=str(exc))


def missing_review_files(inventory: dict) -> list[str]:
    required = list(CORE_REVIEW_FILES)
    for variant in VARIANTS:
        required += [f"hardware/{variant}/{name}" for name in
                     ("placement.yaml", "nubm44_driver.kicad_sch", "nubm44_driver.kicad_pcb", "nubm44_driver.kicad_pro")]
        required += [f"reports/{name}-{variant}.json" for name in ("schematic", "erc", "drc")]
        required += [f"reports/drc-{variant}-evidence.json", f"manufacturing/pcbway/{variant}/reports/export-check.json"]
    return [name for name in required if name not in inventory]


def review_note(manifest: dict) -> str:
    lines = ["# DRAFT design review bundle", "", "This archive is for review. It is not a manufacturing release.",
             "Packaging does not place an order or close a validation gate.", "",
             f"Created: {manifest['created_utc']}", "", "Recorded gates from the archived validation register:", "",
             "| Gate | Recorded status |", "|---|---|"]
    gates = manifest["validation"]["gates"]
    lines += [f"| {key.replace('|', '/')} | {value.replace('|', '/')} |" for key, value in gates.items()]
    if not gates:
        lines += ["| UNKNOWN | Validation register missing or malformed |"]
    lines += ["", "Gate G requires assembled-prototype bench evidence. This bundle makes no claim of physical validation.",
              "", "`review-bundle-manifest.json` contains hashes for every workspace file included in this archive,",
              "the source commit/worktree state, exclusions, and missing review files or generated deliverables.",
              "Tool installers, virtual environments, scratch builds, downloaded datasheets, caches, VCS data and",
              "failed export staging directories are excluded.", ""]
    return "\n".join(lines)


def build_package(root: Path = ROOT, output_dir: Path | None = None) -> Path:
    root = root.resolve()
    output_dir = (output_dir or root / "dist").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc)
    destination = output_dir / f"nubm44-driver-DRAFT-review-{created.strftime('%Y%m%dT%H%M%S.%fZ')}.zip"
    handle, temporary = tempfile.mkstemp(prefix=".nubm44-review-", suffix=".zip", dir=output_dir)
    os.close(handle)
    temporary = Path(temporary)
    inventory, validation_raw = {}, None
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for p in source_files(root):
                rel = p.relative_to(root).as_posix()
                raw = p.read_bytes()
                archive.writestr(rel, raw)
                inventory[rel] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                if rel == VALIDATION_PATH:
                    validation_raw = raw
            manifest = {"schema": "nubm44-review-bundle.v1", "package_state": "DRAFT_REVIEW",
                        "manufacturing_release": False, "physical_validation_claimed": False,
                        "created_utc": created.isoformat(), "git": git_state(root),
                        "validation": validation_snapshot(validation_raw), "files": inventory,
                        "missing_review_files": missing_review_files(inventory),
                        "manufacturing_export_required_to_package": False,
                        "exclusions": ["local tools and environments", "VCS and caches", "build/dist scratch",
                                       "downloaded datasheets and archives", "failed export staging directories",
                                       "KiCad backups/autosaves/local preferences", "symlinks and external targets"]}
            archive.writestr("review-bundle-manifest.json", json.dumps(manifest, indent=2) + "\n")
            archive.writestr("REVIEW_BUNDLE.md", review_note(manifest))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise RuntimeError("review archive CRC check failed")
            for rel, info in inventory.items():
                if hashlib.sha256(archive.read(rel)).hexdigest() != info["sha256"]:
                    raise RuntimeError(f"review archive differs from source snapshot: {rel}")
        temporary.replace(destination)
    except BaseException:
        # Delete only the unique file this call created, never a directory tree.
        if temporary.resolve().parent != output_dir:
            raise RuntimeError("temporary ZIP resolved outside the output directory")
        temporary.unlink(missing_ok=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    result = build_package(output_dir=parser.parse_args().output_dir)
    print(f"DRAFT review package: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
