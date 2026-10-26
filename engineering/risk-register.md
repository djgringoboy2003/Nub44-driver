# Engineering risk register

Risks are uncertainties that need evidence, a decision or a mitigation; confirmed defects live in
[reports/comprehensive-project-audit.md](../reports/comprehensive-project-audit.md). Likelihood (L) and impact (I)
are rated 1 (low) to 3 (high); score = L × I. "Evidence that closes it" names the measurement or decision, never a
calculation alone.

| ID | Risk | L | I | Score | Mitigation in place | Evidence that closes it | Owner / status |
|---|---|---|---|---|---|---|---|
| R-01 | 4.0 A exceeds the NUBM44 typical 3.0 A; shortened diode life or catastrophic optical damage | 2 | 3 | 6 | Owner decision DD-13; 3.0/3.5 A builds by R8 only; T4.2 first light at 3.0 A | Owner acceptance recorded (2026-10-25) | Owner: accepted |
| R-02 | Efficiency below the ≥ 94 % target (estimate 94.1 % with evaluation copper) | 2 | 2 | 4 | Loss model and routed-copper estimate; DD-26 | T1.7 bench efficiency | Open until Gate G |
| R-03 | TPS552882 CC pin not active-low (datasheet silent; sibling TPS552892 states active-low) | 1 | 2 | 2 | Firmware reads CC only while enabled; hardware ISP/ISN limit does not depend on it | T1.10 | Open until Gate G |
| R-04 | Hold-up time (C16 10 µF) and AC2 detection do not give the intended < 0.5 s mode-change window | 2 | 1 | 2 | Firmware gap debounce and classification (holdup.c); long gaps reset to continuous | T1.8, T1.9 | Open until Gate G |
| R-05 | U1 custom footprint (from PDF vectors) or L1 (XGL5030 on XAL5030 pattern) does not match the parts | 1 | 3 | 3 | DD-20 notes required review; release check lists open footprint reviews as blockers | Independent footprint review against manufacturer drawings; PCBWay DFM | Open (release blocker) |
| R-06 | U1 junction temperature high because the RPM0026A centre pads have no via-in-pad (DD-16) | 2 | 2 | 4 | Bridged pads, layout review, thermal bench tests T2.7/T2.12 | T2.7, T2.12 thermal data | Open until Gate G |
| R-07 | Compact 22 mm board cannot be completed on a 4-layer through-via stack-up | 3 | 2 | 6 | Parked (DD-27); strategy comparison in `pcb-review-2026-10-26.md` | Owner choice of direction + HDI quote or re-architecture result | Owner decision pending |
| R-08 | Supplier shortage (SiSS23DN at 220 pcs on 2026-10-24; DMN22M5UFG stock 0) | 2 | 2 | 4 | Alternates listed (different land patterns flagged) | Stock check at order time | Open |
| R-09 | Averaged simulation model misses switching effects; inner-loop and ISP/ISN loop strengths assumed | 2 | 2 | 4 | Model-level wording; FRA cross-check of the loop (SIM-11); sensitivity sweep | T1.3, T2.9, T2.11 waveforms | Open until Gate G |
| R-10 | ADC/DAC reference tolerance (±2–3 %) shifts the 3.2/3.1/2.9 V battery thresholds and the 5.6 V trip | 2 | 1 | 2 | Ratiometric VDD measurement with INT11V; thresholds have hardware backstops (UVLO 2.83 V, Zener) | T1.11 VBAT reading vs DMM; T2.6 | Open until Gate G |
| R-11 | Battery contact resistance above 20 mΩ starves the converter at low charge | 2 | 2 | 4 | Contact design notes; firmware low-battery cut-off | T3.2 | Open until Gate G |
| R-12 | PCBWay centroid rotation convention differs from KiCad's (bottom-side parts misrotated) | 2 | 2 | 4 | Exporter cross-checks against KiCad; iBOM and assembly PDFs in package | PCBWay DFM/assembly review before order | Open (order-time) |
| R-13 | Q6 gate overstress (VGSS ±6 V) if VOUT exceeds about 12 V in a multiple fault | 1 | 2 | 2 | AC0 firmware trip at 5.6 V acts first; Zener backstop normally limits VOUT to about 7 V | Owner decision on a gate clamp for the next revision | Documented |
| R-14 | Board NTC position not representative of the hottest part (U1, Q1) | 2 | 2 | 4 | Board limit 85 °C, IC thermal shutdown 175 °C | T2.7 thermocouple vs NTC reading | Open until Gate G |
| R-15 | Laser diode hot-plugged or disconnected under power (DD-11) | 2 | 3 | 6 | Bleeder, clamp diode, instructions; OV trip and Zener backstop | Procedure discipline (test plan §1) | Procedural |
| R-16 | Output/input capacitor DC-bias retention below the assumed 50–55 % | 2 | 1 | 2 | Ripple check 8.9 % vs 10 % limit; sensitivity sweep | T1.6 ripple | Open until Gate G |
| R-17 | External wiring (interlock, NTC, switch) couples ESD or noise into MCU pins | 2 | 2 | 4 | 47 kΩ series on interlock sense; debounce and sensor confirmation times in firmware | ESD/handling test on the evaluation board (not yet planned) | Open |
| R-18 | Fuses not programmed (BOD disabled by default) on the first prototype | 2 | 2 | 4 | Fuse values recorded in firmware; T0.4 fuse verification step | T0.4 readback | Open until bench |
| R-19 | Gerber package of an incomplete board ordered by mistake | 1 | 2 | 2 | Release levels, DO_NOT_FABRICATE marker in incomplete packages | n/a (control) | Mitigated |
| R-20 | Current-loop gain margin below 10 dB when tolerances stack (SIM-12: 9.5 dB averaged model; AUD-SIM-04) | 1 | 2 | 2 | PM stays above 109 deg in every case; nominal GM 11.9-12.6 dB; Rc 1.0 kOhm option simulated (11.1 dB) | Owner decision; loop measurement on the evaluation prototype (T2.11) | Owner decision pending |
| R-21 | R16 (indicator LED resistor) opens after a short on the external LED pad, silently removing the emission indicator (AUD-SRC-04) | 1 | 2 | 2 | Wiring instructions; LED is external | Owner decision on a larger resistor package or value | Documented |
| R-22 | Switching noise coupled into U1's two-layer ISP/ISN loop toggles the CC flag; firmware latches fault 6 (nuisance trips) | 2 | 1 | 2 | Hardware current limit unaffected; INA186 branch is a tight pair; CC read only 3 ms after enable | T1.10, T2.4, T2.11 on the evaluation board; re-route as a same-layer pair in the next spin if seen (pcb-review-2026-10-26.md) | Open until Gate G |
