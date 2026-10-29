"""Preliminary budget current-loop sensitivity and an independent ngspice AC check.

The TPS54821 typical transconductances and INA186 typical bandwidth are sourced.
The laser incremental resistance, effective capacitance and inner pole are study
assumptions. Passing this model does not verify the actual switching circuit.
"""
from __future__ import annotations

import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))
from nubm44 import evidence, paths  # noqa: E402
from nubm44.variants import sources_for  # noqa: E402

PARAMETERS = sources_for("budget-2s").parameters
OUT = ROOT / "reports/budget-2s"


def transfer(p: dict, frequency_hz, *, cout: float, rd: float, gm_ea_factor: float = 1,
             gm_mod_factor: float = 1, sensor_hz: float | None = None):
    b, cs, loop = p["buck"], p["current_sense"], p["loop"]
    s = 2j * np.pi * np.asarray(frequency_hz)
    gm_ea = b["error_amplifier_gm_s_typ"] * gm_ea_factor
    gm_mod = b["modulator_gm_a_per_v_typ"] * gm_mod_factor
    ro = loop["error_amplifier_dc_gain_min"] / gm_ea
    zseries = loop["compensation_r_ohm"] + 1 / (s * loop["compensation_c_f"])
    zcomp = 1 / (1 / ro + 1 / zseries + s * loop["compensation_hf_c_f"])
    inner_hz = b["frequency_hz_min"] * loop["inner_pole_fraction_of_fsw"]
    hinner = 1 / (1 + s / (2 * np.pi * inner_hz))
    hload_current = 1 / (1 + s * rd * cout)
    hsense = cs["gain"] * cs["shunt_ohm"] / (1 + s / (2 * np.pi * (sensor_hz or cs["amplifier_bandwidth_hz_typ"])))
    divider = cs["fb_bottom_ohm"] / (cs["fb_top_ohm"] + cs["fb_bottom_ohm"])
    return gm_ea * zcomp * gm_mod * hinner * hload_current * hsense * divider


def _crossings(x: np.ndarray, y: np.ndarray, target: float) -> list[tuple[float, int, float]]:
    found = []
    for i in np.where((y[:-1] - target) * (y[1:] - target) <= 0)[0]:
        if y[i] == y[i + 1]:
            continue
        frac = float((target - y[i]) / (y[i + 1] - y[i]))
        if 0 <= frac <= 1:
            found.append((float(math.exp(math.log(x[i]) + frac * math.log(x[i + 1] / x[i]))), int(i), frac))
    return found


def margins(frequency_hz, response) -> dict:
    f, h = np.asarray(frequency_hz), np.asarray(response)
    if (f.ndim != 1 or h.ndim != 1 or len(f) < 3 or len(f) != len(h)
            or not np.all(np.isfinite(h)) or not np.all(np.isfinite(f))
            or np.any(f <= 0) or np.any(np.diff(f) <= 0) or np.any(np.abs(h) == 0)):
        raise ValueError("malformed frequency response")
    gain_db = 20 * np.log10(np.abs(h))
    phase_deg = np.unwrap(np.angle(h)) * 180 / np.pi
    unity = _crossings(f, gain_db, 0)
    if not unity:
        return {"phase_margin_deg": None, "gain_margin_db": None,
                "unity_crossings_hz": [], "reason": "no unity crossing in evaluated interval"}
    pms = [180 + phase_deg[i] + frac * (phase_deg[i + 1] - phase_deg[i]) for _, i, frac in unity]
    pcross = _crossings(f, phase_deg, -180)
    gms = [-(gain_db[i] + frac * (gain_db[i + 1] - gain_db[i])) for _, i, frac in pcross]
    return {"phase_margin_deg": float(min(pms)), "gain_margin_db": float(min(gms)) if gms else None,
            "unity_crossings_hz": [x[0] for x in unity], "phase_crossings_hz": [x[0] for x in pcross],
            "reason": "evaluated interval only; no inferred infinite margin" if not pcross else ""}


def sweep(p: dict) -> dict:
    loop = p["loop"]
    f = np.geomspace(loop["sweep_frequency_hz_min"], loop["sweep_frequency_hz_max"], loop["sweep_frequency_points"])
    rows = []
    for cout, rd, ge, gm, sensor in itertools.product(
            loop["output_cap_f_sweep"], loop["load_incremental_ohm_sweep"],
            loop["error_amplifier_gm_factors"], loop["modulator_gm_factors"], loop["sensor_bandwidth_hz_sweep"]):
        args = {"cout": cout, "rd": rd, "gm_ea_factor": ge, "gm_mod_factor": gm, "sensor_hz": sensor}
        margin = margins(f, transfer(p, f, **args))
        pm, gmargin = margin["phase_margin_deg"], margin["gain_margin_db"]
        ok = pm is not None and gmargin is not None and pm >= loop["minimum_phase_margin_deg"] and gmargin >= loop["minimum_gain_margin_db"]
        rows.append({**args, **margin, "screen_pass": ok})
    return {"cases": rows, "case_count": len(rows), "screen_pass_count": sum(x["screen_pass"] for x in rows),
            "minimum_phase_margin_deg": min(x["phase_margin_deg"] for x in rows if x["phase_margin_deg"] is not None),
            "minimum_gain_margin_db": min(x["gain_margin_db"] for x in rows if x["gain_margin_db"] is not None),
            "qualification": "MODEL SENSITIVITY ONLY: assumed C, diode Rd and inner pole; typical gm/bandwidth, no switching/fault proof"}


