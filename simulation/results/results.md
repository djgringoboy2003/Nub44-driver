# Simulation results

Behavioural cycle-averaged model (see `simulation/run_sims.py` docstring for
every assumption). PASS means the metric met its limit inside this model only: these are predictions,
not measurements, and the model has no switching ripple, saturation or dead time.

| ID | Test | Metrics | Limit | Status |
|---|---|---|---|---|
| SIM-01 | Power-on, nominal battery 3.7 V, typical diode | steady_current_a=4.479, overshoot_pct=0.0002314, peak_a=4.479 | overshoot <= 10 % (REQ-OUT-05), steady current within 5 % of 4.5 A | **PASS** |
| SIM-02 | Power-on at 3.15 V (just above the 3.08 V hardware UVLO), maximum-Vf diode | steady_current_a=4.479, overshoot_pct=0.0002139, peak_inductor_a=7.329 | overshoot <= 10 %, current within 5 %, peak inductor current < ILIM min 10.2 A | **PASS** |
| SIM-03 | Current regulation across battery 3.0-4.2 V and diode Vf corners (incl. Vf below Vbat) | 3.0V_min=4.479, 3.0V_typ=4.479, 3.0V_max=4.479, 3.7V_min=4.479, 3.7V_typ=4.479, 3.7V_max=4.479, 4.2V_min=4.479, 4.2V_typ=4.479, 4.2V_max=4.479 | model-level regulation within 2 % at every corner (tolerances excluded) | **PASS** |
| SIM-04 | Input voltage reduction (4.0 -> 3.2 V over 1 ms, 40 mOhm source) | max_current_deviation_pct=3.515 | deviation <= 5 % | **PASS** |
| SIM-05 | Load variation: diode Vf drops 0.15 V over 2 ms (faster than diode thermal time constants) | max_current_deviation_pct=0.4618 | deviation <= 5 % | **PASS** |
| SIM-06 | Flash transitions at full battery 4.2 V with lowest-Vf diode (Vf < Vbat region) | peak_current_a=4.479, turn_off_to_50mA_s=0.0004915 | peak <= 4.95 A on every turn-on; current < 50 mA within 2 ms of disable | **PASS** |
| SIM-07 | Fault shutdown: interlock opens during emission | time_to_50mA_s=6.491e-05 | < 2 ms | **PASS** |
| SIM-08 | Output short-circuit (10 mOhm) during emission | peak_inductor_current_a=13.43, settled_output_current_a=4.479 | averaged inductor current < 25 A (ILIM_PK typ, SLVSFC5 p.7); output current settles <= 5.2 A (backup ceiling) | **PASS** |
| SIM-09 | Open load (diode disconnected) during emission, hardware backstop only | peak_vout_v=6.741 | VOUT peak < 10 V (16 V-rated capacitors, 2x margin) | **PASS** |
| SIM-10 | Reverse battery (-4.2 V): P-FET blocks (body diode reverse-biased, Vgs = 0) | reverse_current_a=2.492e-07, vbat_node_v=-4.985e-07 | reverse current < 1 mA | **PASS** |
| SIM-11 | Current-loop gain by frequency-response analysis of the averaged deck (3.7 V typ, 3.0 V max-Vf, 4.2 V min-Vf), compared with the Python model | 3.7V_typ_f_cross_hz=2108, 3.7V_typ_phase_margin_deg=117.4, 3.7V_typ_gain_margin_db=13.19, 3.0V_max_f_cross_hz=1339, 3.0V_max_phase_margin_deg=110.4, 3.0V_max_gain_margin_db=13.24, 4.2V_min_f_cross_hz=2978, 4.2V_min_phase_margin_deg=120.9, 4.2V_min_gain_margin_db=12.78, python_model_3.7V_typ_f_cross_hz=2324, python_model_3.7V_typ_phase_margin_deg=121.4, fc_difference_pct=-9.3, pm_difference_deg=-4.1 | PM >= 50 deg at every corner; GM >= 10 dB (or >= 10 dB attenuation at 100 kHz if the phase stays above -180 deg); Python-model difference reported, not judged | **PASS** |
| SIM-12 | Loop sensitivity at 3.0 V, max-Vf diode: output capacitance (DC bias), inductance, error-amplifier gm, CSA bandwidth and the assumed inner-loop gain | min_phase_margin_deg=106.3, cases_passing=11, cases=11 | every case: PM >= 50 deg and the gain-margin rule of SIM-11 | **PASS** |

## SIM-12 sensitivity cases

| Case | fc (Hz) | PM (deg) | GM (dB) | |T| at 100 kHz (dB) | Pass |
|---|---|---|---|---|---|
| nominal | 1338.49 | 110.4 | 13.25 | -29.19 | yes |
| C_out retention 0.35/0.55 | 1341.44 | 111.8 | 11.69 | -25.25 | yes |
| C_out retention 0.75/0.55 | 1335.19 | 109.01 | 14.66 | -31.93 | yes |
| L -20 % | 1337.7 | 110.69 | 14.67 | -29.53 | yes |
| L +20 % | 1339.55 | 110.12 | 12.03 | -28.99 | yes |
| gm -20 % | 1016.06 | 106.34 | 15.19 | -31.13 | yes |
| gm +20 % | 1728.97 | 114.42 | 11.67 | -27.61 | yes |
| CSA bandwidth -30 % | 1337.44 | 109.5 | 14.04 | -32.02 | yes |
| inner loop gain x0.5 (assumption) | 1335.54 | 109.07 | 13.06 | -34.32 | yes |
| inner loop gain x2 (assumption) | 1340.14 | 111.07 | 13.92 | -25.63 | yes |
| combined: low C, high L, high gm, slow CSA | 1735.5 | 114.69 | 10.06 | -26.28 | yes |

Plots: `simulation/results/SIM-*.png`. Evidence manifest: `simulation/results/evidence.json`.
