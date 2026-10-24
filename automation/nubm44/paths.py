"""Repository paths and external tool discovery.

Tool locations are resolved in this order: environment variable, project-local
``tools/`` folder, per-user install, machine-wide install, PATH.
"""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARDWARE = ROOT / "hardware"
LIBRARIES = HARDWARE / "libraries"
MODELS = HARDWARE / "models"
DESIGN = ROOT / "engineering" / "design"
REPORTS = ROOT / "reports"
MANUFACTURING = ROOT / "manufacturing"
DOCS = ROOT / "documentation"
SIMULATION = ROOT / "simulation"
TOOLS = ROOT / "tools"
BUILD = ROOT / "build"

KICAD_MAJOR = "10.0"


def _first_existing(candidates) -> Path | None:
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return None


@lru_cache(maxsize=None)
def kicad_root() -> Path:
    env = os.environ.get("KICAD_ROOT")
    local = os.environ.get("LOCALAPPDATA", "")
    found = _first_existing([
        env,
        Path(local) / "Programs" / "KiCad" / KICAD_MAJOR,
        Path(local) / "Programs" / "KiCad",
        Path("C:/Program Files/KiCad") / KICAD_MAJOR,
    ])
    if found is None:
        cli = shutil.which("kicad-cli")
        if cli:
            found = Path(cli).resolve().parents[1]
    if found is None:
        raise FileNotFoundError(
            "KiCad not found. Run scripts/setup.ps1 or set KICAD_ROOT to the KiCad install folder.")
    return found


def kicad_cli() -> Path:
    exe = kicad_root() / "bin" / "kicad-cli.exe"
    if not exe.exists():
        raise FileNotFoundError(f"kicad-cli not found at {exe}")
    return exe


def kicad_python() -> Path:
    """KiCad's bundled interpreter (has the pcbnew module when KiCad ships it)."""
    exe = kicad_root() / "bin" / "python.exe"
    if not exe.exists():
        raise FileNotFoundError(f"KiCad python not found at {exe}")
    return exe


def kicad_share() -> Path:
    return kicad_root() / "share" / "kicad"


def kicad_symbols_dir() -> Path:
    return kicad_share() / "symbols"


def kicad_footprints_dir() -> Path:
    return kicad_share() / "footprints"


def kicad_3dmodels_dir() -> Path:
    return kicad_share() / "3dmodels"


def ngspice() -> Path:
    found = _first_existing([
        os.environ.get("NGSPICE"),
        TOOLS / "ngspice" / "Spice64" / "bin" / "ngspice_con.exe",
    ])
    if found is None:
        exe = shutil.which("ngspice_con") or shutil.which("ngspice")
        if exe:
            return Path(exe)
        raise FileNotFoundError("ngspice not found. Run scripts/setup.ps1.")
    return found


FREEROUTING_VERSION = "2.5.0"
JRE_DIR_NAME = "jdk-25.0.4.1+1-jre"


def java25() -> Path:
    """Project-local Temurin 25 runtime (FreeRouting 2.5.0 is compiled for Java 25)."""
    found = _first_existing([
        os.environ.get("NUBM44_JAVA"),
        TOOLS / "jre25" / JRE_DIR_NAME / "bin" / "java.exe",
    ])
    if found is None:
        raise FileNotFoundError("Java 25 runtime not found. Run scripts/setup.ps1.")
    return found


def freerouting_jar() -> Path:
    # The 2.5.0 native freerouting-cli.exe aborts with a GraalVM serialization error
    # (ComponentOutline missing from serialization-config), so the jar is used instead.
    found = _first_existing([
        os.environ.get("FREEROUTING_JAR"),
        TOOLS / "freerouting" / f"freerouting-{FREEROUTING_VERSION}.jar",
    ])
    if found is None:
        raise FileNotFoundError("FreeRouting jar not found. Run scripts/setup.ps1.")
    return found


def freerouting_cmd() -> list[str]:
    return [str(java25()), "-jar", str(freerouting_jar())]
