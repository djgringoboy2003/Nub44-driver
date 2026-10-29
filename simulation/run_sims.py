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

SIM-11 measures the current-loop gain in this deck by frequency-response analysis (a sinusoidal voltage
injected between the CSA output and the FB divider, Middlebrook method, one transient per frequency), so it no
longer copies the Python loop model; the Python result at the same corner is reported beside it as a cross-check.
Both share datasheet parameters and the inner-loop assumption, so agreement is corroboration, not proof.
SIM-12 repeats the loop measurement with component tolerances and the modelling assumptions varied.
simulation/results/evidence.json binds every result to parameters.yaml, this script and the ngspice version.
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
I_SET = P["current"]["i_set_a"]      # REQ-OUT-01 setpoint (DD-36: 4.5 A)
I_PEAK = 1.1 * I_SET                 # REQ-OUT-05: normal transients within +10 %
cv, cm, comp = P["converter"], P["components"], P["compensation"]
K_DIV = cm["fb_divider"]["r_bot_ohm"] / (cm["fb_divider"]["r_top_ohm"] + cm["fb_divider"]["r_bot_ohm"])
ILIM = 330000 / cv["r_ilim_ohm"]
C_OUT = cm["c_out"]["count"] * cm["c_out"]["c_nom_f"] * cm["c_out"]["bias_retention"]
C_IN = cm["c_in"]["count"] * cm["c_in"]["c_nom_f"] * cm["c_in"]["bias_retention"]
LASER = {k: v for k, v in P["laser"]["vf_model"].items()}


def netlist(name: str, vbat: float, laser: str = "typ", tstop: float = 0.012, en=None,
            extra: str = "", laser_r_override: str | None = None, interlock=None, rbat=0.04,
            variant: dict | None = None) -> str:
    """Return a full ngspice deck. ``en``: PWL list for the MCU enable (1 = enable).
    ``variant`` scales model parameters for the sensitivity sweep: c_out, l, gm, csa_bw, inner (multipliers)
    and soft_start_s (seconds)."""
    v = variant or {}
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
BSS 0 vref I = (V(en_int) > 0.5) ? ((V(vref) < {cv['vref_v']}) ? {cv['vref_v']}*1e-9/{v.get('soft_start_s', cv['soft_start_s'])} : 0) : 0
CSS vref 0 1n
SSS vref 0 en_int 0 SWHI
.model SWHI SW(Ron=1 Roff=1e12 Vt=0.5 Vh=0.05)
* note SSS shorts vref when en_int is LOW (switch closes when control < Vt via inverted control below)
* ---------------- error amplifier (gm) and compensation
BGM 0 comp I = (V(en_int) > 0.5) ? {cv['gea_s'] * v.get('gm', 1)}*(V(vref)-V(fb)) : -1e-3*V(comp)
* ISP/ISN backup current loop: pulls COMP down above 50 mV (strength assumed)
BCC comp 0 I = {2e-3}*max(V(vout)-V(ldp)-{cv['isp_isn_limit_v'][1]}, 0)/0.001
RC comp comp_rc {comp['r_c_ohm'] * v.get('r_c', 1)}
CC comp_rc 0 {comp['c_c_f']}
CP comp 0 {comp['c_p_f'] * v.get('c_p', 1)}
REA comp 0 {cv['rea_ohm']}
DCH comp clamp_hi DCL
VCH clamp_hi 0 2.5
DCLO 0 comp DCL
.model DCL D(Is=1e-12 N=0.05)
* current command and inner PI current loop -> control variable u
BIC icmd 0 V = min(max(V(comp)/{cv['ri_equiv_ohm']}, -2), {ILIM})
BERR err 0 V = V(icmd) - I(VIL1)
BUI 0 uint I = (V(en_int) > 0.5) ? {6000e-6 * v.get('inner', 1)}*V(err) : -1e-3*V(uint)
CUI uint 0 1u
DUH uint uh DCL
VUH uh 0 1.92
DUL 0 uint DCL
BU u 0 V = (V(en_int) > 0.5) ? min(max(V(uint) + {0.08 * v.get('inner', 1)}*V(err), 0), 1.92) : 0
BD1 d1 0 V = min(V(u), 1)
BD2 d2 0 V = max(V(u) - 1, 0)
* ---------------- averaged power stage (inductor explicit), losses lumped
BNA na 0 V = V(d1)*V(vin)
BNB nb 0 V = (1-V(d2))*V(vout)
VIL1 na nl1 0
RL nl1 nl2 {cm['inductor']['dcr_typ_ohm'] * 1.2 + 0.012}
L1 nl2 nl3 {cm['inductor']['l_h'] * v.get('l', 1)}
* with the converter disabled all four FETs are off: block reverse inductor current
DOFF nl3 nb DIDEAL
SON nl3 nb en_int 0 SWHI2
.model SWHI2 SW(Ron=1e-4 Roff=1e9 Vt=0.5 Vh=0.05)
.model DIDEAL D(Is=1e-9 N=0.5 Rs=1e-3)
BIIN vin 0 I = V(d1)*I(VIL1)
BIOUT 0 vout I = (1-V(d2))*I(VIL1)
* ---------------- output: capacitors, bleeder, shunt, wiring, clamp diode, laser
COUT vout cout_e {C_OUT * v.get('c_out', 1)}
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
RCSA csa_i csf {1/(2*math.pi*cm['csa']['bw_hz']*v.get('csa_bw', 1)*1e-9):.1f}
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


