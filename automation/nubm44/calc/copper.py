"""PCB copper current capacity and resistance.

``ipc2221_width_mm`` uses the IPC-2221 curve fit
``I = k * dT^0.44 * A^0.725`` (A in mil^2; k = 0.048 external, 0.024 internal).
IPC-2221 is conservative for short, wide conductors on a board that is heat-sunk
through its edge, which describes this driver; IPC-2152 charts give lower rises.
The fit is used here as an upper bound on required width, not a thermal model.
"""
from __future__ import annotations

import math

RHO_CU_20C = 1.724e-8      # ohm*m
ALPHA_CU = 0.00393         # 1/K
OZ_TO_M = 34.79e-6         # 1 oz/ft^2 copper thickness
MIL = 25.4e-6


def ipc2221_width_mm(current_a: float, temp_rise_c: float, copper_oz: float,
                     external: bool = True) -> float:
    k = 0.048 if external else 0.024
    area_mil2 = (current_a / (k * temp_rise_c ** 0.44)) ** (1 / 0.725)
    thickness_mil = copper_oz * OZ_TO_M / MIL
    return area_mil2 / thickness_mil * MIL * 1000


def sheet_resistance_mohm(copper_oz: float, temp_c: float = 25.0) -> float:
    """Resistance of one square of copper, milliohm."""
    rho = RHO_CU_20C * (1 + ALPHA_CU * (temp_c - 20))
    return rho / (copper_oz * OZ_TO_M) * 1000


def path_resistance_mohm(length_mm: float, width_mm: float, copper_oz: float,
                         temp_c: float = 25.0, layers: int = 1) -> float:
    squares = length_mm / width_mm
    return sheet_resistance_mohm(copper_oz, temp_c) * squares / layers


def via_resistance_mohm(drill_mm: float, plating_um: float = 20.0, board_mm: float = 1.6,
                        temp_c: float = 25.0) -> float:
    rho = RHO_CU_20C * (1 + ALPHA_CU * (temp_c - 20))
    r_out = drill_mm / 2 * 1e-3 + plating_um * 1e-6
    r_in = drill_mm / 2 * 1e-3
    area = math.pi * (r_out ** 2 - r_in ** 2)
    return rho * board_mm * 1e-3 / area * 1000


def vias_for_current(current_a: float, drill_mm: float, amps_per_via: float = 1.0) -> int:
    """Conservative via count (rule of thumb ~1 A per 0.3 mm via, scaled by circumference)."""
    per_via = amps_per_via * drill_mm / 0.3
    return math.ceil(current_a / per_via)