def ngspice_netlist(p: dict) -> str:
    b, cs, loop = p["buck"], p["current_sense"], p["loop"]
    gm = b["error_amplifier_gm_s_typ"]
    rd, cout = loop["load_incremental_ohm_nominal"], p["output_energy"]["bulk_cap_f_nominal"]
    # Equivalent RC poles are computational model elements, not PCB components.
    ri = 1000
    ci = 1 / (2 * math.pi * b["frequency_hz_min"] * loop["inner_pole_fraction_of_fsw"] * ri)
    csense = 1 / (2 * math.pi * cs["amplifier_bandwidth_hz_typ"] * ri)
    return f"""Budget-2S open-loop small-signal model; study assumptions, no switching
VSTIM EXC 0 AC 1
GEA 0 COMP EXC 0 {gm:.12g}
RO COMP 0 {loop['error_amplifier_dc_gain_min']/gm:.12g}
RCOMP COMP CZ {loop['compensation_r_ohm']:.12g}
CCOMP CZ 0 {loop['compensation_c_f']:.12g}
CHF COMP 0 {loop['compensation_hf_c_f']:.12g}
EINNER CMD 0 COMP 0 1
RINNER CMD CMD_F {ri}
CINNER CMD_F 0 {ci:.12g}
GMOD 0 OUT CMD_F 0 {b['modulator_gm_a_per_v_typ']:.12g}
COUT OUT 0 {cout:.12g}
RLOAD OUT 0 {rd:.12g}
ESENSE RAW_CS 0 OUT 0 {cs['gain']*cs['shunt_ohm']/rd:.12g}
RSENSE RAW_CS CS_POLE {ri}
CSENSE CS_POLE 0 {csense:.12g}
EBUFFER CS_OUT 0 CS_POLE 0 1
RTOP CS_OUT FB {cs['fb_top_ohm']:.12g}
RBOTTOM FB 0 {cs['fb_bottom_ohm']:.12g}
.control
set wr_vecnames
set wr_singlescale
ac dec {loop['ngspice_points_per_decade']} {loop['sweep_frequency_hz_min']} {loop['sweep_frequency_hz_max']}
wrdata loop-ac.txt v(FB)
quit
.endc
.end
"""