def finalize(deck: str) -> str:
    # the soft-start reset switch must close when the converter is disabled: invert its control
    return deck.replace("SSS vref 0 en_int 0 SWHI", "BSSN ssn 0 V = (V(en_int) > 0.5) ? 0 : 1\nSSS vref 0 ssn 0 SWHI")


def run(name: str, deck: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cir = OUT / f"{name}.cir"
    deck = finalize(deck)
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
            "limit": f"overshoot <= 10 % (REQ-OUT-05), steady current within 5 % of {I_SET:g} A",
            "pass": over <= 10 and abs(i_ss - I_SET) / I_SET <= 0.05, "data": d, "il": il}


@test
def startup_low_battery():
    d = run("startup_3v15", netlist("startup_3v15", 3.15, laser="max", tstop=0.010, rbat=0.005))
    il = laser_current_true(d, "max")
    i_ss = settle_value(d["t"], il, 0.008)
    over = 100 * (il.max() - i_ss) / max(i_ss, 1e-6)
    return {"id": "SIM-02", "name": "Power-on at 3.15 V (just above the 3.08 V hardware UVLO), maximum-Vf diode",
            "metrics": {"steady_current_a": i_ss, "overshoot_pct": over, "peak_inductor_a": float(d["iL"].max())},
            "limit": "overshoot <= 10 %, current within 5 %, peak inductor current < ILIM min 10.2 A",
            "pass": over <= 10 and abs(i_ss - I_SET) / I_SET <= 0.05 and d["iL"].max() < 10.2, "data": d, "il": il}


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
            ok &= abs(i_ss - I_SET) / I_SET <= 0.02
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
    dev = 100 * float(np.max(np.abs(il[m] - I_SET))) / I_SET
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
    dev = 100 * float(np.max(np.abs(i[m] - I_SET))) / I_SET
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
            "limit": f"peak <= {I_PEAK:.2f} A on every turn-on; current < 50 mA within 2 ms of disable",
            "pass": peak <= I_PEAK and t_off < 0.002, "data": d, "il": il}


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
    i_peak = float(np.max(d["iL"][d["t"] > 0.009]))
    i_settled = settle_value(d["t"], i, 0.013)
    # 25 A = TPS552882 ILIM_PK, typical cycle-by-cycle peak limit (SLVSFC5 p.7, LEAD-01). The averaged model has
    # no cycle-by-cycle limit, so this compares the averaged inductor current with it.
    return {"id": "SIM-08", "name": "Output short-circuit (10 mOhm) during emission",
            "metrics": {"peak_inductor_current_a": i_peak, "settled_output_current_a": i_settled},
            "limit": "averaged inductor current < 25 A (ILIM_PK typ, SLVSFC5 p.7); output current settles <= 5.2 A (backup ceiling)",
            "pass": i_peak < 25 and i_settled <= 5.2, "data": d, "il": i}


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


