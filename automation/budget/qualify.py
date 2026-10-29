"""Calculate the separate 2S candidate and report its manufacturing prerequisites.

This is engineering qualification, not a schematic/DRC substitute. UNKNOWN inputs
stay unknown. A conditional arithmetic check never closes a physical release gate.
Exit 0: all prerequisites met; 1: open/failed prerequisites; 2: invalid inputs.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from budget import interface, power  # noqa: E402
from nubm44 import evidence  # noqa: E402
from nubm44.variants import BUDGET_VARIANT, sources_for  # noqa: E402

PARAMETERS = sources_for(BUDGET_VARIANT).parameters
OUT = ROOT / "reports/budget-2s"
REQUIRED_TOP = {"targets", "buck", "inductor", "current_sense", "backup", "voltage_monitor", "control",
                "disconnect", "interface", "output_energy", "power_model", "estimates", "loop", "procurement"}


def number(value, label: str, *, zero_ok: bool = False) -> float:
    """Reject UNKNOWN, booleans, NaN, infinities and nonphysical numeric inputs."""
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label}: a finite number is required, got {value!r}")
    value = float(value)
    if not math.isfinite(value) or value < 0 or (value == 0 and not zero_ok):
        raise ValueError(f"{label}: invalid physical value {value!r}")
    return value


def unknowns(value, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in unknowns(v, f"{prefix}.{k}".strip("."))]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in unknowns(v, f"{prefix}[{i}]" )]
    return [prefix] if value == "UNKNOWN" else []


def validate_parameters(p: dict) -> None:
    if not isinstance(p, dict) or p.get("schema") != "nubm44-budget-parameters.v1":
        raise ValueError("missing/unsupported budget parameter schema")
    if missing := REQUIRED_TOP - p.keys():
        raise ValueError(f"missing sections: {sorted(missing)}")
    if p.get("meta", {}).get("variant") != BUDGET_VARIANT:
        raise ValueError("parameters are not for budget-2s")
    for section in REQUIRED_TOP:
        if not isinstance(p[section], dict):
            raise ValueError(f"{section}: expected a mapping")
    for section, keys in {
        "targets": ("current_a", "laser_v_min", "laser_v_max", "input_v_min", "input_v_max"),
        "buck": ("frequency_hz_min", "frequency_hz", "frequency_hz_max", "reference_v_min", "reference_v_max"),
        "inductor": ("l_h",),
        "current_sense": ("gain", "shunt_ohm", "fb_top_ohm", "fb_bottom_ohm"),
        "backup": ("limit_resistor_ohm", "limit_source_a_min", "limit_source_a_max"),
        "output_energy": ("bulk_cap_f_min_analysis", "bulk_cap_f_max_analysis", "bleeder_ohm"),
    }.items():
        for key in keys:
            number(p[section][key], f"{section}.{key}")
    # Validate every recorded numeric quantity as well, including nested candidates.
    def visit(value, label=""):
        if isinstance(value, dict):
            for key, v in value.items():
                visit(v, f"{label}.{key}".strip("."))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                visit(v, f"{label}[{i}]")
        elif isinstance(value, (int, float)):
            number(value, label, zero_ok=True)
            if "fraction" in label and not 0 <= value < 1:
                raise ValueError(f"{label}: fraction must be in [0, 1)")
    visit(p)
    for section, lo, hi in [
        ("targets", "input_v_min", "input_v_max"),
        ("targets", "laser_v_min", "laser_v_max"),
        ("buck", "reference_v_min", "reference_v_max"),
        ("buck", "frequency_hz_min", "frequency_hz_max"),
        ("output_energy", "bulk_cap_f_min_analysis", "bulk_cap_f_max_analysis"),
    ]:
        if p[section][lo] > p[section][hi]:
            raise ValueError(f"{section}: {lo} exceeds {hi}")
    if p["backup"]["delay"] != "FLOAT" or p["backup"]["latch"] != "HIGH":
        raise ValueError("this calculation requires fast FLOAT delay and HIGH latched INA300")
    if p["backup"]["enable"] != "VCTRL":
        raise ValueError("independent backup must be hard enabled, not firmware controlled")
    if p["backup"]["noise_adjustment_v"] != 0.0005:
        raise ValueError("INA300 fast-mode calculation requires the BUD-06 500 uV NAF")
    if p["voltage_monitor"]["ov_sense_net"] != "VBUCK":
        raise ValueError("open-load study requires OVP sensing upstream of the disconnect")
    if p["disconnect"]["topology"] != "single_pmos_source_at_vbuck":
        raise ValueError("power model assumes one output P-FET with its source at VBUCK (DD-31)")
    power.output_fet(p, p["disconnect"]["selected_output_mpn"])


def control_rail(p: dict) -> tuple[float, float]:
    c, t = p["control"], p["targets"]
    # Conservative additive screening; full rail load/line/thermal analysis remains open.
    delta = max(abs(t[v] - c["supply_line_test_v"]) for v in ("input_v_min", "input_v_max"))
    error = c["supply_regulation_fraction_full_temp"] + c["supply_load_fraction_max"]
    error += delta * c["supply_line_fraction_per_v_max"]
    return c["supply_v"] * (1 - error), c["supply_v"] * (1 + error)


def current_bounds(p: dict) -> dict:
    t, s, b = p["targets"], p["current_sense"], p["buck"]
    dt = max(abs(t[k] - 25) for k in ("board_c_min", "board_c_max"))
    gain_error = s["gain_error_fraction"] + s["gain_drift_fraction_per_c"] * dt
    shunt_error = s["shunt_tolerance_fraction"] + s["shunt_tcr_fraction_per_c"] * s["shunt_delta_c_from_25"]
    divider_error = s["fb_resistor_tolerance_fraction"]
    divider_error += s["fb_resistor_tcr_fraction_per_c"] * s["fb_resistor_delta_c_from_25"]
    alpha = lambda top, bottom: bottom / (top + bottom)
    ratios = [alpha(s["fb_top_ohm"] * (1 + a * divider_error),
                    s["fb_bottom_ohm"] * (1 + z * divider_error))
              for a, z in itertools.product((-1, 1), repeat=2)]
    supply_delta = max(abs(v - s["offset_test_supply_v"]) for v in control_rail(p))
    cm_delta = max(abs(t[k] - s["offset_test_common_mode_v"]) for k in ("laser_v_min", "laser_v_max"))
    offset = s["offset_v_max_25c"] + s["offset_drift_v_per_c_max"] * dt
    offset += supply_delta * s["psrr_v_per_v_max"] + cm_delta * 10 ** (-s["cmrr_db_min"] / 20)
    values = [(vref / ratio / (s["gain"] * (1 + ge * gain_error)) - os * offset)
              / (s["shunt_ohm"] * (1 + re * shunt_error))
              for vref, ratio, ge, os, re in itertools.product(
                  (b["reference_v_min"], b["reference_v_max"]),
                  (min(ratios), max(ratios)), (-1, 1), (-1, 1), (-1, 1))]
    nominal = b["reference_v"] / alpha(s["fb_top_ohm"], s["fb_bottom_ohm"]) / s["gain"] / s["shunt_ohm"]
    return {"nominal_a": nominal, "min_a": min(values), "max_a": max(values),
            "offset_envelope_v": offset, "shunt_error_fraction": shunt_error,
            "conditional_accuracy_ok": min(values) >= t["current_a"] * (1 - t["accuracy_fraction"])
            and max(values) <= t["current_a"] * (1 + t["accuracy_fraction"]),
            "qualification": "CONDITIONAL: exact divider MPNs and hot shunt temperature are not verified"}


def backup_bounds(p: dict, current: dict) -> dict:
    b, t, s = p["backup"], p["targets"], p["current_sense"]
    dt = max(abs(t[k] - 25) for k in ("board_c_min", "board_c_max"))
    offset = b["compensated_offset_v_abs_max"] + dt * b["offset_drift_v_per_c_max"]
    offset += max(abs(v - 3.3) for v in control_rail(p)) * b["psrr_v_per_v_max"]
    offset += max(abs(t[k] - 12) for k in ("laser_v_min", "laser_v_max")) * 10 ** (-b["cmrr_db_min"] / 20)
    # Include requested resistor drift, not just its room-temperature tolerance.
    r_error = b["resistor_tolerance_fraction"] + b["resistor_tcr_fraction_per_c"] * dt
    sh_error = current["shunt_error_fraction"]
    values = [(ilim * b["limit_resistor_ohm"] * (1 + re * r_error)
               - b["noise_adjustment_v"] + os * offset)
              / (s["shunt_ohm"] * (1 + se * sh_error))
              for ilim, re, os, se in itertools.product(
                  (b["limit_source_a_min"], b["limit_source_a_max"]), (-1, 1), (-1, 1), (-1, 1))]
    nominal = (b["limit_source_a"] * b["limit_resistor_ohm"] - b["noise_adjustment_v"]) / s["shunt_ohm"]
    return {"nominal_a": nominal, "min_a": min(values), "max_a": max(values),
            "conditional_window_ok": min(values) >= t["backup_trip_a_min"] and max(values) <= t["backup_trip_a_max"],
            "detector_delay_s_typ": b["propagation_s_typ"], "total_shutdown_s_max": "UNKNOWN",
            "qualification": "CONDITIONAL: resistor MPN, response, shared-shunt and sense-fault study OPEN"}


def voltage_bounds(p: dict) -> dict:
    m, t = p["voltage_monitor"], p["targets"]
    out = {}
    for kind in ("uv", "ov"):
        top, bot = m[f"{kind}_top_ohm"], m[f"{kind}_bottom_ohm"]
        tol = m["resistor_tolerance_fraction"] + m["resistor_tcr_fraction_per_c"] * max(
            abs(t["board_c_min"] - 25), abs(t["board_c_max"] - 25))
        threshold = "falling" if kind == "uv" else "rising"
        vals = [(vth * (1 + top * (1 + a * tol) / (bot * (1 + b * tol)))
                 + sign * m[f"{kind}_input_bias_a_abs_max"] * top * (1 + a * tol))
                for vth, a, b, sign in itertools.product(
                    (m[f"{threshold}_threshold_v_min"], m[f"{threshold}_threshold_v_max"]),
                    (-1, 1), (-1, 1), (-1, 1))]
        out[kind] = {"nominal_v": m[f"{threshold}_threshold_v"] * (1 + top / bot),
                     "min_v": min(vals), "max_v": max(vals)}
    return out


def ripple(p: dict) -> dict:
    t, l, b = p["targets"], p["inductor"], p["buck"]
    lmin = l["l_h"] * (1 - l["tolerance_fraction"])
    # Vin/2 is the global maximum of Vo*(Vin-Vo)/Vin, irrespective of series losses.
    di = t["input_v_max"] / (4 * lmin * b["frequency_hz_min"])
    return {"l_h_tolerance_min_25c": lmin, "ripple_a_pp_global_bound": di,
            "peak_a_at_4a": t["current_a"] + di / 2,
            "rms_a_at_4a": math.sqrt(t["current_a"] ** 2 + di ** 2 / 12),
            "catalogue_isat_above_switch_limit": l["isat_a_20pct_l_drop"] >= b["high_side_current_limit_a_max"],
            "qualification": "ROOM-TEMPERATURE screening; hot/bias L, core loss and saturation response UNKNOWN"}


def calculate(p: dict) -> dict:
    validate_parameters(p)
    cc = current_bounds(p)
    vb = voltage_bounds(p)
    rr = ripple(p)
    pw = power.evaluate(p, cc["max_a"], vb["uv"], vb["ov"])
    itf = interface.evaluate(p, control_rail(p), pw["gate_drive"]["output_fet_vgs_abs_min_v"])
    e = p["output_energy"]
    vcap = vb["ov"]["max_v"]
    return {"schema": "nubm44-budget-qualification.v1", "variant": BUDGET_VARIANT,
            "stage": "ELECTRICAL_QUALIFICATION", "manufacturing_ready": False,
            "scope": "candidate calculations only; no budget schematic, PCB, firmware or bench validation",
            "control_rail_screen_v": list(control_rail(p)), "current": cc,
            "backup": backup_bounds(p, cc), "voltage_monitor": vb, "ripple": rr, "power": pw, "interface": itf,
            "energy": {"upstream_j_at_ov_max": 0.5 * e["bulk_cap_f_max_analysis"] * vcap ** 2,
                       "upstream_j_at_switch_short_8p4v": 0.5 * e["bulk_cap_f_max_analysis"] * p["targets"]["input_v_max"] ** 2,
                       "laser_side_j_cap_only_at_ov_max": 0.5 * e["laser_side_cap_f"] * vcap ** 2,
                       "bleed_s_to_target_from_ov_max": e["bleeder_ohm"] * (1 + e["bleeder_tolerance_fraction"])
                       * e["bulk_cap_f_max_analysis"] * math.log(vcap / e["discharge_to_v"]),
                       "bleeder_fault_w_at_8p4v": p["targets"]["input_v_max"] ** 2
                       / (e["bleeder_ohm"] * (1 - e["bleeder_tolerance_fraction"])),
                       "qualification": "capacitance envelope is an ASSUMPTION; peak/reconnection/inductive energy UNKNOWN"},
            "unknown_inputs": unknowns(p), "readiness": readiness(p, cc, pw, itf)}


def readiness(p: dict, cc: dict, pw: dict, itf: dict) -> list[dict]:
    """Computed gates: existing A/B PASS results cannot satisfy any budget gate."""
    def row(identifier, status, detail):
        return {"id": identifier, "status": status, "detail": detail}
    t, dr, uv, ov, eff = p["targets"], pw["dropout"], pw["uv"], pw["ov"], pw["efficiency"]
    small = itf["smallest_voltage_margin"]
    conditional = lambda ok: "CONDITIONAL" if ok else "FAIL"
    return [
        row("BUD-CALC-01", conditional(cc["conditional_accuracy_ok"]),
            "Setpoint tolerance screen; exact resistor MPNs and hot shunt envelope need qualification."),
        row("BUD-PWR-01", conditional(dr["ok"] and pw["all_regulating"]),
            f"Maximum-resistance model regulates {dr['current_a']:.4f} A at {t['laser_v_max']:g} V down to "
            f"{dr['connector_v_at_vf_max_i_max']:.4f} V input ({dr['margin_v']:.4f} V margin, "
            f"{dr['required_margin_v']:g} V required). Conditional on the input/output resistance allocations, "
            "boot-regulator level and low-side resistance below 12 V; thermal/bench dropout OPEN."),
        row("BUD-EFF-01", "CONDITIONAL" if eff["meets_target"] else "FAIL",
            f"Estimate {100 * eff['estimate_at_nominal']:.2f}% at {eff['condition']} versus "
            f"{100 * eff['target']:g}% target. " + ("Estimate only; bench efficiency decides." if eff["meets_target"]
            else "Owner decision: accept a lower budget target or change the architecture; bench efficiency decides.")),
        row("BUD-UV-01", conditional(uv["ok"]),
            f"UV falling {uv['falling_min_v']:.4f}–{uv['falling_max_v']:.4f} V versus loaded sense minimum "
            f"{uv['sense_min_v_at_input_min']:.4f} V at {t['input_v_min']:g} V input ({uv['margin_v']:.4f} V margin, "
            f"{uv['required_margin_v']:g} V required; floor {uv['floor_v']:g} V). Pack rating, firmware cutoff OPEN."),
        row("BUD-OV-01", conditional(ov["ok"]),
            f"OVP rising minimum {ov['rising_min_v']:.4f} V versus highest normal VBUCK {ov['vbuck_normal_peak_v']:.4f} V "
            f"at {t['normal_peak_a']:g} A ({ov['margin_v']:.4f} V margin). Open-load response and laser survival OPEN."),
        row("BUD-IF-01", conditional(itf["ok"]),
            f"{sum(x['ok'] for x in itf['checks'])}/{len(itf['checks'])} static default-off checks pass"
            + (f" (failed: {', '.join(itf['failed'])})" if itf["failed"] else "")
            + f"; smallest voltage margin {small['margin_v']:.4f} V ({small['check']}). Conditional on: "
            + "; ".join(itf["assumptions"]) + "."),
        row("BUD-SAFE-01", "OPEN", "Total fault response time and energy, output-FET turn-off, single and latent "
            "faults (power-on self-test), interlock cable faults and bench fault injection."),
        row("BUD-LOOP-01", "OPEN", "Preliminary small-signal model is separate; complete switching/fault and component-corner qualification remains open."),
        row("BUD-CAD-01", "OPEN", "Budget connectivity/symbols/placement/ERC/DRC/netlist evidence do not exist yet."),
        row("BUD-FW-01", "OPEN", "Budget MCU HAL/ADC/clock/reset/arming interface and target build are not qualified."),
        row("BUD-MFG-01", "OPEN", "Exact BOM, package/paste/thermal review, quote and checked exports are absent."),
        row("BUD-COST-01", "OPEN", "Complete 3/5-unit delivered GBP quotes UNKNOWN; GBP 180/300 are ceilings."),
        row("BUD-G-01", "OPEN", "No measured budget-board records. Gate G requires real dummy-load/thermal/fault data."),
    ]


def markdown(r: dict, p: dict) -> str:
    cc, oc, vm, rr, pw = (r[k] for k in ("current", "backup", "voltage_monitor", "ripple", "power"))
    targets, energy = p["targets"], p["output_energy"]
    efficiency_percent = targets["efficiency_fraction"] * 100
    lines = ["# Budget-2S electrical qualification", "",
             "Generated by `automation/budget/qualify.py`; do not hand-edit. Source: DD-30 / budget parameters.", "",
             "**ELECTRICAL_QUALIFICATION — NOT READY FOR FABRICATION.** This report applies only to budget-2s.",
             "Conditional calculations are not complete circuit verification. Existing A/B results do not apply.", "",
             "## Calculated candidate screens", "",
             "| Screen | Result | Qualification |", "|---|---|---|",
             f"| Current setpoint | {cc['nominal_a']:.4f} A nominal; {cc['min_a']:.4f}–{cc['max_a']:.4f} A envelope | {cc['qualification']} |",
             f"| Independent trip | {oc['nominal_a']:.4f} A nominal; {oc['min_a']:.4f}–{oc['max_a']:.4f} A envelope | {p['backup']['noise_adjustment_v']*1e6:g} µV NAF included; {oc['qualification']} |",
             f"| UVLO falling | {vm['uv']['nominal_v']:.4f} V nominal; {vm['uv']['min_v']:.4f}–{vm['uv']['max_v']:.4f} V | Hardware backstop below the loaded {targets['input_v_min']:g} V operating floor; margins below |",
             f"| Physical VBUCK OVP | {vm['ov']['nominal_v']:.4f} V nominal; {vm['ov']['min_v']:.4f}–{vm['ov']['max_v']:.4f} V | Upstream of disconnect; laser survival/response UNKNOWN |",
             f"| Buck ripple, 25 °C L tolerance / {p['buck']['frequency_hz_min']/1000:g} kHz minimum | ≤{rr['ripple_a_pp_global_bound']:.4f} A p-p; {rr['peak_a_at_4a']:.4f} A peak at {targets['current_a']:g} A average | {rr['qualification']} |",
             f"| Control rail additive screen | {r['control_rail_screen_v'][0]:.4f}–{r['control_rail_screen_v'][1]:.4f} V | LDO load budget, exact line anchor and brownout sequencing OPEN |", "",
             f"Current accuracy assumes the specified {p['current_sense']['fb_resistor_tolerance_fraction']*100:g}% / {p['current_sense']['fb_resistor_tcr_fraction_per_c']*1e6:g} ppm/°C resistors and the stated shunt-temperature",
             "envelope. They are procurement/thermal requirements, not verified purchased parts or temperatures.", "",
             "## Operating points, dropout and efficiency estimate", "",
             "Averaged steady-state model in `automation/budget/power.py`: connector → input allocation → reverse FET →",
             "TPS54821 → shunt → one output P-FET → board terminals (DD-31). The **typical** corner uses typical resistances",
             "at 25 °C; the **maximum** corner uses full-temperature TPS54821 maxima, FET 25 °C maxima × "
             f"{p['disconnect']['r_hot_multiplier_sensitivity']:g} (assumption), hot inductor DCR, minimum L and worst ripple frequency.",
             "Switching, dead-time, gate-drive and core terms are labelled `estimates`; copper, fuse and connector values are",
             "`power_model` allocations the BOM/layout must meet. Efficiency is board-terminal power over connector power.",
             f"The model's largest energy-balance error is {pw['max_energy_balance_error_w']:.1e} W.", "",
             "| Output FET | Corner | Input V | Diode V | Duty | Input A | Loss (W) | Efficiency estimate |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    lines += [f"| {x['output_fet']}{' (selected)' if x['output_fet'] == pw['selected_output_mpn'] else ''} | {x['corner']} | "
              f"{x['vin_v']:g} | {x['vf_v']:g} | {x['duty']:.4f} | {x['i_in_a']:.4f} | {x['p_in_w'] - x['p_out_w']:.4f} | "
              f"{100 * x['efficiency_estimate']:.2f}% |" for x in pw["operating_points"]]
    nominal = next(x for x in pw["operating_points"] if x["output_fet"] == pw["selected_output_mpn"]
                   and x["corner"] == "typical" and x["vin_v"] == targets["input_v_nominal"] and x["vf_v"] == targets["laser_v_typ"])
    dr, uv, ov, gd, eff = (pw[k] for k in ("dropout", "uv", "ov", "gate_drive", "efficiency"))
    lines += ["", f"Loss breakdown at the efficiency condition ({eff['condition']}, {pw['selected_output_mpn']}):", "",
              "| Term | W |", "|---|---:|"]
    lines += [f"| {k} | {v:.4f} |" for k, v in sorted(nominal["losses_w"].items(), key=lambda kv: -kv[1])]
    xc = pw["converter_crosscheck"]
    lines += ["", f"Estimate {100 * eff['estimate_at_nominal']:.2f}% versus the {efficiency_percent:g}% target: "
              + ("meets the target as an estimate only." if eff["meets_target"] else
                 "**below target**; owner decision required (DD-31).") + " Bench efficiency is the evidence of record.", "",
              f"Converter terms alone, {xc['condition']}: {100 * xc['model_estimate']:.2f}% versus an approximate read of "
              f"{100 * xc['manufacturer_typical_read']:.1f}% from BUD-01's typical curve ({100 * xc['difference']:+.2f} points).",
              "This is a plausibility check of the estimate terms, not a guarantee. It does not include the shunt, protection",
              "FETs, input path or control load.", "",
              "| Margin check (selected FET, maximum corner) | Result | Required |", "|---|---:|---:|",
              f"| Dropout: lowest regulating input at {targets['laser_v_max']:g} V / {dr['current_a']:.4f} A | {dr['connector_v_at_vf_max_i_max']:.4f} V; margin {dr['margin_v']:.4f} V | ≥{dr['required_margin_v']:g} V below {targets['input_v_min']:g} V |",
              f"| UV sense node at {targets['input_v_min']:g} V input versus UV falling maximum | {uv['sense_min_v_at_input_min']:.4f} V vs {uv['falling_max_v']:.4f} V; margin {uv['margin_v']:.4f} V | ≥{uv['required_margin_v']:g} V; UV minimum ≥{uv['floor_v']:g} V |",
              f"| Highest normal VBUCK at {targets['normal_peak_a']:g} A versus OVP rising minimum | {ov['vbuck_normal_peak_v']:.4f} V vs {ov['rising_min_v']:.4f} V; margin {ov['margin_v']:.4f} V | ≥{ov['required_margin_v']:g} V |",
              f"| Output P-FET \\|Vgs\\| (gate grounded) | ≥{gd['output_fet_vgs_abs_min_v']:.4f} V normal; {gd['output_fet_vgs_abs_fault_v']:g} V switch-short fault | rating ±{gd['output_fet_gate_rating_v']:g} V |",
              f"| Reverse P-FET \\|Vgs\\| maximum | {gd['reverse_fet_vgs_abs_max_v']:g} V | rating ±{gd['reverse_fet_gate_rating_v']:g} V |",
              "", "Gate ratings exclude plug and switching transients; a gate clamp is still OPEN. The output FET's",
              "exposed-drain land, paste and X-ray inspection review remain OPEN.", ""]
    itf = r["interface"]
    lines += ["## Default-off interface (static, DD-32)", "",
              "nFAULT is the wired-AND fault line and the latch CLR. Series N-MOSFET pairs N1/N2 (output P-FET gate) and",
              "N3/N4 (gate of P1, which sources the EN divider from VCTRL) each need ARM_Q **and** nFAULT high, so any",
              "asserted fault turns both outputs off without relying on the latch. N5 holds nFAULT low unless firmware",
              "drives its permit pin low. Worst cases use the control-rail screen "
              f"{r['control_rail_screen_v'][0]:.4f}–{r['control_rail_screen_v'][1]:.4f} V. Static only; timing and energy are BUD-SAFE-01.", "",
              "| Check | Worst case | Limit | Margin | Basis |", "|---|---:|---:|---:|---|"]
    lines += [f"| {x['check']} | {x['value']:.4g} {x['unit']} | {'≥' if x['kind'] == 'min' else '≤'}{x['limit']:.4g} {x['unit']} | "
              f"{'' if x['ok'] else '**FAIL** '}{x['margin']:.4g} {x['unit']} | {x['basis']} |" for x in itf["checks"]]
    lines += ["", "Assumptions: " + "; ".join(itf["assumptions"]) + ".", ""]
    en = r["energy"]
    lines += ["## Stored energy and discharge", "",
              f"At the assumed {energy['bulk_cap_f_max_analysis']*1e6:g} µF maximum: {1000*en['upstream_j_at_ov_max']:.4f} mJ at calculated OVP maximum,",
              f"or {1000*en['upstream_j_at_switch_short_8p4v']:.4f} mJ at a {targets['input_v_max']:g} V switch-short fault. The proposed {energy['laser_side_cap_f']*1e9:g} nF",
              f"laser-side capacitor alone stores {1e6*en['laser_side_j_cap_only_at_ov_max']:.4f} µJ at OVP maximum.",
              f"A {energy['bleeder_ohm']/1000:g} kΩ +{energy['bleeder_tolerance_fraction']*100:g}% bleeder takes {en['bleed_s_to_target_from_ov_max']:.4f} s to reach {energy['discharge_to_v']:g} V;",
              f"its -{energy['bleeder_tolerance_fraction']*100:g}% fault dissipation at {targets['input_v_max']:g} V is {en['bleeder_fault_w_at_8p4v']:.4f} W.",
              "Cable, diode and gate capacitance, inductive energy, FET delay/SOA and reconnect peak are UNKNOWN.",
              "Voltage and energy arithmetic do not establish laser safety. See the budget fault matrix.", "",
              "## Release prerequisites", "", "| ID | Status | Outstanding work |", "|---|---|---|"]
    lines.extend(f"| {x['id']} | {x['status']} | {x['detail']} |" for x in r["readiness"])
    lines += ["", "## Explicit UNKNOWN inputs", ""] + [f"- `{x}`" for x in r["unknown_inputs"]]
    lines += ["", "No quote, supplier stock, successful simulation, physical measurement or manufacturing release is inferred.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "qualification-evidence.json"
    # Invalidate old evidence before a potentially failing parse/calculation.
    manifest.unlink(missing_ok=True)
    try:
        p = yaml.safe_load(PARAMETERS.read_text(encoding="utf-8"))
        result = calculate(p)
    except (KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        print(f"budget-2s: INVALID INPUT: {exc}", file=sys.stderr)
        return 2
    jp, md = OUT / "qualification.json", OUT / "qualification.md"
    jp.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    md.write_text(markdown(result, p), encoding="utf-8")
    evidence.write(evidence.build(
        "budget-qualification", inputs=[PARAMETERS, Path(__file__), Path(power.__file__), Path(interface.__file__),
            ROOT / "automation/nubm44/variants.py", ROOT / "automation/nubm44/evidence.py",
            ROOT / "research/sources/budget-driver-sources.md"],
        outputs=[jp, md], tools=evidence.python_tools(["PyYAML"])), manifest)
    problems = [x for x in result["readiness"] if x["status"] != "PASS"]
    for x in result["readiness"]:
        print(f"{x['id']}: {x['status']} — {x['detail']}")
    print(f"Budget only: {len(problems)} prerequisites unresolved; existing A/B gates unchanged.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