def run_ngspice(p: dict) -> dict:
    net, raw, log = OUT / "loop-ac.cir", OUT / "loop-ac.txt", OUT / "loop-ac.log"
    net.write_text(ngspice_netlist(p), encoding="utf-8")
    raw.unlink(missing_ok=True)
    proc = subprocess.run([str(paths.ngspice()), "-b", "-o", log.name, net.name], cwd=OUT,
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not raw.is_file():
        raise RuntimeError(f"ngspice failed: rc={proc.returncode}; see {log}")
    data = np.loadtxt(raw, skiprows=1)
    if data.ndim != 2 or data.shape[1] != 3 or len(data) < 100 or not np.all(np.isfinite(data)):
        raise ValueError("ngspice AC output malformed")
    expected = transfer(p, data[:, 0], cout=p["output_energy"]["bulk_cap_f_nominal"],
                        rd=p["loop"]["load_incremental_ohm_nominal"])
    actual = data[:, 1] + 1j * data[:, 2]
    error = float(np.max(np.abs(actual - expected) / np.maximum(np.abs(expected), 1e-15)))
    tol = p["loop"]["ngspice_agreement_relative_tolerance"]
    return {"command_returncode": proc.returncode, "sample_count": len(data),
            "maximum_complex_relative_error": error, "agreement_tolerance": tol,
            "agreement_pass": error <= tol, "nominal_margins": margins(data[:, 0], actual)}


def markdown(result: dict, p: dict) -> str:
    s, n = result["sweep"], result["ngspice"]
    loop, b, cs = p["loop"], p["buck"], p["current_sense"]
    vals = lambda key, scale=1: "/".join(f"{v*scale:g}" for v in loop[key])
    return f"""# Budget-2S preliminary current-loop model

Generated by `automation/budget/loop_model.py`; do not hand-edit.

**Model sensitivity only.** A successful run does not qualify the real circuit or close BUD-LOOP-01.

The candidate type-II network is {loop['compensation_r_ohm']:g} Ω / {loop['compensation_c_f']*1e6:g} µF
with {loop['compensation_hf_c_f']*1e9:g} nF at COMP. It uses BUD-01's typical error-amplifier
transconductance ({b['error_amplifier_gm_s_typ']*1e3:g} mS), typical current modulator
({b['modulator_gm_a_per_v_typ']:g} A/V), minimum EA DC gain {loop['error_amplifier_dc_gain_min']:g}
and PREORDER-07's typical INA186A2 bandwidth ({cs['amplifier_bandwidth_hz_typ']/1e3:g} kHz).
All design values are in the budget YAML.

The incremental diode/load resistance ({vals('load_incremental_ohm_sweep')} Ω), effective output
capacitance ({vals('output_cap_f_sweep', 1e6)} µF), EA gm factors ({vals('error_amplifier_gm_factors')}),
modulator gm factors ({vals('modulator_gm_factors')}), sensor-bandwidth sensitivity
({vals('sensor_bandwidth_hz_sweep', 0.001)} kHz) and assumed inner pole at
{loop['inner_pole_fraction_of_fsw']:g} times the minimum switching frequency are **analysis assumptions**,
not guaranteed data or measurements.
The load-current transfer is `1 / (1 + s*Rd*Cout)` for an ideal controlled current source feeding
the output capacitor and incremental load. The sensor contributes its gain/shunt factor and one pole;
the exact divider and finite error-amplifier output resistance are included.

| Result | Actual tool result |
|---|---:|
| Sensitivity cases | {s['case_count']} |
| Cases meeting ≥{loop['minimum_phase_margin_deg']:g}° phase / ≥{loop['minimum_gain_margin_db']:g} dB gain screen | {s['screen_pass_count']} |
| Minimum phase margin in these cases | {s['minimum_phase_margin_deg']:.3f}° |
| Minimum gain margin in these cases | {s['minimum_gain_margin_db']:.3f} dB |
| ngspice process return code | {n['command_returncode']} |
| ngspice AC samples | {n['sample_count']} |
| Maximum complex relative error versus independent equation | {n['maximum_complex_relative_error']:.8g} |
| Required relative agreement | {n['agreement_tolerance']:.8g} |
| Equation / ngspice agreement | {'PASS' if n['agreement_pass'] else 'FAIL'} |

This is a consistency check between two implementations of the same assumed model, not independent
verification of TPS54821 internal dynamics. No infinite gain margin is awarded when a phase crossing
is absent; the study must contain a unity and a phase crossing to pass its margin screen.

Still OPEN: measured diode incremental impedance; exact capacitor DC-bias/temperature/ESR envelope;
inner sampled-data dynamics and slope compensation at high duty; amplifier delay and higher poles;
COMP range/clamps; SS tracking/current ramp; startup, flashing, disconnect sequencing, output-open,
short and reconnected-load switching transients; component tolerances outside these assumed sweeps.
In particular, this small-signal model contains no mechanism to prove a ≤4.4 A reconnect peak.

Use the generated JSON for every corner, `.cir` for the inspectable ngspice circuit and `.txt` for its
raw AC output. Hash evidence binds all results to the numeric sources and both model implementations.
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "loop-model-evidence.json"
    manifest.unlink(missing_ok=True)
    try:
        p = yaml.safe_load(PARAMETERS.read_text(encoding="utf-8"))
        result = {"schema": "nubm44-budget-loop-model.v1", "physical_qualification": "OPEN",
                  "sweep": sweep(p), "ngspice": run_ngspice(p)}
    except (KeyError, TypeError, ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"budget loop model failed: {exc}", file=sys.stderr)
        return 2
    jp, md = OUT / "loop-model.json", OUT / "loop-model.md"
    jp.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    md.write_text(markdown(result, p), encoding="utf-8")
    outputs = [jp, md, OUT / "loop-ac.cir", OUT / "loop-ac.txt", OUT / "loop-ac.log"]
    evidence.write(evidence.build("budget-loop-model", inputs=[PARAMETERS, Path(__file__),
        ROOT / "automation/nubm44/variants.py", ROOT / "automation/nubm44/evidence.py",
        ROOT / "automation/nubm44/paths.py", ROOT / "research/sources/budget-driver-sources.md"],
        outputs=outputs, tools={**evidence.python_tools(["numpy", "PyYAML"]),
                              "ngspice": evidence.command_version([str(paths.ngspice()), "--version"])}), manifest)
    s, n = result["sweep"], result["ngspice"]
    print(f"Budget preliminary loop: {s['screen_pass_count']}/{s['case_count']} sensitivity cases; "
          f"min PM {s['minimum_phase_margin_deg']:.3f} deg / GM {s['minimum_gain_margin_db']:.3f} dB; "
          f"ngspice rc={n['command_returncode']}, agreement={n['agreement_pass']}; physical qualification OPEN.")
    return 0 if s["screen_pass_count"] == s["case_count"] and n["agreement_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