# ---------------------------------------------------------------- loop gain by frequency-response analysis
FRA_WORK = ROOT / "build" / "sim-fra"           # raw FRA decks and waveforms (scratch; results keep the processed data)
FRA_FREQS = [float(f) for f in np.round(np.logspace(np.log10(300), np.log10(100e3), 16), -1)]
FRA_AMP_V = 0.05                                 # injected amplitude: 2.5 % of the 2.0 V CSA signal at 4 A
FRA_SOFT_START_S = 0.0005                        # shortened ramp: only the steady-state small signal matters
PM_LIMIT, GM_LIMIT = 50.0, 10.0


def fra_point(tag: str, f: float, vbat: float, laser: str, variant: dict | None = None) -> complex:
    """Loop gain T(f) = -Vy/Vx with a series voltage injection between the CSA output (y) and R8 (x)."""
    variant = dict(variant or {}, soft_start_s=FRA_SOFT_START_S)
    period = 1.0 / f
    t_inj = 0.003
    settle = max(5 * period, 0.003)
    n_per = max(5, math.ceil(0.002 / period))
    t_meas = t_inj + settle
    tstop = t_meas + n_per * period
    step = min(period / 200, 2e-6)
    name = f"fra_{tag}_{int(f)}"
    deck = netlist(name, vbat, laser=laser, tstop=0.01, rbat=0.005, variant=variant)
    if vbat < 3.3:                               # start above the 3.08 V UVLO rising threshold, then ramp down
        deck = deck.replace(f"VB batp_i 0 DC {vbat}", f"VB batp_i 0 PWL(0 3.3 1.5m 3.3 2m {vbat})")
    deck = deck.replace("ECSB csout 0 csf 0 1",
                        f"ECSB csy 0 csf 0 1\nVINJ csout csy DC 0 SIN(0 {FRA_AMP_V} {f} {t_inj})")
    deck = deck.replace(".tran 1u 0.01 0 2u uic", f".tran {step:.4g} {tstop:.6g} 0 {step:.4g} uic")
    deck = deck.replace("reltol=1e-4", "reltol=1e-5")
    deck = deck.replace(f"wrdata {name}.csv I(VIL1) v(vout) v(ldk) v(vin) v(enp) v(vref) v(comp) v(u) v(csout) i(VB)",
                        f"wrdata {name}.csv v(csout) v(csy)")
    FRA_WORK.mkdir(parents=True, exist_ok=True)
    (FRA_WORK / f"{name}.cir").write_text(finalize(deck), encoding="utf-8")
    r = subprocess.run([str(paths.ngspice()), "-b", f"{name}.cir"], cwd=FRA_WORK, capture_output=True, text=True,
                       timeout=900)
    csv = FRA_WORK / f"{name}.csv"
    if r.returncode != 0 or not csv.exists():
        raise RuntimeError(f"ngspice failed for {name}:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    data = np.loadtxt(csv, skiprows=1)
    t, x, y = data[:, 0], data[:, 1], data[:, 2]
    tu = np.linspace(t_meas, tstop, 4000, endpoint=False)          # integer number of periods
    xu, yu = np.interp(tu, t, x), np.interp(tu, t, y)
    e = np.exp(-2j * np.pi * f * tu)
    return complex(-np.sum((yu - yu.mean()) * e) / np.sum((xu - xu.mean()) * e))


def margins(freqs: list[float], T: list[complex]) -> dict:
    """Crossover, phase margin and gain margin by log interpolation between measured points."""
    f = np.array(freqs)
    if min(abs(t) for t in T) < 1e-9:
        raise RuntimeError("no loop response at some frequency (converter not running in the FRA deck?)")
    mag = 20 * np.log10(np.abs(np.array(T)))
    ph = np.degrees(np.unwrap(np.angle(np.array(T))))
    out = {"f_cross_hz": None, "phase_margin_deg": None, "f_180_hz": None, "gain_margin_db": None,
           "mag_at_fmax_db": float(mag[-1]), "phase_at_fmax_deg": float(ph[-1])}
    for i in range(len(f) - 1):
        if out["f_cross_hz"] is None and mag[i] >= 0 > mag[i + 1]:
            k = mag[i] / (mag[i] - mag[i + 1])
            lf = np.log10(f[i]) + k * (np.log10(f[i + 1]) - np.log10(f[i]))
            out["f_cross_hz"] = float(10 ** lf)
            out["phase_margin_deg"] = float(180 + ph[i] + k * (ph[i + 1] - ph[i]))
        if out["f_180_hz"] is None and ph[i] > -180 >= ph[i + 1]:
            k = (ph[i] + 180) / (ph[i] - ph[i + 1])
            out["f_180_hz"] = float(10 ** (np.log10(f[i]) + k * (np.log10(f[i + 1]) - np.log10(f[i]))))
            out["gain_margin_db"] = float(-(mag[i] + k * (mag[i + 1] - mag[i])))
    return out


def loop_ok(m: dict) -> bool:
    """PM >= 50 deg at crossover; GM >= 10 dB, or, when the phase never reaches -180 deg below fmax, at least
    10 dB of attenuation at fmax (the averaged model is not meaningful much above fsw/5)."""
    if m["phase_margin_deg"] is None or m["phase_margin_deg"] < PM_LIMIT:
        return False
    if m["gain_margin_db"] is not None:
        return m["gain_margin_db"] >= GM_LIMIT
    return m["mag_at_fmax_db"] <= -GM_LIMIT


def fra_sweep(tag: str, vbat: float, laser: str, variant: dict | None = None, freqs=None) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    freqs = list(freqs or FRA_FREQS)
    with ThreadPoolExecutor(max_workers=4) as pool:
        T = list(pool.map(lambda f: fra_point(tag, f, vbat, laser, variant), freqs))
        # refine: two extra points inside each bracket that holds the gain or the phase crossover
        m = margins(freqs, T)
        extra = []
        for fx in (m["f_cross_hz"], m["f_180_hz"]):
            if fx is None:
                continue
            i = max(k for k in range(len(freqs) - 1) if freqs[k] <= fx)
            lo, hi = math.log10(freqs[i]), math.log10(freqs[i + 1])
            extra += [round(10 ** (lo + (hi - lo) * q), 1) for q in (1 / 3, 2 / 3)]
        extra = sorted(set(extra) - set(freqs))
        T += list(pool.map(lambda f: fra_point(tag, f, vbat, laser, variant), extra))
    order = sorted(range(len(freqs) + len(extra)), key=lambda k: (freqs + extra)[k])
    freqs, T = [(freqs + extra)[k] for k in order], [T[k] for k in order]
    m = margins(freqs, T)
    return {"vbat": vbat, "laser": laser, "freqs_hz": freqs, "mag_db": [round(20 * math.log10(abs(t)), 3) for t in T],
            "phase_deg": [round(math.degrees(a), 2) for a in np.unwrap(np.angle(np.array(T)))], **m}


def loop_fra() -> dict:
    corners = {"3.7V_typ": (3.7, "typ"), "3.0V_max": (3.0, "max"), "4.2V_min": (4.2, "min")}
    sweeps = {k: fra_sweep(k, vb, lz) for k, (vb, lz) in corners.items()}
    calc = json.loads((ROOT / "engineering/calculations/power-stage-results.json").read_text(encoding="utf-8"))
    ref = next((l for l in calc["loop"] if l["corner"] == "typ_25C" and l["v_in"] == 3.7 and l["rd_scale"] == 1.0), None)
    s = sweeps["3.7V_typ"]
    metrics = {f"{k}_{q}": (round(v[q], 2) if v[q] is not None else None)
               for k, v in sweeps.items() for q in ("f_cross_hz", "phase_margin_deg", "gain_margin_db")}
    if ref and s["f_cross_hz"]:
        metrics["python_model_3.7V_typ_f_cross_hz"] = round(ref["f_cross_hz"], 1)
        metrics["python_model_3.7V_typ_phase_margin_deg"] = round(ref["phase_margin_deg"], 2)
        metrics["fc_difference_pct"] = round(100 * (s["f_cross_hz"] - ref["f_cross_hz"]) / ref["f_cross_hz"], 1)
        metrics["pm_difference_deg"] = round(s["phase_margin_deg"] - ref["phase_margin_deg"], 1)
    return {"id": "SIM-11", "name": "Current-loop gain by frequency-response analysis of the averaged deck "
                                    "(3.7 V typ, 3.0 V max-Vf, 4.2 V min-Vf), compared with the Python model",
            "metrics": metrics, "bode": sweeps,
            "limit": f"PM >= {PM_LIMIT:g} deg at every corner; GM >= {GM_LIMIT:g} dB (or >= {GM_LIMIT:g} dB attenuation "
                     "at 100 kHz if the phase stays above -180 deg); Python-model difference reported, not judged",
            "pass": all(loop_ok(v) for v in sweeps.values())}


SENSITIVITY = {                                   # one-at-a-time and combined worst cases (multipliers)
    "nominal": {},
    "C_out retention 0.35/0.55": {"c_out": 0.35 / 0.55},
    "C_out retention 0.75/0.55": {"c_out": 0.75 / 0.55},
    "L -20 %": {"l": 0.8},
    "L +20 %": {"l": 1.2},
    "gm -20 %": {"gm": 0.8},
    "gm +20 %": {"gm": 1.2},
    "CSA bandwidth -30 %": {"csa_bw": 0.7},
    "inner loop gain x0.5 (assumption)": {"inner": 0.5},
    "inner loop gain x2 (assumption)": {"inner": 2.0},
    "combined: low C, high L, high gm, slow CSA": {"c_out": 0.35 / 0.55, "l": 1.2, "gm": 1.2, "csa_bw": 0.7},
}
SENS_FREQS = [float(f) for f in np.round(np.logspace(np.log10(700), np.log10(100e3), 11), -1)]


def sensitivity() -> dict:
    rows = {}
    for label, var in SENSITIVITY.items():
        tag = "sens_" + "".join(ch if ch.isalnum() else "_" for ch in label)[:40]
        s = fra_sweep(tag, 3.0, "max", var, SENS_FREQS)
        rows[label] = {k: (round(s[k], 2) if isinstance(s[k], float) else s[k])
                       for k in ("f_cross_hz", "phase_margin_deg", "gain_margin_db", "mag_at_fmax_db")}
        rows[label]["pass"] = loop_ok(s)
    pms = [r["phase_margin_deg"] for r in rows.values() if r["phase_margin_deg"] is not None]
    return {"id": "SIM-12", "name": "Loop sensitivity at 3.0 V, max-Vf diode: output capacitance (DC bias), inductance, "
                                    "error-amplifier gm, CSA bandwidth and the assumed inner-loop gain",
            "metrics": {"min_phase_margin_deg": min(pms) if pms else None,
                        "cases_passing": sum(r["pass"] for r in rows.values()), "cases": len(rows)},
            "sweep": rows,
            "limit": f"every case: PM >= {PM_LIMIT:g} deg and the gain-margin rule of SIM-11",
            "pass": all(r["pass"] for r in rows.values())}


def plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for r in results:
        if "bode" in r:
            fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
            for k, s in r["bode"].items():
                a1.semilogx(s["freqs_hz"], s["mag_db"], marker="o", ms=3, lw=0.9, label=k)
                a2.semilogx(s["freqs_hz"], [180 + p for p in s["phase_deg"]], marker="o", ms=3, lw=0.9)
            a1.axhline(0, color="k", lw=0.6); a1.set_ylabel("Loop gain (dB)"); a1.legend(fontsize=7)
            a2.axhline(PM_LIMIT, color="grey", ls="--", lw=0.8); a2.set_ylabel("180 + phase (deg)")
            a2.set_xlabel("Frequency (Hz)")
            for a in (a1, a2):
                a.grid(alpha=0.3, which="both")
            a1.set_title(f'{r["id"]}: loop gain measured in the averaged ngspice deck (FRA)', fontsize=9)
            fig.tight_layout(); fig.savefig(OUT / f'{r["id"]}.png', dpi=110); plt.close(fig)
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


SIM_IDS = {"startup_nominal": "SIM-01", "startup_low_battery": "SIM-02", "regulation_corners": "SIM-03",
           "battery_sag": "SIM-04", "load_step": "SIM-05", "flash_mode": "SIM-06", "interlock_open": "SIM-07",
           "short_circuit": "SIM-08", "open_load": "SIM-09", "reverse_polarity": "SIM-10", "loop_fra": "SIM-11",
           "sensitivity": "SIM-12"}


def ngspice_version() -> str:
    try:
        r = subprocess.run([str(paths.ngspice()), "--version"], capture_output=True, text=True, timeout=60)
        return next((ln.strip(" *") for ln in (r.stdout + r.stderr).splitlines() if "ngspice-" in ln), "UNKNOWN")
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return "UNKNOWN"


def write_evidence() -> None:
    from nubm44 import evidence
    outputs = [OUT / "results.json", OUT / "results.md", *sorted(OUT.glob("SIM-*.png")),
               *sorted(OUT.glob("*.cir")), *sorted(OUT.glob("*.csv"))]
    evidence.write(evidence.build(
        "simulation",
        inputs=[ROOT / "engineering/design/parameters.yaml", Path(__file__).resolve(),
                ROOT / "engineering/calculations/power-stage-results.json"],
        outputs=outputs,
        tools={**evidence.python_tools(["numpy", "PyYAML", "matplotlib"]), "ngspice": ngspice_version()},
        evidence_class="PREDICTION (behavioural cycle-averaged ngspice model; not switching-level, not a measurement)",
        simulation_ids=sorted(SIM_IDS.values())), OUT / "evidence.json")


def main() -> int:
    results = []
    for fn in TESTS + [reverse_polarity, loop_fra, sensitivity]:
        try:
            results.append(fn())
        except Exception as e:  # a failed run is reported, never hidden
            results.append({"id": SIM_IDS.get(fn.__name__, fn.__name__), "name": fn.__name__, "metrics": {},
                            "limit": "", "pass": False, "error": f"{type(e).__name__}: {str(e)[:500]}"})
    plot(results)
    slim = [{k: v for k, v in r.items() if k not in ("data", "il")} for r in results]
    for r in slim:
        r["pass"] = bool(r["pass"])               # numpy booleans would serialise as 1.0
        r["status"] = "PASS" if r["pass"] else ("NOT RUN" if r.get("error") else "FAIL")
    (OUT / "results.json").write_text(json.dumps(slim, indent=1, default=float), encoding="utf-8")
    lines = ["# Simulation results", "", "Behavioural cycle-averaged model (see `simulation/run_sims.py` docstring for",
             "every assumption). PASS means the metric met its limit inside this model only: these are predictions,",
             "not measurements, and the model has no switching ripple, saturation or dead time.", "",
             "| ID | Test | Metrics | Limit | Status |", "|---|---|---|---|---|"]
    for r in slim:
        met = ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}" for k, v in r["metrics"].items())
        lines.append(f'| {r["id"]} | {r["name"]} | {met or r.get("error", "")} | {r["limit"]} | **{r["status"]}** |')
    sens = next((r for r in slim if r["id"] == "SIM-12" and "sweep" in r), None)
    if sens:
        lines += ["", "## SIM-12 sensitivity cases", "", "| Case | fc (Hz) | PM (deg) | GM (dB) | |T| at 100 kHz (dB) | Pass |",
                  "|---|---|---|---|---|---|"]
        for label, row in sens["sweep"].items():
            lines.append(f"| {label} | {row['f_cross_hz']} | {row['phase_margin_deg']} | {row['gain_margin_db']} | "
                         f"{row['mag_at_fmax_db']} | {'yes' if row['pass'] else 'NO'} |")
    lines += ["", "Plots: `simulation/results/SIM-*.png`. Evidence manifest: `simulation/results/evidence.json`."]
    (OUT / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_evidence()
    for r in slim:
        print(f'{r["status"]:8} {r["id"]} {r["name"][:70]}: {r["metrics"] or r.get("error", "")}')
    return 0 if all(r["status"] == "PASS" for r in slim) else 1


if __name__ == "__main__":
    sys.exit(main())
