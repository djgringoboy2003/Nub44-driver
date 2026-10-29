"""Source locations for the original 1S circuit and the separate budget circuit.

LEGACY_VARIANTS deliberately remains the default of the existing A/B workflow.
Registering a development variant does not award it the original circuit's gates.
Budget qualification has its own entry point: automation/budget/qualify.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_VARIANTS = ("compact-22mm", "evaluation-board")
BUDGET_VARIANT = "budget-2s"
ALL_VARIANTS = (*LEGACY_VARIANTS, BUDGET_VARIANT)


@dataclass(frozen=True)
class DesignSources:
    parameters: Path
    connectivity: Path
    placement: Path


def sources_for(variant: str, root: Path = ROOT) -> DesignSources:
    if variant not in ALL_VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    design = root / "engineering/design"
    if variant == BUDGET_VARIANT:
        design /= BUDGET_VARIANT
    return DesignSources(design / "parameters.yaml", design / "connectivity.yaml",
                         root / "hardware" / variant / "placement.yaml")
