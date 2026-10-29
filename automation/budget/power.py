"""Budget-2S operating point, dropout and protection-threshold margins.

Steady-state averaged model of connector -> input path -> TPS54821 buck -> shunt -> single
P-FET disconnect -> board output terminals. Datasheet limits come from the budget YAML;
`power_model` values are layout/BOM allocations (limits the design must meet) and
`estimates` are labelled efficiency-only estimates. Nothing here is a measurement.
"""
from __future__ import annotations

CORNERS = ("typical", "maximum")


def fet_r(fet: dict, vgs_abs: float, corner: str) -> float:
    """Resistance at the weakest specified gate drive that |Vgs| still reaches; no interpolation."""
    kind = "max" if corner == "maximum" else "typ"
    for drive, key in ((4.5, "4p5v"), (2.5, "2p5v")):
        if vgs_abs >= drive:
            return fet[f"r_ohm_{kind}_at_{key}_25c"]
    raise ValueError(f"{fet['mpn']}: |Vgs| {vgs_abs:.3f} V is below its lowest specified drive")


def shunt_error(p: dict) -> float:
    s = p["current_sense"]
    return s["shunt_tolerance_fraction"] + s["shunt_tcr_fraction_per_c"] * s["shunt_delta_c_from_25"]


def output_fet(p: dict, mpn: str) -> dict:
    found = [c for c in p["disconnect"]["candidates"] if c["mpn"] == mpn]
    if len(found) != 1:
        raise ValueError(f"disconnect candidate {mpn!r} not found exactly once")
    return found[0]


def gate_fraction(p: dict) -> float:
    """|Vgs| / source voltage with the gate pulled down through the series resistor (DD-34)."""
    d = p["disconnect"]
    return d["gate_pullup_ohm"] / (d["gate_pullup_ohm"] + d["gate_series_ohm"])


def output_resistance(p: dict, fet: dict, v_term: float, corner: str) -> float:
    """Shunt + output P-FET + board copper. |Vgs| is the gate fraction of VBUCK (> v_term, conservative)."""
    worst = corner == "maximum"
    hot = p["disconnect"]["r_hot_multiplier_sensitivity"] if worst else 1.0
    r_shunt = p["current_sense"]["shunt_ohm"] * (1 + (shunt_error(p) if worst else 0.0))
    return r_shunt + fet_r(fet, gate_fraction(p) * v_term, corner) * hot + p["power_model"]["output_copper_ohm_allocation"]


def buck_losses(p: dict, pvin: float, vout: float, il: float, corner: str) -> tuple[float, float, dict]:
    """Duty, ripple and loss terms of the TPS54821 stage and inductor alone."""
    worst = corner == "maximum"
    b, l, est = p["buck"], p["inductor"], p["estimates"]
    r_hs = b["high_side_r_ohm_max"] if worst else b["high_side_r_ohm_typ"]
    r_ls = b["low_side_r_ohm_max"] if worst else b["low_side_r_ohm_typ"]
    dcr = l["dcr_ohm_max_25c"] * p["power_model"]["copper_hot_factor"] if worst else l["dcr_ohm_typ_25c"]
    lh = l["l_h"] * (1 - l["tolerance_fraction"]) if worst else l["l_h"]
    f_ripple = b["frequency_hz_min"] if worst else b["frequency_hz"]
    f_switch = b["frequency_hz_max"] if worst else b["frequency_hz"]
    if pvin <= il * (r_hs - r_ls):
        raise ValueError(f"no operating point at {pvin:.3f} V converter input")
    duty = (vout + il * (r_ls + dcr)) / (pvin - il * (r_hs - r_ls))
    dc = min(duty, 1.0)
    ripple = vout * (1 - dc) / (lh * f_ripple)
    irms2 = il ** 2 + ripple ** 2 / 12
    return duty, ripple, {
        "buck_conduction": irms2 * (dc * r_hs + (1 - dc) * r_ls),
        "inductor_dcr": irms2 * dcr,
        "buck_switching_estimate": pvin * il * est["buck_transition_s"] * f_switch
        + 2 * est["buck_dead_time_s"] * f_switch * est["body_diode_v"] * il + est["buck_gate_drive_w"],
        "inductor_core_estimate": est["inductor_core_loss_w"],
        "buck_quiescent": pvin * (b["nonswitching_iq_a_max"] if worst else b["nonswitching_iq_a_typ"]),
    }


def converter_crosscheck(p: dict) -> dict:
    """Same converter terms at the manufacturer's typical-curve condition, for comparison only."""
    est = p["estimates"]
    vout, i = est["crosscheck_vout_v"], est["crosscheck_i_a"]
    _, _, losses = buck_losses(p, est["crosscheck_vin_v"], vout, i, "typical")
    model = vout * i / (vout * i + sum(losses.values()))
    return {"model_estimate": model, "manufacturer_typical_read": est["crosscheck_typical_curve_read"],
            "difference": model - est["crosscheck_typical_curve_read"],
            "condition": f"{est['crosscheck_vin_v']:g} V to {vout:g} V, {i:g} A, typical corner, this inductor"}


