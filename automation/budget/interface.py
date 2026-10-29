"""Budget-2S default-off interface: static levels, loads and supply sequencing (DD-32).

Fault line nFAULT (wired-AND, = SN74HCS74 CLR) and latch output ARM_Q drive two series N-MOSFET
pairs: N1/N2 pull the output P-FET gate, N3/N4 pull the gate of P1, which sources the TPS54821 EN
divider from VCTRL. N5 (firmware permit) holds nFAULT low by default. Each check compares a computed
worst-case node value with the limit it must meet. Leakage uses explicit allocations, and latch
thresholds between specified supply rows use labelled interpolation. Static only: timing, fault
energy and single-fault behaviour remain BUD-SAFE-01.
"""
from __future__ import annotations


def interp(x: float, xs: list, ys: list) -> float:
    """Piecewise-linear interpolation inside the specified rows; extrapolation is refused."""
    if not xs[0] <= x <= xs[-1]:
        raise ValueError(f"{x:.4f} V is outside the specified supply rows {xs[0]}...{xs[-1]} V")
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise ValueError("supply rows must be increasing")


def check(name: str, value: float, limit: float, kind: str, unit: str, basis: str) -> dict:
    margin = limit - value if kind == "max" else value - limit
    return {"check": name, "value": value, "limit": limit, "kind": kind, "unit": unit,
            "margin": margin, "ok": margin >= 0, "basis": basis}


def parallel(a: float, b: float) -> float:
    return a * b / (a + b)


