"""NUBM44 driver behavioural simulations (ngspice 47).

No usable vendor model exists for the TPS552882 (none published; the TPS55288 PSpice model is
encrypted), so this is a cycle-averaged behavioural model built from datasheet parameters:

  * unified 4-switch averaged power stage: control u in [0, 2]; u <= 1 -> buck duty d1 = u, u > 1 ->
    boost duty d2 = u - 1. v_L = d1*Vin - (1-d2)*Vout, i_in = d1*iL, i_out = (1-d2)*iL. The inductor is
    explicit, so boost RHP-zero dynamics are present; switching ripple is not.
  * inner average-current loop: PI, about 60 kHz crossover (TI does not publish it; assumption).
  * outer loop: gm 190 uA/V error amplifier, Rc-Cc-Cp from parameters.yaml, 1.2 V reference
    ramped over 4 ms by soft start, COMP clamped 0..2.5 V, average current limit (RILIM).
  * INA186A2: gain 50, 37 kHz first-order bandwidth, output limited to its supply.
  * ISP/ISN backup loop: pulls COMP down above 50 mV (gain and speed are assumptions: "slow" per TI).
  * EN/UVLO: VBAT divider with 1.23 V threshold and 5 uA hysteresis current; MCU, interlock and
    over-voltage (6.2 V Zener + FET) pull-downs.
  * load: NUBM44 Vf = V0 + rd*I with a soft knee; 50 nH / 10 mOhm wiring; PMEG4010 clamp.

Results go to simulation/results/ (CSV, PNG, results.json, results.md). A test PASSes only when its
measured metric meets its stated limit inside this model; physical behaviour remains Gate G.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import paths  # noqa: E402

OUT = ROOT / "simulation" / "results"
P = yaml.safe_load((ROOT / "engineering/design/parameters.yaml").read_text(encoding="utf-8"))
cv, cm, comp = P["converter"], P["components"], P["compensation"]
K_DIV = cm["fb_divider"]["r_bot_ohm"] / (cm["fb_divider"]["r_top_ohm"] + cm["fb_divider"]["r_bot_ohm"])
ILIM = 330000 / cv["r_ilim_ohm"]
C_OUT = cm["c_out"]["count"] * cm["c_out"]["c_nom_f"] * cm["c_out"]["bias_retention"]
C_IN = cm["c_in"]["count"] * cm["c_in"]["c_nom_f"] * cm["c_in"]["bias_retention"]
LASER = {k: v for k, v in P["laser"]["vf_model"].items()}


def netlist(name: str, vbat: float, laser: str = "typ", tstop: float = 0.012, en=None,
            extra: str = "", laser_r_override: str | None = None, interlock=None, rbat=0.04) -> str:
    """Return a full ngspice deck. ``en``: PWL list for the MCU enable (1 = enable)."""
    lm = LASER[laser]
    en = en or [(0, 0), (0.0005, 0), (0.00051, 1)]
    en_pwl = " ".join(f"{t} {v}" for t, v in en)
    il = interlock or [(0, 1)]
    il_pwl = " ".join(f"{t} {v}" for t, v in il)
    load = (laser_r_override if laser_r_override is not None else
            f"BLD ldk 0 I = {1/lm['rd']:.6g}*0.03*ln(1+exp((V(ldk)-{lm['v0']})/0.03))")
    return f"""* {name}
