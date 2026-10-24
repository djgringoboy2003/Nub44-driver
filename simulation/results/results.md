# Simulation results

Behavioural cycle-averaged model (see `simulation/run_sims.py` docstring for
every assumption). PASS means the metric met its limit inside this model only.

| ID | Test | Metrics | Limit | Status |
|---|---|---|---|---|
| SIM-01 | Power-on, nominal battery 3.7 V, typical diode | steady_current_a=3.997, overshoot_pct=0.0002557, peak_a=3.997 | overshoot <= 10 % (REQ-OUT-05), steady current within 5 % of 4.0 A | **PASS** |
| SIM-02 | Power-on at 3.15 V (just above the 3.08 V hardware UVLO), maximum-Vf diode | steady_current_a=3.997, overshoot_pct=0.0002397, peak_inductor_a=6.353 | overshoot <= 10 %, current within 5 %, peak inductor current < ILIM min 10.2 A | **PASS** |
| SIM-03 | Current regulation across battery 3.0-4.2 V and diode Vf corners (incl. Vf below Vbat) | 3.0V_min=3.997, 3.0V_typ=3.997, 3.0V_max=3.997, 3.7V_min=3.996, 3.7V_typ=3.996, 3.7V_max=3.997, 4.2V_min=3.997, 4.2V_typ=3.997, 4.2V_max=3.997 | model-level regulation within 2 % at every corner (tolerances excluded) | **PASS** |
| SIM-04 | Input voltage reduction (4.0 -> 3.2 V over 1 ms, 40 mOhm source) | max_current_deviation_pct=2.629 | deviation <= 5 % | **PASS** |
| SIM-05 | Load variation: diode Vf drops 0.15 V over 2 ms (faster than diode thermal time constants) | max_current_deviation_pct=0.08351 | deviation <= 5 % | **PASS** |
| SIM-06 | Flash transitions at full battery 4.2 V with lowest-Vf diode (Vf < Vbat region) | peak_current_a=3.997, turn_off_to_50mA_s=0.0004913 | peak <= 4.4 A on every turn-on; current < 50 mA within 2 ms of disable | **PASS** |
| SIM-07 | Fault shutdown: interlock opens during emission | time_to_50mA_s=6.462e-05 | < 2 ms | **PASS** |
| SIM-08 | Output short-circuit (10 mOhm) during emission | peak_inductor_current_a=12.57, settled_output_current_a=3.997 | inductor current < 25 A cycle-by-cycle peak limit; output current settles <= 5.2 A (backup ceiling) | **PASS** |
| SIM-09 | Open load (diode disconnected) during emission, hardware backstop only | peak_vout_v=6.71 | VOUT peak < 10 V (16 V-rated capacitors, 2x margin) | **PASS** |
| SIM-10 | Reverse battery (-4.2 V): P-FET blocks (body diode reverse-biased, Vgs = 0) | reverse_current_a=2.492e-07, vbat_node_v=-4.985e-07 | reverse current < 1 mA | **PASS** |
| SIM-11 | Control-loop response (linearised model, 12 corners) | min_phase_margin_deg=111.7, min_gain_margin_db=12.09 | PM >= 50 deg, GM >= 10 dB (time-domain step tests SIM-04/05 corroborate) | **PASS** |

Plots: `simulation/results/SIM-*.png`.
