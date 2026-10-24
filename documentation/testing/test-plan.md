# Bench test plan (Gate G: physical validation)

Gate G closes only when these tests have been run on assembled prototypes and the results are recorded in
`documentation/testing/results/`. Simulation and calculation results (`simulation/results/results.md`,
`engineering/calculations/power-stage-results.md`) are predictions to compare against, not evidence.

## 1. Safety (read before powering anything)

- The NUBM44 is a **Class 4** laser source (several watts at ~445 nm). Direct and diffuse reflections can cause
  permanent eye injury and burns.
- **Every test in stages 1–3 uses a dummy load, never a laser diode.**
- Laser tests (stage 4) need all of the following:
  - a controlled area with the door interlocked and warning signs;
  - laser safety eyewear rated for 445 nm, OD ≥ 6, for everyone present;
  - a fixed beam path into a beam dump, with non-reflective surroundings;
  - the driver's external interlock loop wired to the room or door interlock;
  - a responsible person who knows the local laser safety rules (e.g. IEC 60825-1, ANSI Z136, or your national
    equivalent).
- Use a current-limited bench supply in place of a cell until stage 3. Lithium cells can deliver > 30 A into a fault.
- Never connect or disconnect the laser diode while the driver is powered (DD-11, SIM-09).

## 2. Equipment

| Item | Purpose |
|---|---|
| Bench supply, 0–6 V, ≥ 10 A, current limit | Battery substitute; set the limit to 10 A for normal tests, 1 A for first power-up |
| Dummy load: a string of power diodes or a laser-diode simulator giving ≈ 4.2–4.8 V at 4 A (for example 6 × 1N5408 in series, on a heatsink; check its I–V first) | Representative of the diode's I–V knee and dynamic resistance; a resistor alone does not reproduce the knee |
| Low-ohm shunt or current probe (≥ 20 MHz) | Laser current waveform; overshoot and ripple |
| Oscilloscope, 4 channels | VOUT, laser current, EN pin, VIN |
| Two DMMs, 4-wire capable | Efficiency (input and output V and I) |
| Thermocouple or thermal camera | IC, inductor, FETs, shunt, board temperature |
| SerialUPDI programmer | Firmware load (TP6/TP7/TP8) |
| Relay or MOSFET switch in the supply line | Simulates a tail-switch click (mode change, hold-up) |

## 3. Test list

**Stage 0: assembly inspection (no power).**

| ID | Test | Method | Pass criterion | Req. |
|---|---|---|---|---|
| T0.1 | Visual / X-ray inspection of U1 (VQFN-HR), U3 (VQFN) | Microscope; X-ray if available | No bridges, centre pads soldered | REQ-PCB-01 |
| T0.2 | Polarity marks | Compare with `manufacturing/pcbway/<variant>/drawings/assembly_*.pdf` | All diodes, ICs and FETs oriented correctly | REQ-MFG-02 |
| T0.3 | Short check VBAT–GND, VOUT–GND, LD+–LD− | DMM | > 1 kΩ (bleeder 4.7 kΩ on VOUT) | — |

**Stage 1: power-up on a bench supply with a dummy load.**

| ID | Test | Method | Pass criterion | Req. / prediction |
|---|---|---|---|---|
| T1.1 | First power-up, 3.7 V, 1 A limit, laser output open | Measure supply current; program firmware | Idle current < 2 mA; no output voltage on VOUT | REQ-SAFE-03 |
| T1.2 | Default-off / emission delay | Dummy load connected, interlock closed; scope laser current from power-up | Current < 10 mA for ≥ 2.0 s, then a ramp | REQ-SAFE-03, firmware |
| T1.3 | Soft start and overshoot | Scope laser current at turn-on: 3.15 V, 3.7 V, 4.2 V | Peak ≤ 4.4 A (≤ 10 % overshoot); ramp ≈ 4 ms | REQ-OUT-05 (SIM-01/02) |
| T1.4 | Regulation accuracy | Steady current at 3.0/3.3/3.7/4.0/4.2 V × dummy loads with low/high Vf | 4.0 A ± 5 % (design ± 3.6 %) | REQ-OUT-02/03 (SIM-03) |
| T1.5 | Vf below Vbat (buck mode) | Dummy load with Vf ≈ 3.8 V at 4 A, supply 4.2 V | Current still regulated | REQ-OUT-02 |
| T1.6 | Ripple | Laser-current ripple at 3.0 V and 4.2 V | ≤ 10 % p-p (prediction 8.9 % at 2.83 V) | power-stage calc |
| T1.7 | Efficiency | 4-wire V and I at the board input and output: 3.0, 3.7, 4.0 V | Record; targets > 95 % at 4.0 V (predicted 94.6 %, AT-RISK) and ≥ 86 % at 3.0 V (predicted 91.3 %) | REQ-PWR-02/03 |
| T1.8 | Flash mode | Short supply interruption (< 0.5 s) via the relay; check 2 Hz / 50 % | Mode advances; no overshoot at each flash; off < 1 ms to < 50 mA | REQ-MODE-02/04 (SIM-06) |
| T1.9 | Mode memory timing | Interruptions of 0.1 / 0.3 / 0.6 / 1.0 s | < 0.5 s advances mode, > 1 s resets (record the actual threshold) | firmware |
| T1.10 | CC pin polarity | Force the backup limit (lower R_FB_TOP temporarily, or a light test load with a CSA fault injected) | Confirm the firmware's active-low assumption | firmware README |