.option method=gear reltol=1e-4 abstol=1e-9 vntol=1e-6
* ---------------- battery, contacts, reverse-polarity FET (on), input capacitance
VB batp_i 0 DC {vbat}
RB batp_i batp_l {rbat}
LB batp_l batp 50n
RQ1 batp vin 0.0065
CIN vin cin_e {C_IN}
RCIN cin_e 0 0.002
* ---------------- EN/UVLO divider, pull-downs (MCU, interlock, OV backstop)
R5 vin enp {cv['r_en_top_ohm']}
R6 enp 0 {cv['r_en_bot_ohm']}
BHYS 0 enp I = (V(en_int) > 0.5) ? {cv['en_uvlo_hys_a']} : 0
VMCU mcu_en 0 PWL({en_pwl})
VIL il_ok 0 PWL({il_pwl})
SQ4 enp 0 q4c 0 SWLOW
BQ4 q4c 0 V = (V(mcu_en) > 0.5) ? 0 : 1
SQ5 enp 0 q5c 0 SWLOW
BQ5 q5c 0 V = (V(il_ok) > 0.5) ? 0 : 1
* OV backstop: BZT52C6V2-class Zener + DMG1012T, about 6.5 V at threshold
BOV ovr 0 V = (V(vout) > 6.5) ? 1 : 0
ROV ovr ovc 1k
COV ovc 0 1n
SQ6 enp 0 ovc 0 SWLOW
.model SWLOW SW(Ron=5 Roff=1e9 Vt=0.5 Vh=0.05)
* internal enable: UVLO comparator on EN pin and VIN UVLO (rising 3.0 V max / falling 2.65 V)
BEN en_raw 0 V = (V(enp) > {cv['en_uvlo_v']} && V(vin) > 2.7) ? 1 : 0
REN en_raw en_int 100
CEN en_int 0 1n
* ---------------- soft start: 1.2 V reference ramp in 4 ms, reset when disabled
BSS 0 vref I = (V(en_int) > 0.5) ? ((V(vref) < {cv['vref_v']}) ? {cv['vref_v']}*1e-9/{cv['soft_start_s']} : 0) : 0
CSS vref 0 1n
SSS vref 0 en_int 0 SWHI
.model SWHI SW(Ron=1 Roff=1e12 Vt=0.5 Vh=0.05)
* note SSS shorts vref when en_int is LOW (switch closes when control < Vt via inverted control below)
* ---------------- error amplifier (gm) and compensation
BGM 0 comp I = (V(en_int) > 0.5) ? {cv['gea_s']}*(V(vref)-V(fb)) : -1e-3*V(comp)
* ISP/ISN backup current loop: pulls COMP down above 50 mV (strength assumed)
BCC comp 0 I = {2e-3}*max(V(vout)-V(ldp)-{cv['isp_isn_limit_v'][1]}, 0)/0.001
RC comp comp_rc {comp['r_c_ohm']}
CC comp_rc 0 {comp['c_c_f']}
CP comp 0 {comp['c_p_f']}
REA comp 0 {cv['rea_ohm']}
DCH comp clamp_hi DCL
VCH clamp_hi 0 2.5
DCLO 0 comp DCL
.model DCL D(Is=1e-12 N=0.05)
* current command and inner PI current loop -> control variable u
BIC icmd 0 V = min(max(V(comp)/{cv['ri_equiv_ohm']}, -2), {ILIM})
BERR err 0 V = V(icmd) - I(VIL1)
BUI 0 uint I = (V(en_int) > 0.5) ? 6000e-6*V(err) : -1e-3*V(uint)
CUI uint 0 1u
DUH uint uh DCL
VUH uh 0 1.92
DUL 0 uint DCL
BU u 0 V = (V(en_int) > 0.5) ? min(max(V(uint) + 0.08*V(err), 0), 1.92) : 0
BD1 d1 0 V = min(V(u), 1)
BD2 d2 0 V = max(V(u) - 1, 0)
* ---------------- averaged power stage (inductor explicit), losses lumped
BNA na 0 V = V(d1)*V(vin)
BNB nb 0 V = (1-V(d2))*V(vout)
VIL1 na nl1 0
RL nl1 nl2 {cm['inductor']['dcr_typ_ohm'] * 1.2 + 0.012}
L1 nl2 nl3 {cm['inductor']['l_h']}
* with the converter disabled all four FETs are off: block reverse inductor current
DOFF nl3 nb DIDEAL
SON nl3 nb en_int 0 SWHI2
.model SWHI2 SW(Ron=1e-4 Roff=1e9 Vt=0.5 Vh=0.05)
.model DIDEAL D(Is=1e-9 N=0.5 Rs=1e-3)
BIIN vin 0 I = V(d1)*I(VIL1)
BIOUT 0 vout I = (1-V(d2))*I(VIL1)
* ---------------- output: capacitors, bleeder, shunt, wiring, clamp diode, laser
COUT vout cout_e {C_OUT}
RCOUT cout_e 0 0.0015
R7 vout 0 {cm['bleeder_ohm']}
RS1 vout ldp {cm['shunt']['r_ohm']}
LW ldp ldw 50n
RW ldw ldk 0.010
D1 0 ldk DSCH
.model DSCH D(Is=2e-6 N=1.05 Rs=0.08 Cjo=60p)
{load}
* ---------------- current sense amplifier INA186A2 + FB divider
BCSA csa_i 0 V = min(max({cm['csa']['gain']}*(V(vout)-V(ldp)), 0), V(vin)-0.02)
RCSA csa_i csf {1/(2*math.pi*cm['csa']['bw_hz']*1e-9):.1f}
CCSA csf 0 1n
ECSB csout 0 csf 0 1
R8 csout fb {cm['fb_divider']['r_top_ohm']}
R9 fb 0 {cm['fb_divider']['r_bot_ohm']}
{extra}
.tran 1u {tstop} 0 2u uic
.control
set wr_singlescale
set wr_vecnames
run
wrdata {name}.csv I(VIL1) v(vout) v(ldk) v(vin) v(enp) v(vref) v(comp) v(u) v(csout) i(VB)
quit
.endc
.end
"""


def run(name: str, deck: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cir = OUT / f"{name}.cir"
    # the soft-start reset switch must close when the converter is disabled: invert its control
    deck = deck.replace("SSS vref 0 en_int 0 SWHI", "BSSN ssn 0 V = (V(en_int) > 0.5) ? 0 : 1\nSSS vref 0 ssn 0 SWHI")
    cir.write_text(deck, encoding="utf-8")
    r = subprocess.run([str(paths.ngspice()), "-b", cir.name], cwd=OUT, capture_output=True, text=True, timeout=900)
    csv = OUT / f"{name}.csv"
    if r.returncode != 0 or not csv.exists():
        raise RuntimeError(f"ngspice failed for {name}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    data = np.loadtxt(csv, skiprows=1)
    cols = ["t", "iL", "vout", "vld", "vin", "enp", "vref", "comp", "u", "csout", "ibat"]
    d = {c: data[:, i] for i, c in enumerate(cols)}
    # laser current = shunt current = (vout - ldp)/Rs; ldp not saved: derive from CSA output (before filter)
    d["ilaser"] = d["csout"] / (cm["csa"]["gain"] * cm["shunt"]["r_ohm"])
    return d


def laser_current_true(d, laser="typ"):
    lm = LASER[laser]
    v = d["vld"]
    return 1 / lm["rd"] * 0.03 * np.log1p(np.exp(np.clip((v - lm["v0"]) / 0.03, -50, 50)))


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def settle_value(t, y, t0):
    m = t >= t0
    return float(np.mean(y[m])) if m.any() else float("nan")


@test
def startup_nominal():
    d = run("startup_3v7", netlist("startup_3v7", 3.7, tstop=0.010))
    il = laser_current_true(d)
    i_ss = settle_value(d["t"], il, 0.008)
    over = 100 * (il.max() - i_ss) / i_ss
    return {"id": "SIM-01", "name": "Power-on, nominal battery 3.7 V, typical diode",
            "metrics": {"steady_current_a": i_ss, "overshoot_pct": over, "peak_a": float(il.max())},
            "limit": "overshoot <= 10 % (REQ-OUT-05), steady current within 5 % of 4.0 A",
            "pass": over <= 10 and abs(i_ss - 4.0) / 4.0 <= 0.05, "data": d, "il": il}


@test
def startup_low_battery():
    d = run("startup_3v15", netlist("startup_3v15", 3.15, laser="max", tstop=0.010, rbat=0.005))
    il = laser_current_true(d, "max")
    i_ss = settle_value(d["t"], il, 0.008)
    over = 100 * (il.max() - i_ss) / max(i_ss, 1e-6)
    return {"id": "SIM-02", "name": "Power-on at 3.15 V (just above the 3.08 V hardware UVLO), maximum-Vf diode",
            "metrics": {"steady_current_a": i_ss, "overshoot_pct": over, "peak_inductor_a": float(d["iL"].max())},
            "limit": "overshoot <= 10 %, current within 5 %, peak inductor current < ILIM min 10.2 A",
            "pass": over <= 10 and abs(i_ss - 4.0) / 4.0 <= 0.05 and d["iL"].max() < 10.2, "data": d, "il": il}


@test
def regulation_corners():
    res = {}
    ok = True
    for vb in (3.0, 3.7, 4.2):
        for lz in ("min", "typ", "max"):
            n = f"reg_{vb}_{lz}".replace(".", "p")
            deck = netlist(n, max(vb, 3.3), laser=lz, tstop=0.008, rbat=0.005)
            if vb < 3.3:
                deck = deck.replace(f"VB batp_i 0 DC {max(vb, 3.3)}", f"VB batp_i 0 PWL(0 3.3 4.5m 3.3 5.5m {vb})")
            d = run(n, deck)
            i_ss = settle_value(d["t"], laser_current_true(d, lz), 0.0065)
            res[f"{vb}V_{lz}"] = round(i_ss, 4)
            ok &= abs(i_ss - 4.0) / 4.0 <= 0.02
    return {"id": "SIM-03", "name": "Current regulation across battery 3.0-4.2 V and diode Vf corners (incl. Vf below Vbat)",
            "metrics": res, "limit": "model-level regulation within 2 % at every corner (tolerances excluded)",
            "pass": ok}


@test
def battery_sag():
    extra = "* battery step: 4.0 V -> 3.2 V at 9 ms (series source)\nVSTEP batp_i_s 0 0\n"
    deck = netlist("battery_step", 4.0, tstop=0.014)
    deck = deck.replace("VB batp_i 0 DC 4.0", "VB batp_i 0 PWL(0 4.0 9m 4.0 10m 3.2)")
    d = run("battery_step", deck)
    il = laser_current_true(d)
    m = d["t"] > 0.009
    dev = 100 * float(np.max(np.abs(il[m] - 4.0))) / 4.0
    return {"id": "SIM-04", "name": "Input voltage reduction (4.0 -> 3.2 V over 1 ms, 40 mOhm source)",
            "metrics": {"max_current_deviation_pct": dev}, "limit": "deviation <= 5 %", "pass": dev <= 5, "data": d, "il": il}


@test
def load_step():
    # diode warms: V0 falls 0.15 V within 50 us at 9 ms (worst-case thermal step, much faster than reality)
    lm = LASER["typ"]
    load = (f"BLD ldk 0 I = {1/lm['rd']:.6g}*0.03*ln(1+exp((V(ldk)-({lm['v0']}-0.15*min(max((time-9e-3)/2e-3,0),1)))/0.03))")
    d = run("load_step", netlist("load_step", 3.7, tstop=0.014, laser_r_override=load))
    i = (d["csout"] / (cm["csa"]["gain"] * cm["shunt"]["r_ohm"]))
    m = d["t"] > 0.009
    dev = 100 * float(np.max(np.abs(i[m] - 4.0))) / 4.0
    return {"id": "SIM-05", "name": "Load variation: diode Vf drops 0.15 V over 2 ms (faster than diode thermal time constants)",
            "metrics": {"max_current_deviation_pct": dev}, "limit": "deviation <= 5 %", "pass": dev <= 5, "data": d, "il": i}


@test
def flash_mode():
    en = [(0, 0), (0.0005, 0), (0.00051, 1), (0.010, 1), (0.01001, 0), (0.020, 0), (0.02001, 1), (0.030, 1), (0.03001, 0)]
    d = run("flash", netlist("flash", 4.2, laser="min", tstop=0.036, en=en))
    il = laser_current_true(d, "min")
    peak = float(il.max())
    off = d["t"] > 0.0305
    decay = float(il[off][np.argmax(il[off] < 0.05)] if (il[off] < 0.05).any() else il[off][-1])
    t_off = float(d["t"][off][np.argmax(il[off] < 0.05)] - 0.03001) if (il[off] < 0.05).any() else float("nan")
    return {"id": "SIM-06", "name": "Flash transitions at full battery 4.2 V with lowest-Vf diode (Vf < Vbat region)",
            "metrics": {"peak_current_a": peak, "turn_off_to_50mA_s": t_off},
            "limit": "peak <= 4.4 A on every turn-on; current < 50 mA within 2 ms of disable",
            "pass": peak <= 4.4 and t_off < 0.002, "data": d, "il": il}


@test
def interlock_open():
    d = run("interlock", netlist("interlock", 3.7, tstop=0.014, interlock=[(0, 1), (0.009, 1), (0.00901, 0)]))
    il = laser_current_true(d)
    m = d["t"] > 0.009
    t_off = float(d["t"][m][np.argmax(il[m] < 0.05)] - 0.009) if (il[m] < 0.05).any() else float("nan")
    return {"id": "SIM-07", "name": "Fault shutdown: interlock opens during emission",
            "metrics": {"time_to_50mA_s": t_off}, "limit": "< 2 ms", "pass": t_off < 0.002, "data": d, "il": il}


@test
def short_circuit():
    load = "BLD ldk 0 I = (time < 9e-3) ? 0.170^-1*0.03*ln(1+exp((V(ldk)-3.75)/0.03)) : V(ldk)/0.01"
    d = run("short", netlist("short", 3.7, tstop=0.014, laser_r_override=load))
    i = d["csout"] / (cm["csa"]["gain"] * cm["shunt"]["r_ohm"])
    ish = (d["vout"] - d["vld"]) * 0  # placeholder (shunt current not saved separately)
    m = d["t"] > 0.0095
    i_short = float(np.max(d["iL"][m]))
    return {"id": "SIM-08", "name": "Output short-circuit (10 mOhm) during emission",
            "metrics": {"peak_inductor_current_a": float(np.max(d["iL"][d["t"] > 0.009])),
                        "settled_output_current_a": settle_value(d["t"], d["iL"] * 0 + i, 0.013)},
            "limit": "inductor current < 25 A cycle-by-cycle peak limit; output current settles <= 5.2 A (backup ceiling)",
            "pass": float(np.max(d["iL"][d["t"] > 0.009])) < 25 and settle_value(d["t"], i, 0.013) <= 5.2, "data": d, "il": i}


@test
def open_load():
    load = "BLD ldk 0 I = (time < 9e-3) ? 0.170^-1*0.03*ln(1+exp((V(ldk)-3.75)/0.03)) : 1e-6*V(ldk)"
    d = run("open", netlist("open", 3.7, tstop=0.016, laser_r_override=load))
    m = d["t"] > 0.009
    vmax = float(np.max(d["vout"][m]))
    return {"id": "SIM-09", "name": "Open load (diode disconnected) during emission, hardware backstop only",
            "metrics": {"peak_vout_v": vmax}, "limit": "VOUT peak < 10 V (16 V-rated capacitors, 2x margin)",
            "pass": vmax < 10.0, "data": d, "il": d["vout"]}


def reverse_polarity() -> dict:
    """DC check of the high-side P-FET protection with the battery reversed (VDMOS model, Vgs = 0)."""
    deck = f"""* reverse polarity