def evaluate(p: dict, rail: tuple[float, float], gate: dict) -> dict:
    """Static default-off checks over the control-rail screen `rail` (min, max)."""
    f, b, d, c, t = p["interface"], p["buck"], p["disconnect"], p["control"], p["targets"]
    lo, hi = rail
    m, delta = f["logic_margin_v"], f["latch_vo_delta_v"]
    vt_pos = lambda vcc: interp(vcc, f["latch_vt_vcc_v"], f["latch_vt_pos_v_max"])
    vt_neg = lambda vcc: interp(vcc, f["latch_vt_vcc_v"], f["latch_vt_neg_v_min"])
    nmos_off = f["nmos_vth_v_min"] - m
    out = []

    # nFAULT leakage: datasheet maxima must fit the allocations used below.
    loads_leak = sum(x["leak_a_max"] * x["count"] for x in f["fault_loads"])
    sinks_leak = sum(x["leak_a_max"] * x["count"] for x in f["fault_sinks"])
    out += [check("nFAULT leakage out of node, datasheet sum", sinks_leak + loads_leak,
                  f["fault_leak_out_a_allocation"], "max", "A", "25 C maxima of all sinks and loads"),
            check("nFAULT leakage into node, datasheet sum", loads_leak,
                  f["fault_leak_in_a_allocation"], "max", "A", "25 C maxima of all inputs")]

    r_pu = f["fault_pullup_ohm"] + f["interlock_loop_ohm_max"]
    r_pd = f["fault_pulldown_ohm"]
    for vcc in (lo, hi):
        v_high = (vcc / r_pu - f["fault_leak_out_a_allocation"]) / (1 / r_pu + 1 / r_pd)
        need = max(vt_pos(vcc), f["nmos_vgs_for_r_v"], f["mcu_vih_fraction"] * vcc) + m
        out.append(check(f"nFAULT high (no fault) at VCTRL {vcc:.4f} V", v_high, need, "min", "V",
                         "HCS74 VT+ (interpolated), N2/N4 RDS drive, MCU VIH; leakage allocation"))
    low_limit = lambda vcc: min(vt_neg(vcc), f["nmos_vth_v_min"], f["mcu_vil_fraction"] * vcc) - m
    out.append(check("nFAULT with interlock loop open", f["fault_leak_in_a_allocation"] * r_pd,
                     low_limit(lo), "max", "V", "pulldown against input-leakage allocation"))

    vit_minus = c["supervisor_threshold_v"]
    vit_lo, vit_hi = vit_minus * (1 - f["supervisor_accuracy_fraction"]), vit_minus * (1 + f["supervisor_accuracy_fraction"])
    for s in f["fault_sinks"]:
        r_eq = s["r_ohm_max"] if "r_ohm_max" in s else s["vol_v"] / s["at_a"]
        supervisor = s["part"].startswith("TLV803")
        # The supervisor asserts while VCTRL is below its threshold; the others assert on a normal rail.
        for vcc in ((f["supervisor_vdd_min_v"], vit_hi) if supervisor else (lo, hi)):
            v_low = r_eq * (vcc / f["fault_pullup_ohm"] + f["fault_leak_in_a_allocation"])
            in_latch_range = vcc >= f["latch_vcc_min_v"]
            limit = low_limit(vcc) if in_latch_range else nmos_off
            out.append(check(f"nFAULT low, {s['part']} asserting at VCTRL {vcc:.4f} V", v_low, limit, "max", "V",
                             f"{s['source']}; VOL scaled linearly (ASSUMPTION)"
                             + ("" if in_latch_range else "; latch unspecified, N2/N4 off only")))

    # Latch output ARM_Q: two gate networks only, inside the 20 uA guaranteed-level condition.
    g_r, g_pd, igss = f["nmos_gate_series_ohm"], f["nmos_gate_pulldown_ohm"], f["nmos_igss_a_max"]
    i_q = f["latch_driven_gates"] * (hi / (g_r + g_pd) + igss)
    out.append(check("ARM_Q load current", i_q, f["latch_io_a_max"], "max", "A", "BUD-19 levels hold only at |IO| <= 20 uA"))
    out.append(check("N1/N3 gate when armed", (lo - delta) * g_pd / (g_r + g_pd) - igss * parallel(g_r, g_pd),
                     f["nmos_vgs_for_r_v"] + m, "min", "V", "VOH >= VCC - 0.1 V; RDS specified at 1.8 V"))
    out.append(check("N1/N3 gate when cleared", delta + igss * parallel(g_r, g_pd), nmos_off, "max", "V",
                     "VOL <= 0.1 V plus gate leakage"))

    # Output P-FET: off by its pull-up against the series-pair leakage; on with the gate pulled down.
    fet = next(x for x in d["candidates"] if x["mpn"] == d["selected_output_mpn"])
    leak = f["switch_leak_a_allocation"]
    out.append(check("Series pair leakage, datasheet", f["nmos_idss_a_max"], leak, "max", "A", "LEAD-04 IDSS, 25 C"))
    out.append(check("Output P-FET |Vgs| when off", leak * d["gate_pullup_ohm"], fet["vth_v_min_abs"] - m, "max", "V",
                     "pull-up to VBUCK against the leakage allocation"))
    i_pu = t["input_v_max"] / d["gate_pullup_ohm"]
    out.append(check("Output P-FET |Vgs| when on", gate["output_fet_vgs_abs_min_v"] - 2 * i_pu * f["nmos_r_ohm_max"],
                     2.5 + m, "min", "V", "gate-divider fraction of minimum VBUCK; 2.5 V resistance condition"))
    out.append(check("Output P-FET |Vgs| at OVP maximum, clamp off", gate["output_fet_vgs_abs_normal_max_v"],
                     gate["clamp_vz_v_min"] - m, "max", "V", "BZX585-C6V2 minimum VZ (PREORDER-11)"))
    out.append(check("Output P-FET |Vgs| at a switch-short, clamped", gate["output_fet_vgs_abs_fault_v"],
                     gate["output_fet_gate_rating_v"] - m, "max", "V", "clamp maximum VZ against the gate rating"))
    out.append(check("Reverse P-FET |Vgs| at maximum pack voltage", gate["reverse_fet_vgs_abs_max_v"],
                     gate["reverse_fet_gate_rating_v"] - m, "max", "V", "gate grounded; no clamp"))
    out.append(check("N1/N2 drain voltage at a buck switch-short", t["input_v_max"], f["nmos_vds_rating_v"], "max", "V",
                     "VBUCK can reach the pack voltage"))

    # P1 and the TPS54821 EN divider.
    r1, r2 = f["en_series_ohm"], f["en_pulldown_ohm"]
    ratio, r_par = r2 / (r1 + r2), parallel(r1, r2)
    out.append(check("P1 |Vgs| when off", (leak + f["pmos_igss_a_max"]) * f["pmos_gate_pullup_ohm"],
                     f["pmos_vth_v_min_abs"] - m, "max", "V", "BUD-23 VGS(th) against leakage allocation"))
    p1_vgs = lo - 2 * (lo / f["pmos_gate_pullup_ohm"]) * f["nmos_r_ohm_max"]
    out.append(check("P1 |Vgs| when on", p1_vgs, f["pmos_vgs_for_r_v"] + m, "min", "V", "RDS specified at -2.5 V"))
    out.append(check("P1 gate-source voltage rating", hi, f["pmos_gate_rating_v"], "max", "V", "BUD-23 VGSS"))
    i_en = lo / (r1 + r2)
    out.append(check("EN when armed", (lo - i_en * f["pmos_r_ohm_max"]) * ratio, b["en_rising_v_max"] + f["en_margin_v"],
                     "min", "V", "BUD-01 p.5 rising maximum; internal pull-up ignored (it only helps)"))
    i_pullup = f["en_pullup_factor_min"] * (b["en_pullup_a_typ"] + b["en_hysteresis_a_typ"])
    out.append(check("EN absolute maximum", hi * ratio + i_pullup * r_par, b["en_abs_max_v"], "max", "V", "BUD-01 p.3"))
    tolerated = (b["en_falling_v_min"] - f["en_margin_v"]) / r2
    out.append(check("EN pull-up tolerated when disarmed (x typical)", tolerated / b["en_pullup_a_typ"],
                     f["en_pullup_factor_min"], "min", "x", "BUD-01 gives the pull-up as typical only"))
    v_guard = f["supervisor_vdd_min_v"]
    out.append(check(f"EN with any logic state at VCTRL <= {v_guard:g} V",
                     v_guard * ratio + f["en_pullup_factor_min"] * b["en_pullup_a_typ"] * r_par,
                     b["en_falling_v_min"] - f["en_margin_v"], "max", "V",
                     "P1 can only source VCTRL; holds below the supervisor's specified range"))

    # Supervisor window: asserts before the latch/MCU leave their ranges, never on a healthy rail.
    vit_plus_hi = vit_hi * (1 + f["supervisor_hysteresis_fraction_max"])
    out.append(check("Supervisor falling threshold minimum", vit_lo,
                     max(f["latch_vcc_min_v"], f["mcu_vdd_min_at_clock_v"]) + f["supervisor_margin_v"], "min", "V",
                     "HCS74 2.0 V and ATtiny 10 MHz 2.7 V minimum supplies"))
    out.append(check("Supervisor release threshold maximum", vit_plus_hi, lo - f["supervisor_margin_v"], "max", "V",
                     "control-rail screen minimum"))

    # Firmware permit: N5 inhibits by default (MCU reset or tristate); the MCU must drive it low.
    r_mcu = f["mcu_vol_v"] / f["mcu_drive_test_a"]
    out.append(check("N5 gate with MCU pin tristated", lo - (f["mcu_pin_leak_a_assumed"] + igss) * f["inhibit_gate_pullup_ohm"],
                     f["nmos_vgs_for_r_v"] + m, "min", "V", "default inhibit; MCU leakage ASSUMPTION"))
    out.append(check("N5 gate with MCU permitting", r_mcu * (hi / f["inhibit_gate_pullup_ohm"] + igss), nmos_off, "max", "V",
                     "PREORDER-08 VOL scaled linearly (ASSUMPTION)"))
    # MCU arm edge into the latch clock input.
    clk_leak = next(x["leak_a_max"] for x in f["fault_loads"] if x["part"].startswith("SN74HCS74"))
    r_mcu_h = f["mcu_voh_drop_v"] / f["mcu_drive_test_a"]
    out.append(check("Latch CLK high from MCU", lo - r_mcu_h * clk_leak, vt_pos(lo) + m, "min", "V",
                     "PREORDER-08 VOH scaled linearly (ASSUMPTION); HCS74 VT+ interpolated"))
    out.append(check("Latch CLK low from MCU", r_mcu * clk_leak, vt_neg(lo) - m, "max", "V",
                     "PREORDER-08 VOL scaled linearly (ASSUMPTION); HCS74 VT- interpolated"))

    # Back-power: injected pin current must not lift an unpowered VCTRL to a gate threshold.
    out.append(check("Back-powered VCTRL", f["backpower_injection_a_allocation"] * f["vctrl_bleed_ohm"],
                     min(f["nmos_vth_v_min"], f["pmos_vth_v_min_abs"]) - m, "max", "V",
                     "injection allocation into the VCTRL bleed resistor"))

    volts = [x for x in out if x["unit"] == "V"]
    worst = min(volts, key=lambda x: x["margin"])
    return {"checks": out, "ok": all(x["ok"] for x in out), "failed": [x["check"] for x in out if not x["ok"]],
            "smallest_voltage_margin": {"check": worst["check"], "margin_v": worst["margin"]},
            "assumptions": ["HCS74 thresholds interpolated between the 2 V and 4.5 V rows",
                            "open-drain/MCU VOL and VOH scaled linearly from their test currents",
                            "leakage allocations cover 25 C datasheet maxima; hot leakage UNKNOWN",
                            "TPS54821 EN pull-up and ATtiny pin leakage are typical-only figures",
                            "interlock loop and back-power injection are allocations for later parts"]}