**Stage 2: protection and faults (dummy load).**

| ID | Test | Method | Pass criterion | Req. / prediction |
|---|---|---|---|---|
| T2.1 | Interlock | Open the loop during emission | Current < 50 mA within 1 ms; no restart until power cycle | REQ-SAFE-02 (SIM-07) |
| T2.2 | Open load | Disconnect the dummy load during emission (use a relay, not by hand) | VOUT peak < 7 V; firmware fault latched | REQ-SAFE-09 (SIM-09) |
| T2.3 | Short circuit | Short the output through a relay during emission | Output current ≤ 5.2 A; firmware latches; no damage | REQ-SAFE-10 (SIM-08) |
| T2.4 | Backup current ceiling | Disable the INA186 path (lift R8) | Output limited to 4.8–5.2 A by ISP/ISN; CC flag asserted | REQ-SAFE-07 |
| T2.5 | Reverse polarity | Apply −4.2 V, 1 A current limit, then 10 A for 1 s | Reverse current < 1 mA; board works afterwards | REQ-PROT-01 (SIM-10) |
| T2.6 | UVLO | Ramp the supply down and up slowly | Converter off at 2.83 V ± 3 %, on at 3.08 V ± 3 %; firmware warns at 3.1 V and latches at 2.9 V | REQ-BAT-05 |
| T2.7 | Thermal | 4 A continuous at 3.0 V. Board clamped in an aluminium pill (or a heat-sunk ring fixture) and also in still air. Thermocouples on U1, L1, Q1, RS1 | Record steady temperatures; U1 Tj estimate < 125 °C; firmware stops at 85 °C board | REQ-SAFE-08, DD-15/16 |
| T2.8 | Hot insertion | Connect a charged cell through a spring contact (no laser) | VIN/VMCU overshoot below 6 V (MCU abs max) | — |

**Stage 3: battery operation (dummy load).**

| ID | Test | Method | Pass criterion | Req. |
|---|---|---|---|---|
| T3.1 | Real cells | 18650 (≥ 15 A CDR) and 21700, full to cut-off, through spring and ring contacts | Regulation held to cut-off; cut-off at ≥ 2.83 V loaded; record run time | REQ-BAT-01..05 |
| T3.2 | Contact resistance | 4-wire across spring and ring at 8 A | Total ≤ 20 mΩ (bypass the springs) | battery research |
| T3.3 | Polarity confirmation | Owner's host: verify spring = B+, ring = B− | Confirms REQ-BAT-04 (unblocks Gate F) | REQ-BAT-04 |

**Stage 4: laser diode (controlled area only, all section 1 measures in place).**

| ID | Test | Method | Pass criterion |
|---|---|---|---|
| T4.1 | Diode check | Confirm the NUBM44 case is isolated from both pins (DMM) | Open circuit case–pin |
| T4.2 | First light at reduced current | Build with R8 for 3.0 A first | Stable output; case temperature logged |
| T4.3 | Full current | 4.0 A (or the owner-chosen setpoint) with the diode in a copper module | Case < 65 °C at the intended duty cycle; optical power recorded |

## 4. Recording

For each test, record the date, board serial, firmware hash, instrument list, raw scope captures and a PASS/FAIL
against the criterion. Save these in `documentation/testing/results/<serial>/` and update `engineering/requirements.md`
from `NEEDS-TEST` to `VERIFIED-TEST`. Then run `scripts/validate.ps1`.
