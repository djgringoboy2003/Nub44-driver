"""Steady-state loss model of a 4-switch non-inverting buck-boost driving a laser diode.

Switches: Q1 buck high side, Q2 buck low side, Q3 boost high side, Q4 boost low side.

Operating regions (TPS55288-family behaviour, SLVSFC5 section 7.3):
* boost  (Vin < Vout): Q1 permanently on, Q2 off, Q3/Q4 switch.
* buck   (Vin > Vout): Q3 permanently on, Q4 off, Q1/Q2 switch.
* transition (Vin close to Vout): the controller alternates one buck cycle and one
  boost cycle. Modelled as the mean of the buck-cycle and boost-cycle losses with each
  leg switching at fsw/2, plus the always-on device of the idle leg. This is an
  approximation; the datasheet gives no loss data for this region.

``band`` sets the half-width of the transition region as a fraction of Vout.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field

from .boost import LaserModel


@dataclass
class BuckBoostParams:
    r_input_path: float     # reverse-polarity FET + input copper, ohm
    l_h: float
    dcr: float
    core_loss_w: float
    rds_q1: float           # buck high side
    rds_q2: float           # buck low side
    rds_q3: float           # boost high side
    rds_q4: float           # boost low side
    t_sw_boost: float       # effective boost-leg switch-node transition time, s
    t_sw_buck: float        # effective buck-leg switch-node transition time, s
    c_oss_leg: float        # output capacitance per leg (both FETs), F
    t_deadtime: float
    vf_body: float
    q_gate_buck: float      # gate charge, Q1 + Q2, C
    q_gate_boost: float     # gate charge, Q3 + Q4, C
    v_drive: float
    i_q: float
    f_sw: float
    r_shunt: float
    r_output_path: float
    esr_out: float
    esr_in: float
    p_aux: float = 0.0
    band: float = 0.05


@dataclass
class BBPoint:
    region: str
    v_in: float
    i_out: float
    v_laser: float
    v_out_node: float
    i_in: float
    i_l_avg: float
    ripple_pp: float
    i_l_peak: float
    p_laser: float
    p_in: float
    efficiency: float
    losses: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _boost_cycle(v_sw: float, v_o: float, i_out: float, i_in: float, p: BuckBoostParams, f: float):
    d = max(1 - i_out / i_in, 0.0)
    ripple = v_sw * d / (p.l_h * f) if f > 0 else 0.0
    i_pk, i_val = i_in + ripple / 2, i_in - ripple / 2
    i_rms_sq = i_in ** 2 + ripple ** 2 / 12
    loss = {
        "q1_on": i_rms_sq * p.rds_q1,
        "q4_conduction": d * i_rms_sq * p.rds_q4,
        "q3_conduction": (1 - d) * i_rms_sq * p.rds_q3,
        "boost_switching": 0.5 * v_o * f * (max(i_val, 0) + i_pk) * p.t_sw_boost
                           + 0.5 * p.c_oss_leg * v_o ** 2 * f,
        "deadtime": p.vf_body * f * p.t_deadtime * (i_pk + max(i_val, 0)),
        "gate": p.q_gate_boost * p.v_drive * f,
        "inductor_dcr": i_rms_sq * p.dcr,
        "input_cap_esr": ripple ** 2 / 12 * p.esr_in,
        "output_cap_esr": i_in ** 2 * d * (1 - d) * p.esr_out,
    }
    return loss, ripple, i_pk


def _buck_cycle(v_sw: float, v_o: float, i_out: float, p: BuckBoostParams, f: float):
    d = min(v_o / v_sw, 1.0)
    ripple = (v_sw - v_o) * d / (p.l_h * f) if f > 0 else 0.0
    i_pk, i_val = i_out + ripple / 2, i_out - ripple / 2
    i_rms_sq = i_out ** 2 + ripple ** 2 / 12
    loss = {
        "q3_on": i_rms_sq * p.rds_q3,
        "q1_conduction": d * i_rms_sq * p.rds_q1,
        "q2_conduction": (1 - d) * i_rms_sq * p.rds_q2,
        "buck_switching": 0.5 * v_sw * f * (max(i_val, 0) + i_pk) * p.t_sw_buck
                          + 0.5 * p.c_oss_leg * v_sw ** 2 * f,
        "deadtime": p.vf_body * f * p.t_deadtime * (i_pk + max(i_val, 0)),
        "gate": p.q_gate_buck * p.v_drive * f,
        "inductor_dcr": i_rms_sq * p.dcr,
        "input_cap_esr": i_out ** 2 * d * (1 - d) * p.esr_in,
        "output_cap_esr": ripple ** 2 / 12 * p.esr_out,
    }
    return loss, ripple, i_pk


def solve(v_in: float, i_out: float, laser: LaserModel, p: BuckBoostParams,
          max_iter: int = 300) -> BBPoint:
    v_laser = laser.vf(i_out)
    v_o = v_laser + i_out * (p.r_shunt + p.r_output_path)
    if v_in < v_o * (1 - p.band):
        region = "boost"
    elif v_in > v_o * (1 + p.band):
        region = "buck"
    else:
        region = "transition"

    i_in = i_out * v_o / v_in / 0.9
    for _ in range(max_iter):
        v_sw = v_in - i_in * p.r_input_path
        if region == "boost":
            loss, ripple, i_pk = _boost_cycle(v_sw, v_o, i_out, i_in, p, p.f_sw)
            i_l = i_in
        elif region == "buck":
            loss, ripple, i_pk = _buck_cycle(v_sw, v_o, i_out, p, p.f_sw)
            i_l = i_out
        else:
            lb, rb, pb = _boost_cycle(v_sw, v_o, i_out, max(i_in, i_out * 1.0001), p, p.f_sw / 2)
            lk, rk, pk = _buck_cycle(v_sw, v_o, i_out, p, p.f_sw / 2)
            loss = {k: 0.5 * lb.get(k, 0) + 0.5 * lk.get(k, 0) for k in sorted(set(lb) | set(lk))}
            # each leg switches every other cycle at the full-frequency edge rate
            ripple, i_pk, i_l = max(rb, rk), max(pb, pk), 0.5 * (i_in + i_out)
        loss = dict(loss)
        loss["inductor_core"] = p.core_loss_w
        loss["input_path_I2R"] = i_in ** 2 * p.r_input_path
        loss["quiescent_and_aux"] = p.i_q * v_in + p.p_aux
        loss["current_shunt"] = i_out ** 2 * p.r_shunt
        loss["output_path_I2R"] = i_out ** 2 * p.r_output_path
        p_laser = v_laser * i_out
        p_in = p_laser + sum(loss.values())
        new = p_in / v_in
        if abs(new - i_in) < 1e-9:
            i_in = new
            break
        i_in = 0.5 * (i_in + new)
    else:
        raise RuntimeError("buck-boost operating point did not converge")
    return BBPoint(region=region, v_in=v_in, i_out=i_out, v_laser=v_laser, v_out_node=v_o,
                   i_in=i_in, i_l_avg=i_l, ripple_pp=ripple, i_l_peak=i_pk,
                   p_laser=p_laser, p_in=p_in, efficiency=p_laser / p_in, losses=loss)