VB batp 0 DC -4.2
RB batp spring 0.04
M1 spring gate vbat vbat PFET
.model PFET VDMOS(pchan Vto=-0.7 Kp=60 Rd=2m Rs=1m Rb=5m Is=1e-12 N=1.0)
RG gate 0 100k
RLOAD vbat 0 2
.op
.control
run
print i(VB) v(vbat)
quit
.endc
.end
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reverse.cir").write_text(deck, encoding="utf-8")
    r = subprocess.run([str(paths.ngspice()), "-b", "reverse.cir"], cwd=OUT, capture_output=True, text=True, timeout=120)
    vals = {}
    for ln in r.stdout.splitlines():
        if "=" in ln:
            k, v = ln.split("=", 1)
            try:
                vals[k.strip()] = float(v.split()[0])
            except ValueError:
                pass
    i = abs(vals.get("i(vb)", float("nan")))
    return {"id": "SIM-10", "name": "Reverse battery (-4.2 V): P-FET blocks (body diode reverse-biased, Vgs = 0)",
            "metrics": {"reverse_current_a": i, "vbat_node_v": vals.get("v(vbat)")},
            "limit": "reverse current < 1 mA", "pass": i < 1e-3}


def loop_ac() -> dict:
    """Cross-check of the Python loop model: crossover / phase margin at 3.7 V, typical diode."""
    sys.path.insert(0, str(ROOT / "engineering/calculations"))
    res = json.loads((ROOT / "engineering/calculations/power-stage-results.json").read_text(encoding="utf-8"))
    loops = res["loop"]
    pm = min(l["phase_margin_deg"] for l in loops if l["phase_margin_deg"] is not None)
    gm = min(l["gain_margin_db"] for l in loops if l["gain_margin_db"] is not None)
    return {"id": "SIM-11", "name": "Control-loop response (linearised model, 12 corners)",
            "metrics": {"min_phase_margin_deg": pm, "min_gain_margin_db": gm},
            "limit": "PM >= 50 deg, GM >= 10 dB (time-domain step tests SIM-04/05 corroborate)",
            "pass": pm >= 50 and gm >= 10}


def plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for r in results:
        if "data" not in r:
            continue
        d = r["data"]
        fig, axs = plt.subplots(3, 1, figsize=(7.5, 6.5), sharex=True)
        axs[0].plot(d["t"] * 1e3, r["il"], lw=0.9)
        axs[0].set_ylabel("Laser I (A)" if r["id"] != "SIM-09" else "VOUT (V)")
        axs[1].plot(d["t"] * 1e3, d["vout"], lw=0.9, label="VOUT")
        axs[1].plot(d["t"] * 1e3, d["vin"], lw=0.9, label="VIN")
        axs[1].set_ylabel("V"); axs[1].legend(fontsize=7)
        axs[2].plot(d["t"] * 1e3, d["iL"], lw=0.9, label="inductor I")
        axs[2].set_ylabel("A"); axs[2].set_xlabel("time (ms)"); axs[2].legend(fontsize=7)
        for a in axs:
            a.grid(alpha=0.3)
        axs[0].set_title(f'{r["id"]}: {r["name"]}', fontsize=9)
        fig.tight_layout(); fig.savefig(OUT / f'{r["id"]}.png', dpi=110); plt.close(fig)


def main() -> int:
    results = []
    for fn in TESTS:
        try:
            results.append(fn())
        except Exception as e:  # a failed run is reported, never hidden
            results.append({"id": fn.__name__, "name": fn.__name__, "metrics": {}, "limit": "",
                            "pass": False, "error": str(e)[:500]})
    results.append(reverse_polarity())
    results.append(loop_ac())
    plot(results)
    slim = [{k: v for k, v in r.items() if k not in ("data", "il")} for r in results]
    for r in slim:
        r["status"] = "PASS" if r["pass"] else ("NOT RUN" if r.get("error") else "FAIL")
    (OUT / "results.json").write_text(json.dumps(slim, indent=1, default=float), encoding="utf-8")
    lines = ["# Simulation results", "", "Behavioural cycle-averaged model (see `simulation/run_sims.py` docstring for",
             "every assumption). PASS means the metric met its limit inside this model only.", "",
             "| ID | Test | Metrics | Limit | Status |", "|---|---|---|---|---|"]
    for r in slim:
        met = ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in r["metrics"].items())
        lines.append(f'| {r["id"]} | {r["name"]} | {met or r.get("error", "")} | {r["limit"]} | **{r["status"]}** |')
    lines += ["", "Plots: `simulation/results/SIM-*.png`."]
    (OUT / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in slim:
        print(f'{r["status"]:8} {r["id"]} {r["name"]}: {r["metrics"] or r.get("error", "")}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
