"""Small-signal loop model: peak-current-mode boost regulating laser-diode current.

Derivation (averaged CCM model, stiff input, inductor current directly controlled):

    L s iL = -(1-D) vo + Vo d
    C s vo = (1-D) iL - IL d - vo / Zac

Eliminating d with IL (1-D) = Io gives the inductor-current-to-output transfer

    vo / iL = (1-D) (1 - s / w_rhp) / (C s + Io/Vo + 1/Zac)

    w_rhp = Vo (1-D)^2 / (Io L)

where ``Zac`` is the small-signal impedance of the load branch seen by the output
capacitor (laser dynamic resistance + shunt + series FET + copper). With a resistive
load Zac = Vo/Io and the pole reduces to the textbook 2/(R C).

The current loop is closed through the shunt and the current-sense amplifier:

    T(s) = Gea(s) * (1/Ri) * He(s) * [vo/iL](s) * (1/Zac) * (Rs * Gcsa * Kdiv) * Hcsa(s)

``He(s)`` is Ridley's sampling double pole at fs/2. ``Ri`` is the controller's
internal current-sense gain (V/A) referred to the COMP pin. The error amplifier
is a transconductance stage with a series Rc-Cc network and a high-frequency Cp.

This is a linear model for crossover/phase-margin estimates. It ignores input
filter interaction and battery impedance; check those separately.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class LoopParams:
    v_out: float        # output-node voltage, V
    i_out: float        # laser current, A
    duty: float         # steady-state duty cycle
    l_h: float          # inductance, H
    c_out: float        # effective output capacitance (after DC bias), F
    esr: float          # output capacitor ESR, ohm
    z_ac: float         # small-signal load-branch resistance, ohm
    f_sw: float         # switching frequency, Hz
    ri: float           # controller current-sense gain referred to COMP, V/A
    q_sampling: float   # quality factor of the fs/2 sampling poles (slope-comp dependent)
    r_shunt: float      # current-sense resistor, ohm
    g_csa: float        # current-sense amplifier gain, V/V
    k_div: float        # divider from amplifier output to FB, V/V
    f_csa: float        # current-sense amplifier -3 dB bandwidth, Hz
    gm_ea: float        # error-amplifier transconductance, S
    r_ea_out: float     # error-amplifier output resistance, ohm
    r_c: float          # compensation resistor, ohm
    c_c: float          # compensation capacitor, F
    c_p: float          # high-frequency compensation capacitor, F


def plant(p: LoopParams, s: np.ndarray) -> np.ndarray:
    """Control (COMP voltage) to laser-current transfer, A/V."""
    w_rhp = p.v_out * (1 - p.duty) ** 2 / (p.i_out * p.l_h)
    w_esr = 1 / (p.esr * p.c_out) if p.esr > 0 else np.inf
    wn = math.pi * p.f_sw
    he = 1 / (1 + s / (wn * p.q_sampling) + (s / wn) ** 2)
    vo_il = ((1 - p.duty) * (1 - s / w_rhp) * (1 + s / w_esr)
             / (p.c_out * s + p.i_out / p.v_out + 1 / p.z_ac))
    return (1 / p.ri) * he * vo_il / p.z_ac


def feedback(p: LoopParams, s: np.ndarray) -> np.ndarray:
    """Laser current to FB voltage, V/A."""
    return p.r_shunt * p.g_csa * p.k_div / (1 + s / (2 * math.pi * p.f_csa))


def error_amp(p: LoopParams, s: np.ndarray) -> np.ndarray:
    """FB to COMP transfer of a gm amplifier with Rc+Cc series and Cp shunt (inverting sign dropped)."""
    z_series = p.r_c + 1 / (s * p.c_c)
    z = 1 / (1 / p.r_ea_out + 1 / z_series + s * p.c_p)
    return p.gm_ea * z


def loop_gain(p: LoopParams, f: np.ndarray) -> np.ndarray:
    s = 2j * math.pi * f
    return error_amp(p, s) * plant(p, s) * feedback(p, s)


def margins(p: LoopParams, f_min: float = 10.0, f_max: float = None, n: int = 20000) -> dict:
    """Crossover frequency, phase margin and gain margin of the current loop."""
    f_max = f_max or p.f_sw
    f = np.logspace(math.log10(f_min), math.log10(f_max), n)
    t = loop_gain(p, f)
    mag_db = 20 * np.log10(np.abs(t))
    phase = np.unwrap(np.angle(t)) * 180 / math.pi
    out = {"f": f, "mag_db": mag_db, "phase_deg": phase}
    idx = np.where(np.diff(np.sign(mag_db)) < 0)[0]
    if len(idx):
        i = idx[0]
        fc = f[i] - mag_db[i] * (f[i + 1] - f[i]) / (mag_db[i + 1] - mag_db[i])
        ph = np.interp(fc, f, phase)
        out["f_cross_hz"] = float(fc)
        out["phase_margin_deg"] = float(180 + ph)
    else:
        out["f_cross_hz"] = None
        out["phase_margin_deg"] = None
    idx = np.where(np.diff(np.sign(phase + 180)) < 0)[0]
    if len(idx):
        f180 = f[idx[0]]
        out["f_180_hz"] = float(f180)
        out["gain_margin_db"] = float(-np.interp(f180, f, mag_db))
    else:
        out["f_180_hz"] = None
        out["gain_margin_db"] = None
    out["f_rhp_hz"] = p.v_out * (1 - p.duty) ** 2 / (p.i_out * p.l_h) / (2 * math.pi)
    out["dc_gain_db"] = float(mag_db[0])
    return out
