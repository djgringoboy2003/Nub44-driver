"""Steady-state CCM model of a synchronous boost converter driving a laser diode.

The model solves the operating point self-consistently:

* output current ``i_out`` is fixed (constant-current regulation),
* the output-node voltage is the laser forward voltage plus resistive drops of the
  current-sense shunt, the series laser-path MOSFET and the output copper,
* average inductor current comes from the power balance (output power + losses),
* duty follows from the boost current relation ``i_out = i_L,avg * (1 - D)``.

All resistances should be entered at the expected operating temperature.
Switching-loss terms use the usual first-order hard-switching approximation, so
this model is a design estimate and must be checked against datasheet
efficiency curves and, finally, bench measurements.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict


@dataclass
class LaserModel:
    """Piecewise-linear diode model: Vf = v0 + rd * I (valid above threshold)."""

    v0: float          # intercept voltage, V
    rd: float          # dynamic resistance, ohm

    def vf(self, i: float) -> float:
        return self.v0 + self.rd * i


@dataclass
class BoostParams:
    # source side (all at the board's battery contacts unless stated)
    r_input_path: float     # fuse + reverse-polarity FET + input copper, ohm
    # inductor
    l_h: float              # inductance at operating current (after saturation roll-off), H
    dcr: float              # DC resistance at temperature, ohm
    core_loss_w: float      # core loss at the operating point (vendor calculator), W
    # switches (integrated or discrete)
    rds_ls: float           # low-side switch on-resistance at temperature, ohm
    rds_hs: float           # high-side (synchronous) switch on-resistance at temperature, ohm
    t_rise: float           # effective switch-node voltage rise time, s
    t_fall: float           # effective switch-node voltage fall time, s
    c_oss_total: float      # LS + HS output capacitance (energy-equivalent), F
    t_deadtime: float       # dead time per transition, s
    vf_body: float          # body-diode forward voltage during dead time, V
    q_gate_total: float     # total gate charge of both switches, C
    v_drive: float          # gate-drive voltage, V
    i_q: float              # controller quiescent current, A
    f_sw: float             # switching frequency, Hz
    # output side
    r_shunt: float          # current-sense resistor, ohm
    r_laser_fet: float      # series laser-path MOSFET on-resistance, ohm
    r_output_path: float    # output copper + connections to the diode, ohm
    esr_out: float          # output capacitor bank ESR, ohm
    esr_in: float           # input capacitor bank ESR, ohm
    c_out_eff: float        # effective output capacitance after DC-bias derating, F
    c_in_eff: float         # effective input capacitance after DC-bias derating, F
    p_aux: float = 0.0      # MCU, amplifiers, dividers, LEDs (W, from the battery)


@dataclass
class OperatingPoint:
    v_in: float
    i_out: float
    v_laser: float
    v_out_node: float
    duty: float
    i_in: float
    i_l_avg: float
    ripple_pp: float
    i_l_peak: float
    i_l_valley: float
    i_l_rms: float
    ccm: bool
    i_cin_rms: float
    i_cout_rms: float
    v_out_ripple_pp: float
    p_laser: float
    p_in: float
    efficiency: float
    losses: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def solve(v_in: float, i_out: float, laser: LaserModel, p: BoostParams,
          tol: float = 1e-9, max_iter: int = 200) -> OperatingPoint:
    """Solve the converter operating point for a stiff source of ``v_in`` at the board."""
    v_laser = laser.vf(i_out)
    v_node = v_laser + i_out * (p.r_shunt + p.r_laser_fet + p.r_output_path)
    if v_node <= v_in:
        raise ValueError(
            f"boost cannot regulate: required output {v_node:.3f} V <= input {v_in:.3f} V")

    i_in = i_out * v_node / v_in / 0.9  # starting guess
    for _ in range(max_iter):
        v_sw_in = v_in - i_in * p.r_input_path       # voltage at the inductor input
        d = 1.0 - i_out / i_in
        ripple = v_sw_in * d / (p.l_h * p.f_sw)
        i_pk = i_in + ripple / 2
        i_val = i_in - ripple / 2
        i_rms_sq = i_in ** 2 + ripple ** 2 / 12
        losses = {
            "input_path_I2R": i_in ** 2 * p.r_input_path,
            "inductor_dcr": i_rms_sq * p.dcr,
            "inductor_core": p.core_loss_w,
            "low_side_conduction": d * i_rms_sq * p.rds_ls,
            "high_side_conduction": (1 - d) * i_rms_sq * p.rds_hs,
            "switching_overlap": 0.5 * v_node * p.f_sw * (max(i_val, 0) * p.t_rise + i_pk * p.t_fall),
            "coss": 0.5 * p.c_oss_total * v_node ** 2 * p.f_sw,
            "deadtime_body_diode": p.vf_body * p.f_sw * p.t_deadtime * (i_pk + max(i_val, 0)),
            "gate_drive": p.q_gate_total * p.v_drive * p.f_sw,
            "quiescent_and_aux": p.i_q * v_in + p.p_aux,
            "input_cap_esr": (ripple ** 2 / 12) * p.esr_in,
            "output_cap_esr": i_in ** 2 * d * (1 - d) * p.esr_out,
            "current_shunt": i_out ** 2 * p.r_shunt,
            "laser_path_fet": i_out ** 2 * p.r_laser_fet,
            "output_path_I2R": i_out ** 2 * p.r_output_path,
        }
        p_laser = v_laser * i_out
        p_in = p_laser + sum(losses.values())
        i_in_new = p_in / v_in
        if abs(i_in_new - i_in) < tol:
            i_in = i_in_new
            break
        i_in = 0.5 * (i_in + i_in_new)
    else:
        raise RuntimeError("operating point did not converge")

    d = 1.0 - i_out / i_in
    i_cout_rms = i_in * math.sqrt(d * (1 - d))
    # output ripple: charge removed during the on-time plus ESR step
    v_ripple = i_out * d / (p.f_sw * p.c_out_eff) + i_pk * p.esr_out
    return OperatingPoint(
        v_in=v_in, i_out=i_out, v_laser=v_laser, v_out_node=v_node, duty=d,
        i_in=i_in, i_l_avg=i_in, ripple_pp=ripple, i_l_peak=i_pk, i_l_valley=i_val,
        i_l_rms=math.sqrt(i_rms_sq), ccm=i_val > 0, i_cin_rms=ripple / math.sqrt(12),
        i_cout_rms=i_cout_rms, v_out_ripple_pp=v_ripple, p_laser=p_laser, p_in=p_in,
        efficiency=p_laser / p_in, losses=losses,
    )


def inductance_for_ripple(v_in: float, v_out: float, i_l_avg: float, ripple_frac: float,
                          f_sw: float) -> float:
    """Inductance giving a peak-to-peak ripple of ``ripple_frac * i_l_avg`` (lossless duty)."""
    d = 1 - v_in / v_out
    return v_in * d / (ripple_frac * i_l_avg * f_sw)


def rhp_zero_hz(v_out: float, i_out: float, duty: float, l_h: float) -> float:
    """Right-half-plane zero of the boost (uses the DC load resistance Vout/Iout)."""
    return (v_out / i_out) * (1 - duty) ** 2 / (2 * math.pi * l_h)
