# Simulation results

Behavioural cycle-averaged model (see `simulation/run_sims.py` docstring for
every assumption). PASS means the metric met its limit inside this model only: these are predictions,
not measurements, and the model has no switching ripple, saturation or dead time.

| ID | Test | Metrics | Limit | Status |
|---|---|---|---|---|
| SIM-01 | Power-on, nominal battery 3.7 V, typical diode | steady_current_a=3.997, overshoot_pct=0.0002557, peak_a=3.997 | overshoot <= 10 % (REQ-OUT-05), steady current within 5 % of 4.0 A | **PASS** |
| SIM-02 | Power-on at 3.15 V (just above the 3.08 V hardware UVLO), maximum-Vf diode | steady_current_a=3.997, overshoot_pct=0.0002397, peak_inductor_a=6.353 | overshoot <= 10 %, current within 5 %, peak inductor current < ILIM min 10.2 A | **PASS** |
| SIM-03 | Current regulation across battery 3.0-4.2 V and diode Vf corners (incl. Vf below Vbat) | 3.0V_min=3.997, 3.0V_typ=3.997, 3.0V_max=3.997, 3.7V_min=3.996, 3.7V_typ=3.996, 3.7V_max=3.997, 4.2V_min=3.997, 4.2V_typ=3.997, 4.2V_max=3.997 | model-level regulation within 2 % at every corner (tolerances excluded) | **PASS** |
| SIM-04 | Input voltage reduction (4.0 -> 3.2 V over 1 ms, 40 mOhm source) | max_current_deviation_pct=2.629 | deviation <= 5 % | **PASS** |
| SIM-05 | Load variation: diode Vf drops 0.15 V over 2 ms (faster than diode thermal time constants) | max_current_deviation_pct=0.08351 | deviation <= 5 % | **PASS** |
| SIM-06 | Flash transitions at full battery 4.2 V with lowest-Vf diode (Vf < Vbat region) | peak_current_a=3.997, turn_off_to_50mA_s=0.0004913 | peak <= 4.4 A on every turn-on; current < 50 mA within 2 ms of disable | **PASS** |
| SIM-07 | Fault shutdown: interlock opens during emission | time_to_50mA_s=6.462e-05 | < 2 ms | **PASS** |
| SIM-08 | Output short-circuit (10 mOhm) during emission | peak_inductor_current_a=12.57, settled_output_current_a=3.997 | averaged inductor current < 25 A (ILIM_PK typ, SLVSFC5 p.7); output current settles <= 5.2 A (backup ceiling) | **PASS** |
| SIM-09 | Open load (diode disconnected) during emission, hardware backstop only | peak_vout_v=6.71 | VOUT peak < 10 V (16 V-rated capacitors, 2x margin) | **PASS** |
| SIM-10 | Reverse battery (-4.2 V): P-FET blocks (body diode reverse-biased, Vgs = 0) | reverse_current_a=2.492e-07, vbat_node_v=-4.985e-07 | reverse current < 1 mA | **PASS** |
| SIM-11 | Current-loop gain by frequency-response analysis of the averaged deck (3.7 V typ, 3.0 V max-Vf, 4.2 V min-Vf), compared with the Python model | 3.7V_typ_f_cross_hz=2855, 3.7V_typ_phase_margin_deg=121, 3.7V_typ_gain_margin_db=12.42, 3.0V_max_f_cross_hz=1696, 3.0V_max_phase_margin_deg=114.2, 3.0V_max_gain_margin_db=12.63, 4.2V_min_f_cross_hz=4294, 4.2V_min_phase_margin_deg=121.9, 4.2V_min_gain_margin_db=11.94, python_model_3.7V_typ_f_cross_hz=3272, python_model_3.7V_typ_phase_margin_deg=126, fc_difference_pct=-12.7, pm_difference_deg=-5 | PM >= 50 deg at every corner; GM >= 10 dB (or >= 10 dB attenuation at 100 kHz if the phase stays above -180 deg); Python-model difference reported, not judged | **PASS** |
| SIM-12 | Loop sensitivity at 3.0 V, max-Vf diode: output capacitance (DC bias), inductance, error-amplifier gm, CSA bandwidth and the assumed inner-loop gain | min_phase_margin_deg=109.5, cases_passing=10, cases=11 | every case: PM >= 50 deg and the gain-margin rule of SIM-11 | **FAIL** |

## SIM-12 sensitivity cases

| Case | fc (Hz) | PM (deg) | GM (dB) | |T| at 100 kHz (dB) | Pass |
|---|---|---|---|---|---|
| nominal | 1696.87 | 114.24 | 12.65 | -29.12 | yes |
| C_out retention 0.35/0.55 | 1704.27 | 116.06 | 11.13 | -25.18 | yes |
| C_out retention 0.75/0.55 | 1687.64 | 112.43 | 14.05 | -31.86 | yes |
| L -20 % | 1695.05 | 114.54 | 14.04 | -29.33 | yes |
| L +20 % | 1699.66 | 113.94 | 11.49 | -29.0 | yes |
| gm -20 % | 1252.04 | 109.47 | 14.59 | -31.06 | yes |
| gm +20 % | 2286.82 | 118.69 | 11.07 | -27.54 | yes |
| CSA bandwidth -30 % | 1693.52 | 113.08 | 13.42 | -31.95 | yes |
| inner loop gain x0.5 (assumption) | 1686.49 | 112.39 | 12.42 | -34.28 | yes |
| inner loop gain x2 (assumption) | 1700.78 | 115.16 | 13.41 | -25.51 | yes |
| combined: low C, high L, high gm, slow CSA | 2307.49 | 119.18 | 9.51 | -26.29 | NO |

Plots: `simulation/results/SIM-*.png`. Evidence manifest: `simulation/results/evidence.json`.