def operating_point(p: dict, fet: dict, vin: float, vf: float, i_laser: float, corner: str) -> dict:
    """Solve the averaged steady state at connector voltage `vin`; `regulating` is False beyond 100% duty."""
    if corner not in CORNERS:
        raise ValueError(f"unknown corner {corner!r}")
    worst = corner == "maximum"
    b, m, d, e, vm = p["buck"], p["power_model"], p["disconnect"], p["output_energy"], p["voltage_monitor"]
    hot = d["r_hot_multiplier_sensitivity"] if worst else 1.0
    v_term = vf + i_laser * m["laser_wiring_ohm"]
    r_out = output_resistance(p, fet, v_term, corner)
    vbuck = v_term + i_laser * r_out
    # VBUCK-side loads: bleeder, P-FET gate pull-up (gate held at ground while on) and OV divider.
    i_aux = vbuck * (1 / e["bleeder_ohm"] + 1 / d["gate_pullup_ohm"] + 1 / (vm["ov_top_ohm"] + vm["ov_bottom_ohm"]))
    il = i_laser + i_aux
    i_ctrl = p["control"]["design_current_a"]
    r_uv = vm["uv_top_ohm"] + vm["uv_bottom_ohm"]
    iin, pvin = il * vbuck / vin, vin
    for _ in range(200):
        # Reverse P-FET gate is grounded, so |Vgs| = VBAT_PROTECTED (previous iterate).
        r_rev = fet_r(d["reverse"], pvin, corner) * hot
        pvin = vin - iin * (m["input_path_ohm_allocation"] + r_rev)  # PVIN = VBAT_PROTECTED = UV sense node
        duty, ripple, losses_buck = buck_losses(p, pvin, vbuck, il, corner)
        new = (vbuck * il + sum(losses_buck.values())) / pvin + i_ctrl + pvin / r_uv
        converged = abs(new - iin) <= 1e-13 * max(1.0, new)
        iin = new
        if converged:
            break
    else:
        raise ValueError("operating point did not converge")
    duty_max = 1 - b["min_off_s_max"] * (b["frequency_hz_max"] if worst else b["frequency_hz"])
    r_shunt = p["current_sense"]["shunt_ohm"] * (1 + (shunt_error(p) if worst else 0.0))
    r_fet = r_out - r_shunt - m["output_copper_ohm_allocation"]
    losses = {
        "input_path_allocation": iin ** 2 * m["input_path_ohm_allocation"],
        "reverse_fet": iin ** 2 * r_rev,
        **losses_buck,
        "shunt": i_laser ** 2 * r_shunt,
        "output_fet": i_laser ** 2 * r_fet,
        "output_copper_allocation": i_laser ** 2 * m["output_copper_ohm_allocation"],
        "vbuck_aux_loads": vbuck * i_aux,
        "control_and_uv_divider": pvin * (i_ctrl + pvin / r_uv),
    }
    p_out = i_laser * v_term
    p_in = vin * iin
    return {"corner": corner, "output_fet": fet["mpn"], "vin_v": vin, "vf_v": vf, "i_laser_a": i_laser,
            "v_terminal_v": v_term, "vbuck_v": vbuck, "pvin_v": pvin, "duty": duty, "duty_max": duty_max,
            "regulating": duty <= duty_max, "i_in_a": iin, "ripple_a_pp": ripple,
            "p_out_w": p_out, "p_in_w": p_in, "losses_w": losses,
            "energy_balance_w": p_in - p_out - sum(losses.values()),
            "efficiency_estimate": p_out / p_in}


def dropout_v(p: dict, fet: dict, vf: float, i_laser: float) -> float:
    """Lowest connector voltage that still regulates at the maximum-resistance corner (duty = 1)."""
    t = p["targets"]
    lo, hi = p["buck"]["input_operating_v_min"], t["input_v_max"]
    if not operating_point(p, fet, hi, vf, i_laser, "maximum")["regulating"]:
        raise ValueError("no regulation even at maximum input")
    for _ in range(80):
        mid = (lo + hi) / 2
        try:
            ok = operating_point(p, fet, mid, vf, i_laser, "maximum")["regulating"]
        except ValueError:
            ok = False
        lo, hi = (lo, mid) if ok else (mid, hi)
    return hi


