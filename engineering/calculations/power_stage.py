"""NUBM44 driver power-stage calculations.

Reads engineering/design/parameters.yaml, evaluates the TPS552882 buck-boost stage at
every corner of battery voltage, diode forward voltage and temperature, and writes:

* engineering/calculations/power-stage-results.md   (human-readable report)
* engineering/calculations/power-stage-results.json (machine-readable, used by validation)
* engineering/calculations/plots/*.png

Every check records PASS/FAIL against an explicit limit; nothing is hard-coded as passing.
Run:  .venv\\Scripts\\python.exe engineering\\calculations\\power_stage.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44.calc import buckboost, copper, loop  # noqa: E402
from nubm44.calc.boost import LaserModel  # noqa: E402

OUT = Path(__file__).resolve().parent
PLOTS = OUT / "plots"
P = yaml.safe_load((ROOT / "engineering/design/parameters.yaml").read_text(encoding="utf-8"))

checks: list[dict] = []


def check(name: str, value: float, limit: float, kind: str, unit: str = "", note: str = "") -> bool:
    ok = value <= limit if kind == "max" else value >= limit
    checks.append({"check": name, "value": round(value, 4), "limit": limit, "kind": kind,
                   "unit": unit, "status": "PASS" if ok else "FAIL", "note": note})
    return ok


# ------------------------------------------------------------------ laser corners
def laser(corner: str, temp_c: float = 25.0) -> LaserModel:
    m = P["laser"]["vf_model"][corner]
    return LaserModel(v0=m["v0"] + P["laser"]["vf_tempco_v_per_k"] * (temp_c - 25.0), rd=m["rd"])


LASER_CORNERS = {
    "min_hot": laser("min", P["laser"]["case_temp_c"][1]),
    "typ_25C": laser("typ", 25.0),
    "max_cold": laser("max", P["laser"]["case_temp_c"][0]),
}
I_SET = P["current"]["i_set_a"]

# ------------------------------------------------------------------ setpoint
cv = P["converter"]
cm = P["components"]
fb = cm["fb_divider"]
k_div = fb["r_bot_ohm"] / (fb["r_top_ohm"] + fb["r_bot_ohm"])
gain_v_per_a = cm["shunt"]["r_ohm"] * cm["csa"]["gain"]
i_set_nominal = cv["vref_v"] / (k_div * gain_v_per_a)


def setpoint_for(i_target: float) -> dict:
    k = cv["vref_v"] / (i_target * gain_v_per_a)
    r_top_exact = fb["r_bot_ohm"] * (1 / k - 1)
    e96 = [10.0 * 10 ** (i / 96) for i in range(96)]
    decade = 10 ** math.floor(math.log10(r_top_exact))
    r_top = min((round(v * decade / 10, 1) for v in e96), key=lambda v: abs(v - r_top_exact))
    k_real = fb["r_bot_ohm"] / (r_top + fb["r_bot_ohm"])
    return {"i_target_a": i_target, "r_top_exact_ohm": round(r_top_exact, 1), "r_top_e96_ohm": r_top,
            "i_resulting_a": round(cv["vref_v"] / (k_real * gain_v_per_a), 4)}


# worst-case and RSS tolerance stack of the regulated current
tol = {
    "vref": cv["vref_tol_pct"],
    "shunt": cm["shunt"]["tol_pct"],
    "csa_gain": cm["csa"]["gain_err_pct"],
    "csa_offset": 100 * cm["csa"]["vos_v"] / (I_SET * cm["shunt"]["r_ohm"]),
    "fb_divider": 2 * fb["tol_pct"] * (1 - k_div),
    "shunt_tcr_50K": 75e-6 * 50 * 100,
}
tol_worst = sum(tol.values())
tol_rss = math.sqrt(sum(v * v for v in tol.values()))
check("Current setpoint worst-case tolerance", tol_worst, P["current"]["accuracy_target_pct"], "max", "%",
      "linear sum of VREF, shunt, CSA gain/offset, divider, shunt TCR over 50 K")
check("Nominal setpoint error", abs(i_set_nominal - I_SET) / I_SET * 100, 0.5, "max", "%")

# ISP/ISN backup limit (independent of CSA and firmware)
backup = [v / cm["shunt"]["r_ohm"] for v in cv["isp_isn_limit_v"]]
check("Backup current limit minimum above setpoint (no interference)", backup[0],
      I_SET * (1 + tol_worst / 100) * P["current"]["backup_margin_factor"], "min", "A",
      "ISP/ISN 48 mV min / shunt; must not clip normal regulation (margin factor: owner decision DD-36)")

# ------------------------------------------------------------------ operating points
r_rev = {"hot_4v": cm["q_reverse"]["rds_max_4v5"] * 1.25}


def rev_fet_rds(v_in: float) -> float:
    """SiSS23DN Rds(on) max interpolated between -2.5 V and -4.5 V gate drive, x1.3 for 85 C."""
    a, b = cm["q_reverse"]["rds_max_2v5"], cm["q_reverse"]["rds_max_4v5"]
    vg = min(max(v_in, 2.5), 4.5)
    return (a + (b - a) * (vg - 2.5) / 2.0) * 1.3


def bb_params(v_in: float) -> buckboost.BuckBoostParams:
    cout = cm["c_out"]
    cin = cm["c_in"]
    return buckboost.BuckBoostParams(
        r_input_path=rev_fet_rds(v_in) + P["pcb"]["model_copper_input_ohm"],   # FET + copper
        l_h=cm["inductor"]["l_h"],
        dcr=cm["inductor"]["dcr_typ_ohm"] * 1.2,               # copper at ~75 C
        core_loss_w=0.06,                                      # vendor calculator value UNKNOWN; estimate
        rds_q1=cm["q_buck"]["rds_max_4v5"] * 1.35,
        rds_q2=cm["q_buck"]["rds_max_4v5"] * 1.35,
        rds_q3=cv["rds_boost_hs_ohm"] * 1.4,
        rds_q4=cv["rds_boost_ls_ohm"] * 1.4,
        t_sw_boost=4e-9, t_sw_buck=12e-9,                      # integrated vs external (Qg 36 nC, 1 A driver)
        c_oss_leg=1.5e-9, t_deadtime=20e-9, vf_body=0.7,
        q_gate_buck=2 * cm["q_buck"]["qg_c"], q_gate_boost=15e-9, v_drive=5.0,
        i_q=cv["iq_a"], f_sw=cv["f_sw_hz"],
        r_shunt=cm["shunt"]["r_ohm"], r_output_path=P["pcb"]["model_copper_output_ohm"],
        esr_out=cout["esr_each_ohm"] / cout["count"], esr_in=cin["esr_each_ohm"] / cin["count"],
        p_aux=0.006, band=0.05)


V_IN_SWEEP = [2.83, 3.0, 3.3, 3.7, 4.0, 4.2]
points = []
for corner, lm in LASER_CORNERS.items():
    for v in V_IN_SWEEP:
        op = buckboost.solve(v, I_SET, lm, bb_params(v))
        d = op.as_dict()
        d["corner"] = corner
        points.append(d)

worst_iL = max(p["i_l_avg"] for p in points)
worst_pk = max(p["i_l_peak"] for p in points)
ilim_min = 330000 / cv["r_ilim_ohm"] * cv["ilim_tol"][0]
check("Average inductor current vs ILIM minimum (20 % margin)", worst_iL * 1.2, ilim_min, "max", "A",
      f"worst operating avg {worst_iL:.2f} A; ILIM min {ilim_min:.2f} A")
check("Peak inductor current vs Isat (30 % drop rating)", worst_pk, cm["inductor"]["isat_30pct_a"], "max", "A")
i_l_rms_worst = max(math.sqrt(p["i_l_avg"] ** 2 + p["ripple_pp"] ** 2 / 12) for p in points)
check("Inductor RMS current vs Irms (20 C rise)", i_l_rms_worst, cm["inductor"]["irms_20c_a"], "max", "A",
      "RMS = sqrt(avg^2 + ripple_pp^2 / 12) at the worst operating point")

eff = {(p["corner"], p["v_in"]): p["efficiency"] for p in points}
eta_4v = eff[("typ_25C", 4.0)]
eta_3v = eff[("typ_25C", 3.0)]
eta_3v_worst = min(eff[(c, 3.0)] for c in LASER_CORNERS)
ETA_TARGET = P["current"]["efficiency_target_pct"]
check(f"Efficiency at 4.0 V, typical diode (REQ-PWR-02 target >= {ETA_TARGET:g} %, owner deviations DD-26/DD-37)",
      eta_4v * 100, ETA_TARGET, "min", "%", "board-input to laser; estimate from loss model; brief asked > 95 %")
check("Efficiency at 3.0 V, worst diode corner (REQ-PWR-03 target >= 86 %)", eta_3v_worst * 100, 86.0, "min", "%")

# switching-time constraints
t = 1 / cv["f_sw_hz"]
max_boost_duty = max(1 - p["i_out"] / p["i_in"] for p in points if p["region"] == "boost")
check("Boost off-time vs minimum off-time", (1 - max_boost_duty) * t * 1e9, cv["min_off_time_boost_s"] * 1e9,
      "min", "ns")

# dissipation of key parts
pt_hot = max(points, key=lambda p: p["i_in"])
p_rev = pt_hot["losses"]["input_path_I2R"]
check("Reverse-polarity FET dissipation (worst point)", p_rev, cm["q_reverse"]["p_max_w"], "max", "W",
      "PowerPAK 1212-8 on 4-layer pour at ~60 K/W (estimate); limit is an owner decision (DD-36), bench thermal T-test decides")
p_shunt = I_SET ** 2 * cm["shunt"]["r_ohm"]
check("Shunt dissipation vs 50 % of rating", p_shunt, 0.5 * cm["shunt"]["p_rated_w"], "max", "W")
p_ic = max(p["losses"].get("q3_conduction", 0) + p["losses"].get("q4_conduction", 0)
           + p["losses"].get("boost_switching", 0) + p["losses"].get("deadtime", 0) for p in points)
tj_est = 50 + p_ic * 60
check("TPS552882 junction estimate at 50 C board (60 K/W assumed)", tj_est, 125, "max", "C",
      "RthJA 47.5 K/W on JEDEC board; 60 K/W assumed for the 22 mm board; verify by test")

# ------------------------------------------------------------------ dividers and thresholds
r1, r2 = cv["r_en_top_ohm"], cv["r_en_bot_ohm"]
v_on = cv["en_uvlo_v"] * (1 + r1 / r2)
v_off = v_on - cv["en_uvlo_hys_a"] * r1
check("Hardware UVLO falling threshold >= 2.80 V cell floor", v_off, 2.80, "min", "V")
check("Hardware UVLO falling threshold below firmware cut-off", v_off, P["battery"]["v_fw_cutoff_loaded"] - 0.05,
      "max", "V", "firmware must act first; hardware is the backstop")

v_out_max_normal = max(p["v_out_node"] for p in points)
ov_backstop_min = cm["ov_backstop_zener_v"] * 0.95 + 0.5
check("OV backstop trip (min) above normal maximum output", ov_backstop_min, v_out_max_normal + 0.5, "min", "V")

# ------------------------------------------------------------------ ripple and capacitors
c_out_eff = cm["c_out"]["count"] * cm["c_out"]["c_nom_f"] * cm["c_out"]["bias_retention"]
c_in_eff = cm["c_in"]["count"] * cm["c_in"]["c_nom_f"] * cm["c_in"]["bias_retention"]
worst_boost = max((p for p in points if p["region"] == "boost"), key=lambda p: p["i_in"])
d_w = 1 - worst_boost["i_out"] / worst_boost["i_in"]
v_ripple = worst_boost["i_out"] * d_w / (cv["f_sw_hz"] * c_out_eff)
i_ripple_laser = v_ripple / (LASER_CORNERS["typ_25C"].rd + cm["shunt"]["r_ohm"])
check("Laser current ripple (p-p) as % of setpoint", 100 * i_ripple_laser / I_SET, 10.0, "max", "%",
      "capacitive ripple / diode dynamic resistance; ESR adds a little")
i_cout_rms = worst_boost["i_in"] * math.sqrt(d_w * (1 - d_w))
check("Output capacitor RMS current per capacitor", i_cout_rms / cm["c_out"]["count"], 3.0, "max", "A",
      "0805 22 uF X5R typically rated 2-4 A at 10 K rise")

# ------------------------------------------------------------------ control loop
LOOP_CORNERS = []
for corner, lm in LASER_CORNERS.items():
    for v in (2.83, 3.7):
        op = next(p for p in points if p["corner"] == corner and p["v_in"] == v)
        if op["region"] != "boost":
            continue
        for rd_scale in (0.7, 1.0, 1.5):
            LOOP_CORNERS.append((corner, v, rd_scale, op))

loop_results = []
comp = P["compensation"]
for corner, v, rd_scale, op in LOOP_CORNERS:
    z_ac = LASER_CORNERS[corner].rd * rd_scale + cm["shunt"]["r_ohm"] + 0.012
    lp = loop.LoopParams(
        v_out=op["v_out_node"], i_out=op["i_out"], duty=1 - op["i_out"] / op["i_in"],
        l_h=cm["inductor"]["l_h"], c_out=c_out_eff, esr=cm["c_out"]["esr_each_ohm"] / cm["c_out"]["count"],
        z_ac=z_ac, f_sw=cv["f_sw_hz"], ri=cv["ri_equiv_ohm"], q_sampling=0.5,
        r_shunt=cm["shunt"]["r_ohm"], g_csa=cm["csa"]["gain"], k_div=k_div, f_csa=cm["csa"]["bw_hz"],
        gm_ea=cv["gea_s"], r_ea_out=cv["rea_ohm"], r_c=comp["r_c_ohm"], c_c=comp["c_c_f"], c_p=comp["c_p_f"])
    m = loop.margins(lp)
    loop_results.append({"corner": corner, "v_in": v, "rd_scale": rd_scale, "z_ac": round(z_ac, 4),
                         "f_cross_hz": m["f_cross_hz"], "phase_margin_deg": m["phase_margin_deg"],
                         "gain_margin_db": m["gain_margin_db"], "f_rhp_hz": m["f_rhp_hz"], "_m": m})

pm_min = min(r["phase_margin_deg"] for r in loop_results if r["phase_margin_deg"] is not None)
gm_vals = [r["gain_margin_db"] for r in loop_results if r["gain_margin_db"] is not None]
fc_max = max(r["f_cross_hz"] for r in loop_results if r["f_cross_hz"])
fr_min = min(r["f_rhp_hz"] for r in loop_results)
check("Current-loop phase margin (all corners)", pm_min, 50.0, "min", "deg")
if gm_vals:
    check("Current-loop gain margin (all corners)", min(gm_vals), 10.0, "min", "dB")
check("Crossover below RHP zero / 5", fc_max, fr_min / 5, "max", "Hz")
check("Crossover below CSA bandwidth / 3", fc_max, cm["csa"]["bw_hz"] / 3, "max", "Hz")

# ------------------------------------------------------------------ copper and battery
cu = {
    "input_8A_1oz_dT20_mm": copper.ipc2221_width_mm(8.3, 20, 1.0),
    "input_8A_2oz_dT20_mm": copper.ipc2221_width_mm(8.3, 20, 2.0),
    "output_4A_1oz_dT20_mm": copper.ipc2221_width_mm(4.4, 20, 1.0),
    "sheet_mohm_1oz_75C": copper.sheet_resistance_mohm(1.0, 75),
    "via_0p3_mohm": copper.via_resistance_mohm(0.3),
    "vias_for_8A_0p3": copper.vias_for_current(8.3, 0.3),
}
bat = P["battery"]
runtime = {}
for cell, mah in (("18650 3000 mAh", 3000), ("21700 4000 mAh", 4000)):
    p_in = I_SET * LASER_CORNERS["typ_25C"].vf(I_SET) / eff[("typ_25C", 3.7)]
    wh = mah / 1000 * 3.6 * 0.9            # 90 % of energy usable above the cut-off
    runtime[cell] = round(wh / p_in * 60, 1)

# ------------------------------------------------------------------ outputs
PLOTS.mkdir(parents=True, exist_ok=True)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for corner in LASER_CORNERS:
        vs = [p["v_in"] for p in points if p["corner"] == corner]
        es = [100 * p["efficiency"] for p in points if p["corner"] == corner]
        ax.plot(vs, es, marker="o", label=f"diode {corner}")
    ax.axhline(ETA_TARGET, ls="--", lw=0.8, color="grey"); ax.axhline(86, ls=":", lw=0.8, color="grey")
    ax.set_xlabel("Board input voltage (V)"); ax.set_ylabel("Efficiency (%)")
    ax.set_title(f"Estimated efficiency, TPS552882 buck-boost, {I_SET:.1f} A")
    ax.grid(alpha=0.3); ax.legend(); fig.tight_layout()
    fig.savefig(PLOTS / "efficiency_vs_vin.png", dpi=130); plt.close(fig)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    for r in loop_results:
        m = r["_m"]
        lbl = f'{r["corner"]} {r["v_in"]} V rd x{r["rd_scale"]}'
        a1.semilogx(m["f"], m["mag_db"], lw=0.9, label=lbl)
        a2.semilogx(m["f"], 180 + np.array(m["phase_deg"]), lw=0.9)
    a1.axhline(0, color="k", lw=0.6); a1.set_ylabel("Loop gain (dB)"); a1.grid(alpha=0.3, which="both")
    a2.set_ylabel("Phase margin trace (deg)"); a2.set_xlabel("Frequency (Hz)"); a2.grid(alpha=0.3, which="both")
    a1.legend(fontsize=6, ncol=2); a1.set_title("Laser-current loop (CSA into FB)")
    fig.tight_layout(); fig.savefig(PLOTS / "current_loop_bode.png", dpi=130); plt.close(fig)
except ImportError:  # pragma: no cover
    pass

results = {
    "inputs": "engineering/design/parameters.yaml",
    "setpoint": {"k_div": k_div, "i_set_nominal_a": i_set_nominal, "tolerance_pct": tol,
                 "worst_case_pct": tol_worst, "rss_pct": tol_rss,
                 "alternates": [setpoint_for(i) for i in P["current"]["alternates_a"] + [I_SET]],
                 "backup_limit_a": backup},
    "uvlo": {"v_on": v_on, "v_off": v_off},
    "operating_points": points,
    "loop": [{k: v for k, v in r.items() if k != "_m"} for r in loop_results],
    "ripple": {"c_out_eff_uF": c_out_eff * 1e6, "c_in_eff_uF": c_in_eff * 1e6, "v_out_ripple_pp": v_ripple,
               "laser_ripple_pp_a": i_ripple_laser, "i_cout_rms_total": i_cout_rms},
    "copper": cu,
    "runtime_min": runtime,
    "checks": checks,
}
(OUT / "power-stage-results.json").write_text(json.dumps(results, indent=1, default=float), encoding="utf-8")

# ------------------------------------------------------------------ markdown
L = ["# Power-stage calculation results", "",
     "Generated by `engineering/calculations/power_stage.py` from `engineering/design/parameters.yaml`.",
     "Values are design estimates from datasheet parameters and first-order loss models. They are not",
     "measurements. Gate G (physical validation) remains open until bench data exists.", "",
     "## Checks", "", "| Check | Value | Limit | Status | Note |", "|---|---|---|---|---|"]
for c in checks:
    lim = ("≤ " if c["kind"] == "max" else "≥ ") + f'{c["limit"]:g} {c["unit"]}'
    L.append(f'| {c["check"]} | {c["value"]:g} {c["unit"]} | {lim} | **{c["status"]}** | {c["note"]} |')
L += ["", "## Laser current setpoint", "",
      f"- CSA gain × shunt = {gain_v_per_a:.3f} V/A; FB divider ratio k = {k_div:.4f}",
      f"- Nominal setpoint: **{i_set_nominal:.4f} A**",
      f"- Tolerance contributions (%): " + ", ".join(f"{k} {v:.2f}" for k, v in tol.items()),
      f"- Worst-case sum **±{tol_worst:.2f} %**, RSS ±{tol_rss:.2f} %",
      f"- Independent ISP/ISN backup limit: {backup[0]:.2f} / {backup[1]:.2f} / {backup[2]:.2f} A (min/typ/max)", "",
      "| Target (A) | R_FB_TOP exact (Ω) | E96 (Ω) | Resulting (A) |", "|---|---|---|---|"]
for s in results["setpoint"]["alternates"]:
    L.append(f'| {s["i_target_a"]} | {s["r_top_exact_ohm"]} | {s["r_top_e96_ohm"]} | {s["i_resulting_a"]} |')
L += ["", "## Operating points", "",
      "| Diode corner | Vin (V) | Vf (V) | Vout node (V) | Region | Iin (A) | IL avg (A) | IL peak (A) | Efficiency |",
      "|---|---|---|---|---|---|---|---|---|"]
for p in points:
    L.append(f'| {p["corner"]} | {p["v_in"]} | {p["v_laser"]:.3f} | {p["v_out_node"]:.3f} | {p["region"]} | '
             f'{p["i_in"]:.2f} | {p["i_l_avg"]:.2f} | {p["i_l_peak"]:.2f} | {100 * p["efficiency"]:.1f} % |')
for key in (("typ_25C", 4.0), ("typ_25C", 3.0)):
    p = next(q for q in points if (q["corner"], q["v_in"]) == key)
    L += ["", f"### Loss breakdown: diode {key[0]}, Vin {key[1]} V", "", "| Loss | W |", "|---|---|"]
    for k, v in sorted(p["losses"].items(), key=lambda kv: -kv[1]):
        L.append(f"| {k} | {v:.3f} |")
    L.append(f'| **total** | **{p["p_in"] - p["p_laser"]:.3f}** |')
L += ["", "## Hardware undervoltage lockout (EN/UVLO divider)", "",
      f"- Turn-on {v_on:.3f} V, turn-off {v_off:.3f} V (R_top {r1} Ω, R_bot {r2} Ω, 5 µA hysteresis current)", "",
      "## Ripple", "",
      f"- Effective output capacitance {c_out_eff * 1e6:.1f} µF; output ripple {v_ripple * 1000:.1f} mV p-p at the worst boost point",
      f"- Laser current ripple ≈ {i_ripple_laser * 1000:.0f} mA p-p; output capacitor RMS (total) {i_cout_rms:.2f} A", "",
      "## Current loop", "", "| Diode | Vin | rd scale | Zac (Ω) | fc (Hz) | PM (°) | GM (dB) | f_RHPZ (Hz) |",
      "|---|---|---|---|---|---|---|---|"]
for r in loop_results:
    gm = f'{r["gain_margin_db"]:.1f}' if r["gain_margin_db"] is not None else "n/a"
    fc = f'{r["f_cross_hz"]:.0f}' if r["f_cross_hz"] else "n/a"
    pm = f'{r["phase_margin_deg"]:.1f}' if r["phase_margin_deg"] is not None else "n/a"
    L.append(f'| {r["corner"]} | {r["v_in"]} | {r["rd_scale"]} | {r["z_ac"]} | {fc} | {pm} | {gm} | {r["f_rhp_hz"]:.0f} |')
L += ["", "Model: averaged CCM boost-mode plant with the TPS552882 equivalent current-sense resistance (0.055 Ω),",
      "INA186A2 bandwidth pole, gm error amplifier with Rc-Cc-Cp. Buck mode has no RHP zero and is less restrictive.", "",
      "## Copper", ""]
for k, v in cu.items():
    L.append(f"- {k}: {v:.3f}" if isinstance(v, float) else f"- {k}: {v}")
L += ["", "## Run time (typical diode, 90 % of rated energy usable)", ""]
for k, v in runtime.items():
    L.append(f"- {k}: ~{v} min continuous")
L += ["", "![efficiency](plots/efficiency_vs_vin.png)", "", "![loop](plots/current_loop_bode.png)", ""]
(OUT / "power-stage-results.md").write_text("\n".join(L), encoding="utf-8")

# Evidence manifest: binds the results to the parameters, this script, the model code and the tool versions
# (audit AUD-VAL-01). The validator recomputes every hash.
from nubm44 import evidence  # noqa: E402

evidence.write(evidence.build(
    "calculation",
    inputs=[ROOT / "engineering/design/parameters.yaml", Path(__file__).resolve(),
            *sorted((ROOT / "automation/nubm44/calc").glob("*.py"))],
    outputs=[OUT / "power-stage-results.json", OUT / "power-stage-results.md", *sorted(PLOTS.glob("*.png"))],
    tools=evidence.python_tools(["numpy", "PyYAML", "matplotlib"]),
    evidence_class="PREDICTION (engineering calculation from datasheet parameters; not a measurement)",
    check_names=[c["check"] for c in checks]), OUT / "power-stage-evidence.json")

fails = [c for c in checks if c["status"] == "FAIL"]
print(f"{len(checks)} checks, {len(fails)} FAIL")
for c in checks:
    print(f'  {c["status"]:4}  {c["check"]}: {c["value"]} {c["unit"]} (limit {c["kind"]} {c["limit"]})')
sys.exit(1 if fails else 0)