def evaluate(p: dict, current_max_a: float, uv: dict, ov: dict) -> dict:
    """All operating points plus dropout, UV-sense and OVP false-trip margins for the selected FET."""
    t, m, d = p["targets"], p["power_model"], p["disconnect"]
    vfs = (t["laser_v_min"], t["laser_v_typ"], t["laser_v_max"])
    vins = (t["input_v_min"], t["input_v_nominal"], t["input_v_max"])
    points = [operating_point(p, c, vin, vf, t["current_a"], corner)
              for c in d["candidates"] for corner in CORNERS for vin in vins for vf in vfs]
    fet = output_fet(p, d["selected_output_mpn"])
    v_drop = dropout_v(p, fet, t["laser_v_max"], current_max_a)
    at_min = [operating_point(p, fet, t["input_v_min"], vf, current_max_a, "maximum") for vf in vfs]
    uv_sense_min = min(x["pvin_v"] for x in at_min)
    # Highest normal VBUCK: maximum diode at the normal transient peak, steepest assumed diode slope.
    i_pk = t["normal_peak_a"]
    vf_pk = t["laser_v_max"] + max(p["loop"]["load_incremental_ohm_sweep"]) * (i_pk - t["current_a"])
    v_term_pk = vf_pk + i_pk * m["laser_wiring_ohm"]
    vbuck_pk = v_term_pk + i_pk * output_resistance(p, fet, v_term_pk, "maximum")
    nominal = next(x for x in points if x["output_fet"] == fet["mpn"] and x["corner"] == "typical"
                   and x["vin_v"] == t["input_v_nominal"] and x["vf_v"] == t["laser_v_typ"])
    vgs_min = gate_fraction(p) * min(x["v_terminal_v"] for x in points if x["output_fet"] == fet["mpn"])
    # Highest normal |Vgs| (OVP maximum on the source) must stay below the clamp; a fault is clamped.
    vgs_normal_max = gate_fraction(p) * ov["max_v"]
    vgs_fault = min(t["input_v_max"], d["gate_clamp_vz_v_max"])
    vi_points = [operating_point(p, fet, t["input_v_nominal"], vf, i, corner)
                 for i, vf in t["laser_vi_points"] for corner in CORNERS]
    return {
        "operating_points": points,
        "owner_vi_points": vi_points,
        "selected_output_mpn": fet["mpn"],
        "dropout": {"connector_v_at_vf_max_i_max": v_drop, "current_a": current_max_a,
                    "margin_v": t["input_v_min"] - v_drop, "required_margin_v": m["dropout_margin_v_allocation"],
                    "ok": t["input_v_min"] - v_drop >= m["dropout_margin_v_allocation"]},
        "uv": {"sense_min_v_at_input_min": uv_sense_min, "falling_max_v": uv["max_v"], "falling_min_v": uv["min_v"],
               "margin_v": uv_sense_min - uv["max_v"], "required_margin_v": m["uv_margin_v_allocation"],
               "floor_v": t["pack_cutoff_floor_v"],
               "ok": uv_sense_min - uv["max_v"] >= m["uv_margin_v_allocation"] and uv["min_v"] >= t["pack_cutoff_floor_v"]},
        "ov": {"vbuck_normal_peak_v": vbuck_pk, "rising_min_v": ov["min_v"], "margin_v": ov["min_v"] - vbuck_pk,
               "required_margin_v": m["ov_margin_v_allocation"],
               "ok": ov["min_v"] - vbuck_pk >= m["ov_margin_v_allocation"]},
        "gate_drive": {"output_fet_vgs_abs_min_v": vgs_min, "output_fet_vgs_abs_normal_max_v": vgs_normal_max,
                       "clamp_vz_v_min": d["gate_clamp_vz_v_min"],
                       "output_fet_vgs_abs_fault_v": vgs_fault, "output_fet_gate_rating_v": fet["gate_rating_v_abs"],
                       "reverse_fet_vgs_abs_max_v": t["input_v_max"], "reverse_fet_gate_rating_v": d["reverse"]["gate_rating_v_abs"],
                       "ok": vgs_normal_max < d["gate_clamp_vz_v_min"] and vgs_fault < fet["gate_rating_v_abs"]
                       and t["input_v_max"] < d["reverse"]["gate_rating_v_abs"]},
        "efficiency": {"estimate_at_nominal": nominal["efficiency_estimate"], "target": t["efficiency_fraction"],
                       "condition": f"{t['input_v_nominal']:g} V input, {t['laser_v_typ']:g} V diode, {t['current_a']:g} A, typical corner",
                       "meets_target": nominal["efficiency_estimate"] >= t["efficiency_fraction"]},
        "converter_crosscheck": converter_crosscheck(p),
        "max_energy_balance_error_w": max(abs(x["energy_balance_w"]) for x in points),
        "all_regulating": all(x["regulating"] for x in points),
        "qualification": "ESTIMATE/ALLOCATION model: switching/core terms are estimates, copper/fuse/connector are limits to meet",
    }
