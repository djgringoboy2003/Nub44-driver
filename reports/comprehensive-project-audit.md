# Comprehensive project audit

_Independent audit started 2026-10-26 on branch `audit/comprehensive-improvements` (base `main` at 3d04793).
This file is the single issue register for the audit; statuses are updated as fixes land. Risks that are not
defects live in [engineering/risk-register.md](../engineering/risk-register.md); the order of work is in
[engineering/improvement-roadmap.md](../engineering/improvement-roadmap.md); what was done, with test
results, is in [engineering/implementation-log.md](../engineering/implementation-log.md)._

## 1. Scope and method

Every finding below was checked against the repository, and hardware assumptions against the local datasheet
copies in `research/datasheets/` (git-ignored; source IDs in `research/source-index.md`). Previous reviews were
not taken as correct. No hardware was energised, no laser was operated and nothing was ordered.

- **Read:** every file named in the brief, plus the automation, export, sourcing, test and CAD-pipeline sources,
  the generated evidence, both routing checkpoints and the git history.
- **Datasheets consulted:** TPS552882 SLVSFC5 (LEAD-01), TPS552892 SLVSH28A (sibling, for the CC pin), ATtiny1616
  DS40001997C (LEAD-03), DMG1012T DS31783 (LEAD-04).
- **Classes:** **Defect** (confirmed wrong behaviour, reproducible or provable from the code and a datasheet),
  **Risk** (plausible problem that needs evidence; mirrored in the risk register), **Enhancement** (missing
  capability).
- **Severity:** critical (can cause unintended emission or injury), high (defeats or weakens a protection or a
  release control), medium (wrong behaviour or evidence with a bounded consequence), low (cosmetic, latent or
  documentation).

No critical finding was identified: every emission path keeps its hardware disables (interlock FET, over-voltage
Zener FET, ISP/ISN ceiling, default-off pull-up), which are independent of the firmware defects below.

## 2. Baseline (before any change)

| Check | Command | Result |
|---|---|---|
| Python unit tests | `.venv\Scripts\python.exe -m pytest tests -q` | 147 passed (15 s) |
| Firmware host tests | TinyCC build of `firmware/tests/test_app.c` + `src/app.c` | 26 checks, 0 failures |
| Firmware target build | avr-gcc 15.2.0 `-mmcu=attiny1616 -Os -Wall -Wextra -Werror` | PASS; 2362 B text, 44 B rodata, 29 B bss, 4 B noinit |
| Validation register (committed) | `reports/validation-register.md` (2026-10-26) | 2 FAIL (compact routing, compact DRC); gates A/B/C PASS; D/E/F evaluation PASS, compact OPEN; G OPEN |
| One ngspice deck | `simulation/results/startup_3v7.cir` | runs in 0.8 s (ngspice-47) |

`scripts\*.ps1` could not be started with `-ExecutionPolicy Bypass` from the agent shell (blocked by the agent's
permission policy, not by the scripts); the same compiler and Python commands were run directly.

**Current functionality.** Both schematics are generated from `connectivity.yaml` with ERC 0/0 and exact netlist
parity. The evaluation board is routed with KiCad DRC 0/0/0/0 and has a power-layout review and a DRAFT PCBWay
package. The compact board is a parked routing draft (DRC 0 errors / 3 warnings / 20 unconnected). Firmware
implements the state machine in `firmware/src/app.c` with a hardware layer in `main.c`. Calculations (21 checks)
and 11 behavioural simulations pass at model level. Gate G is open: no physical evidence exists.

**Known intentional limitations (preserved).** Compact board parked (DD-27); 4.0 A setpoint above the NUBM44
typical rating, owner-accepted (DD-13); efficiency target relaxed to ≥ 94 % (DD-26); package-limited SW2/PGND/AGND
paths without HDI via-in-pad (DD-16); supplier stock and prices UNKNOWN; averaged simulation model only.

## 3. Summary register

Status values: OPEN, FIXED (implemented and tested), MITIGATED (partly addressed, residual noted), DOCUMENTED
(accepted limitation or owner decision needed), DEFERRED (needs CAD regeneration or owner approval).

| ID | Sev. | Class | Title | Status |
|---|---|---|---|---|
| AUD-FW-01 | high | Defect | Open or shorted board NTC silently disables board over-temperature protection | FIXED |
| AUD-FW-02 | medium | Defect | A fitted laser NTC that opens or shorts is silently treated as "not fitted" | FIXED |
| AUD-FW-03 | high | Defect | Watchdog cleared on every loop pass, so a stalled tick never resets the MCU | FIXED |
| AUD-FW-04 | high | Defect | 2.5 V internal reference used below its 2.9 V VDD minimum near the battery thresholds | FIXED |
| AUD-FW-05 | medium | Defect | ADC0 reference switched every tick with no settling or forced reference | FIXED |
| AUD-FW-06 | medium | Defect | Switch input not debounced (header claims it is) | FIXED |
| AUD-FW-07 | medium | Defect | Watchdog reset restarts emission automatically with no fault indication | FIXED |
| AUD-FW-08 | medium | Defect | Power-loss handler races can sleep forever with the watchdog off | FIXED |
| AUD-FW-09 | medium | Defect | Reconnection bounce after a tail-switch click can advance the mode more than once | FIXED |
| AUD-FW-10 | medium | Defect | MCU pull-ups drive TPS552882 CC/PG above VCC + 0.3 V while the converter is shut down | FIXED |
| AUD-FW-11 | low | Defect | Start voltage checked only at boot, never before emission after re-arming | FIXED |
| AUD-FW-12 | low | Defect | Boolean tick flag drops ticks on overrun and stretches fault timers silently | FIXED |
| AUD-FW-13 | low | Defect | Fault codes ≥ 10 blink without a pause and cannot be read | FIXED |
| AUD-FW-14 | low | Defect | Over-voltage event while the converter is off is not latched until the next enabled tick | FIXED |
| AUD-FW-15 | medium | Enhancement | No detection of output current while firmware holds the converter off | FIXED |
| AUD-FW-16 | medium | Defect | Fuses (BOD level, watchdog) neither defined nor verified by the build/programming flow | MITIGATED |
| AUD-FW-17 | low | Enhancement | Hardware layer has no host tests (no HAL; ISRs, init, conversions, hold-up untested) | FIXED |
| AUD-FW-18 | info | Risk | CC pin active-low polarity not stated in the TPS552882 datasheet | DOCUMENTED |
| AUD-FW-19 | high | Defect | DAC2 reference written to VREF.CTRLC: AC2 power-loss trip at about 0.57 V, not 2.6 V | FIXED |
| AUD-FW-20 | medium | Defect | DAC2 not enabled in standby: AC2 reference stops during the hold-up sleep | FIXED |
| AUD-VAL-01 | high | Defect | Calculation evidence not bound to its inputs; stale results pass | OPEN |
| AUD-VAL-02 | high | Defect | Simulation evidence not bound to its inputs or ngspice version; stale results pass | OPEN |
| AUD-VAL-03 | medium | Defect | Malformed calculation/simulation evidence crashes the validator or passes on a status string | OPEN |
| AUD-VAL-04 | medium | Defect | SIM-11 copies the Python loop analysis instead of simulating | OPEN |
| AUD-VAL-05 | high | Defect | Validator always exits 1 because of the parked compact board: no regression signal | OPEN |
| AUD-VAL-06 | medium | Defect | Gate statuses hide the evidence type (model-level, internal consistency) | OPEN |
| AUD-VAL-07 | medium | Defect | Firmware evidence uses a hard-coded file list and records no tool versions | OPEN |
| AUD-VAL-08 | low | Defect | Schematic/ERC freshness relies on file modification times | OPEN |
| AUD-VAL-09 | medium | Defect | `run_sims.py` and `power_stage.py` exit 0 when checks fail | OPEN |
| AUD-VAL-10 | medium | Enhancement | No structured channel for bench (Gate G) evidence | OPEN |
| AUD-SIM-01 | medium | Risk | Averaged model only; inner current loop and ISP/ISN loop strength are assumptions | DOCUMENTED |
| AUD-SIM-02 | low | Defect | SIM-08 has a dead placeholder and an unsourced 25 A limit | OPEN |
| AUD-SIM-03 | medium | Enhancement | No parameter/tolerance sensitivity sweep in simulation | OPEN |
| AUD-CAL-01 | low | Defect | "Inductor RMS current" check uses the average current | OPEN |
| AUD-CAL-02 | medium | Risk | Efficiency margin is thin (94.1 % estimate with evaluation copper vs ≥ 94 %) | DOCUMENTED |
| AUD-PCB-01 | medium | Risk | Evaluation-board layout items accepted with bench checks (DR1H via, ISP/ISN, C5, VCC, SW2, AGND/PGND) | DOCUMENTED |
| AUD-PCB-02 | high | Risk | Compact board: 20 unconnected items, routing-capacity limit | DOCUMENTED |
| AUD-PCB-03 | medium | Risk | Custom/assumed footprints (TPS552882 from PDF vectors; XGL5030 on the XAL5030 pattern) not independently reviewed | OPEN |
| AUD-PCB-04 | low | Risk | Q6 gate (VGSS ±6 V) sees VOUT − 6.2 V with no clamp; overstressed above ~12 V in a multiple fault | DOCUMENTED |
| AUD-PCB-05 | low | Risk | CS_OUT can exceed VMCU by up to about 0.3 V when the INA186 output saturates | DOCUMENTED |
| AUD-MFG-01 | high | Defect | Compact fabrication ZIP and Gerbers carry no "incomplete board" marker | OPEN |
| AUD-MFG-02 | medium | Defect | Export ignores DRC/ERC/parity state; no release levels; no human approval record | OPEN |
| AUD-MFG-03 | medium | Defect | Compact BOM descriptions contradict the MPN and footprint (0402/16 V X7R text on 0201/10 V X5R parts) | OPEN |
| AUD-MFG-04 | medium | Risk | Centroid rotation/side conventions verified against KiCad only, not against PCBWay | DOCUMENTED |
| AUD-SRC-01 | medium | Defect | Sourcing ratings are a hand table with no consistency or derating check; CSV freshness unchecked | OPEN |
| AUD-SRC-02 | low | Enhancement | Stock/price snapshot carries no age flag | OPEN |
| AUD-SRC-03 | medium | Risk | Capacitor DC-bias retention (50–55 %) is an assumption | DOCUMENTED |
| AUD-DOC-01 | medium | Defect | AGENTS.md toolchain paths corrupted by control characters | OPEN |
| AUD-DOC-02 | low | Defect | Firmware README/app.h out of date (debounce, check count) | FIXED |
| AUD-DOC-03 | low | Defect | Requirement statuses overstate firmware thermal/UVLO verification | OPEN |
| AUD-CI-01 | medium | Enhancement | No continuous integration; portable and Windows/KiCad tests not separated | OPEN |
| AUD-PROC-01 | low | Defect | Firmware compile flags duplicated in `build.ps1` and `validate.py` | OPEN |

## 4. Findings in detail

Each block gives: files/functions; existing → expected behaviour; evidence/reproduction; root cause; correction;
side effects; dependencies; tests; status; validation outcome.

### Firmware

#### AUD-FW-01 Open or shorted board NTC disables board over-temperature protection (high, defect)
- **Files:** `firmware/src/main.c` `ntc_c10()`; `firmware/src/app.c` `app_tick()`.
- **Existing:** `ntc_c10()` returns `APP_T_NONE` for raw ≥ 1015 (open: R14 pulls NTC_BRD to NTC_PWR) or raw ≤ 8
  (short to GND). `app_tick()` skips the board limit when the value is `APP_T_NONE`. A missing, cracked or shorted
  RT1 therefore removes board thermal protection (REQ-SAFE-08) without any indication.
- **Expected:** RT1 is a fitted, mandatory sensor. An invalid reading must fail safe: latched sensor fault, no
  emission.
- **Evidence:** code path above; connectivity R14 (NTC_PWR→NTC_BRD) and RT1 (NTC_BRD→GND). Reproduce on the host
  with `t_board_c10 = APP_T_NONE` during emission: the state stays `ST_EMIT`.
- **Root cause:** one sentinel value meant both "optional sensor absent" and "sensor broken".
- **Correction:** classify each reading as valid/open/short in a pure conversion module; latch
  `FAULT_SENSOR_BOARD` after a short confirmation time (so one ADC glitch cannot trip it).
- **Side effects:** a board with a damaged RT1 no longer emits (intended).
- **Tests:** open, short, ADC rail values, boundary, glitch shorter than the confirmation time, latch persistence.
- **Status:** FIXED (DD-28). `conv_ntc()` classifies open/short; `app.c` latches FAULT_SENSOR_BOARD after 50 ms. **Validation:** `test_app.c` open, short, 49 ms glitch, boundary 85.0/85.1 °C; `test_fw.c` raw 0 and 1023 through the HAL; mutant killed.

#### AUD-FW-02 Fitted laser NTC that fails is treated as not fitted (medium, defect)
- **Files:** same as FW-01.
- **Existing:** the optional external NTC (TP10) reads open when absent. An open wire or a short during operation
  also returns `APP_T_NONE`, so a laser-module sensor that detaches mid-session silently stops protecting the
  diode (60 °C limit).
- **Expected:** absent at power-up = optional and ignored (documented); valid at power-up = mandatory for that
  session; a short is never "absent".
- **Correction:** latch presence at boot; afterwards an open or short latches `FAULT_SENSOR_LASER`. A short at
  boot is a fault.
- **Tests:** absent at boot, present then open, present then short, short at boot.
- **Status:** FIXED (DD-28). Presence latched at the end of the 20 ms boot window; `APP_LASER_NTC_REQUIRED` build option. **Validation:** `test_app.c` absent, fitted-then-open, short at boot, valid hot reading; required-variant suite; mutant killed.

#### AUD-FW-03 Watchdog cleared on every loop pass (high, defect)
- **Files:** `firmware/src/main.c` `main()`.
- **Existing:** `wdr` runs at the top of the busy loop whether or not a tick was processed. If the TCB0 interrupt
  stops (mis-configuration, a disabled interrupt, a corrupted flag), the loop keeps clearing the watchdog while
  `LASER_EN_N` holds its last value with no monitoring.
- **Expected:** the watchdog is only cleared after a complete supervision cycle (sample → state machine → output).
- **Correction:** clear the watchdog only after `app_tick()` has run and the output was written.
- **Tests:** host harness: with ticks stopped, no watchdog clear occurs.
- **Status:** FIXED. `fw_poll()` clears the watchdog only after sampling, the state machine and the output write. **Validation:** `test_fw.c` (1000 polls without ticks: no clear); mutant killed.

#### AUD-FW-04 2.5 V reference used outside its supply range (high, defect)
- **Files:** `firmware/src/main.c` `analog_init()`, `adc_read()`, `to_mv()`.
- **Existing:** ADC0 (VBAT, CS current), ADC1 (VOUT), DAC0 (AC0 over-voltage reference) and DAC2 (AC2 power-loss
  reference) all use the internal 2.5 V reference. ATtiny1616 Table 37-22 specifies INT25V for VDD 2.9–5.5 V.
  VMCU = VBAT − D2 (RB521S30) drop, about 0.2–0.35 V at MCU currents, so VMCU is at or below 2.9 V at the 3.2 V
  start threshold and below it at the 3.1 V warning and 2.9 V cut-off. The thresholds that matter most are
  measured with a reference outside its specification; the error direction is UNKNOWN.
- **Expected:** every reference used at the battery thresholds is inside its specified supply range.
- **Correction (firmware only; thresholds unchanged):** measure VBAT and CS ratiometrically against VDD and
  calibrate VDD with the 1.1 V reference (INT11V: 1.8–5.5 V, ±2 % at 0–105 °C); use the 1.5 V reference (INT15V:
  1.9–5.5 V) for ADC1, DAC0 and DAC2 with recomputed DAC codes for the same 5.625 V and 2.6 V trip points.
- **Side effects:** one extra conversion per tick; DAC codes change (160 for AC0, 222 for AC2).
- **Dependencies:** bench confirmation of the VBAT reading against a DMM (new T1.11).
- **Tests:** conversion arithmetic at VDD 2.5–4.0 V, saturation, zero/invalid reference readings.
- **Status:** FIXED (DD-28). ADC0 on VDD with INT11V calibration; ADC1/DAC0/DAC2 on INT15V; DAC codes 160/222. **Validation:** `test_conv.c` VBAT within 12 mV for VDD 2.25–4.05 V, 2.9 V readable at VDD 2.6 V; `test_hal.c` reference registers. Bench: T1.11.

#### AUD-FW-05 ADC0 reference switching without settling (medium, defect)
- **Files:** `firmware/src/main.c` `adc_read()`.
- **Existing:** each tick ends with two VDD-referenced NTC conversions and begins with an internally referenced
  VBAT conversion; `ADC0.CTRLD.INITDLY` is 0 and the reference is not forced on. The datasheet notes up to 60 µs
  VREF start-up (§29.3.1) and INITDLY exists for exactly this case (§30.5.4).
- **Correction:** force the ADC0 reference on (`VREF.CTRLB`), set `INITDLY`, and discard the first conversion
  after any reference change.
- **Status:** FIXED by removing the switching: ADC0 never changes reference; 1.1 V forced on (`VREF.CTRLB`), INITDLY 64 clocks, first reference conversion discarded. **Validation:** `test_hal.c` checks every ADC0 conversion runs on VDD.

#### AUD-FW-06 Switch input not debounced (medium, defect)
- **Files:** `firmware/src/main.c` (raw `PORTA.IN` read), `firmware/src/app.c`, `app.h` (`switch_pressed` comment
  says "debounced").
- **Existing:** every bounce edge is a press; a bouncing contact can change the mode two or more times, and a
  switch held at power-up counts as a press.
- **Correction:** debounce in the application layer (20 ms stable level), accept a press only after a debounced
  release, ignore a switch held at power-up, and require 250 ms between accepted presses.
- **Tests:** bounce bursts, rapid presses, held at boot, stuck closed.
- **Status:** FIXED. **Validation:** `test_app.c` noisy press = one change, sub-debounce contact ignored, lockout, held at boot, stuck closed; mutant killed.

#### AUD-FW-07 Watchdog reset re-arms emission without a fault (medium, defect)
- **Files:** `firmware/src/main.c` `main()` reset-flag handling.
- **Existing:** `RSTCTRL.RSTFR` is read only to recognise the hold-up software reset; a watchdog reset boots like a
  power-up and, with the interlock closed, emits again after 2 s.
- **Expected (Class 4, manual reset):** an unexpected reset latches a visible fault until power is removed.
- **Correction:** latch `FAULT_INTERNAL` on WDRF (and on a software reset without the hold-up marker).
- **Status:** FIXED. `fw_init()` latches FAULT_INTERNAL on WDRF and on a software reset without a valid hold-up record (with check byte). **Validation:** `test_fw.c`; mutant killed.

#### AUD-FW-08 Power-loss handler races (medium, defect)
- **Files:** `firmware/src/main.c` `handle_power_loss()`.
- **Existing:** (a) `power_lost` is cleared after AC2 is switched to rising-edge mode, so a return edge in that
  window is lost; (b) the flag test and `sleep_cpu()` are not atomic; (c) if the supply has already returned (a
  short sag rather than a removal), no rising edge comes. With the watchdog disabled, the MCU then sleeps until the
  battery is removed long enough for a brown-out. The laser stays off (safe) but the device is locked up.
- **Correction:** clear the flag first, check `AC2.STATUS.STATE` after reconfiguration, use the
  `cli`/`sei`+`sleep` idiom, and debounce the return (FW-09).
- **Status:** FIXED. `hal_holdup_sleep()` uses cli → state check → sei+sleep; the hold-up loop polls `AC2.STATUS.STATE`; a 1 s guard watchdog covers polling with the supply present. **Validation:** `test_hal.c` (no sleep when present, interrupts enabled at sleep), `test_fw.c` (supply already back: no sleep, restart); mutant killed.

#### AUD-FW-09 Reconnection bounce advances the mode more than once (medium, defect)
- **Existing:** the first rising edge after a gap resets the MCU at once. A contact that bounces on reconnection
  produces a further short gap immediately after boot; the stored mode is already advanced, so it advances again.
- **Correction:** a pure hold-up module that requires the supply to stay present for a debounce time before the
  restart, and classifies the gap once.
- **Status:** FIXED. `holdup.c` restarts only after 20 ms of continuous supply and measures the gap from the first loss. **Validation:** `test_holdup.c` (bounce, wrap, boundaries), `test_fw.c` (bouncing return = one click, mode advanced once); mutant killed.

#### AUD-FW-10 CC/PG back-powered through MCU pull-ups (medium, defect)
- **Files:** `firmware/src/main.c` `gpio_init()`.
- **Existing:** PB0 (PG) and PB1 (CC) have the internal pull-ups to VMCU permanently enabled. SLVSFC5 §6.1 limits
  CC and PG to VCC + 0.3 V; in shutdown (EN < 0.4 V, §7.3.6) all functions, including the VCC regulator, are
  off. PG is never read.
- **Correction:** PG: pull-up off, digital input disabled. CC: pull-up and input enabled only while the converter
  is enabled, and evaluated only after a short arming delay.
- **Status:** FIXED. **Validation:** `test_hal.c` (no pull-up after init, on only while enabled, off after over-voltage), `test_app.c` (pull-up from the second enabled tick, CC read from the third); mutant killed. TPS552882 VCC start-up time is an assumption (≤ 1 ms).

#### AUD-FW-11 Start voltage not re-checked before emission (low, defect)
- **Existing:** the 3.2 V resting check runs once in `ST_BOOT`; an interlock wait or a re-arm can last
  indefinitely before emission.
- **Correction:** require the resting voltage at the end of every arming period (converter off) before entering
  `ST_EMIT`.
- **Status:** FIXED. **Validation:** `test_app.c` (30 s interlock wait then 3.15 V: fault with detail ARMING_RECHECK; dip during arming that recovers: emits); mutant killed.

#### AUD-FW-12 Ticks lost on overrun (low, defect)
- **Existing:** `tick_flag` is a boolean; if one pass takes over 1 ms, ticks are lost and the 200 ms low-battery or
  50 ms regulation timers stretch. Measured work per tick is well under 1 ms today (five conversions of about 48 µs
  at 312.5 kHz ADC clock), so this is latent.
- **Correction:** count pending ticks, run the state machine once per tick, and latch `FAULT_INTERNAL` if the
  backlog exceeds a bound.
- **Status:** FIXED. Pending-tick counter (saturating), state machine run once per tick, backlog > 4 latches FAULT_INTERNAL. **Validation:** `test_fw.c`, `test_hal.c` (saturation); mutant killed.

#### AUD-FW-13 Fault codes ≥ 10 unreadable (low, defect)
- **Existing:** `n` blinks of 300 ms inside a fixed 3000 ms period: code 10 (`FAULT_OVERVOLTAGE`) leaves no pause.
- **Correction:** period = n × 300 ms + 1500 ms pause.
- **Status:** FIXED. **Validation:** `test_app.c` counts n blinks and a ≥ 1.5 s pause for every code 1–15; mutant killed.

#### AUD-FW-14 Over-voltage event while off is not latched (low, defect)
- **Existing:** `ov_trip` is evaluated only inside `check_running()` (converter enabled). An AC0 event during a
  flash off-phase leaves the state `ST_EMIT` with the indicator on until the next on-phase.
- **Correction:** evaluate the latched comparator event in every non-fault state.
- **Status:** FIXED. **Validation:** `test_app.c` over-voltage while emitting, arming and in a flash off phase; mutant killed.

#### AUD-FW-15 No check that the output is really off (medium, enhancement)
- **Existing:** nothing detects laser current while firmware holds LASER_EN_N high (failed Q4 open, a broken PA1
  trace). Firmware cannot stop the converter in that case, but it can refuse to indicate "ready" and latch a
  fault code so the user knows.
- **Correction:** `FAULT_OUTPUT_WHILE_OFF` when the current exceeds 200 mA for 20 ms while disabled, outside a
  10 ms turn-off blanking window (SIM-06 shows < 50 mA within 0.5 ms of disable).
- **Status:** FIXED (FAULT_OUTPUT_WHILE_OFF, 10 ms blanking, 200 mA, 20 ms). **Validation:** `test_app.c` (150 mA tolerated, 800 mA latches, flash turn-off decay not a fault); mutant killed.

#### AUD-FW-16 Fuses undefined (medium, defect)
- **Existing:** README says "set the BOD level to 1.8 V"; `build.ps1 -Flash` writes flash only. ATtiny1616 BODCFG
  resets to 0x00 (BOD disabled). Without BOD, RAM retention during hold-up (the mode memory) is unprotected.
- **Correction:** record the required fuse values in the firmware (single source), print them in the build, and
  add a fuse-verification step to the bench plan. Programming fuses stays a manual bench action.
- **Status:** MITIGATED. Required values in `firmware/src/fuses.h`, start-up check latches FAULT_CONFIG, programming/readback commands in the firmware README, bench step T0.4. Programming remains a manual bench action. **Validation:** `test_hal.c` (BOD disabled and 16 MHz rejected), `test_fw.c`.

#### AUD-FW-17 Hardware layer untested (low, enhancement)
- **Existing:** `main.c` mixes register access with logic (tick handling, conversions, hold-up), none of which
  is compiled on the host.
- **Correction:** split into `hal.h` + `hal_avr.c` (registers, ISRs), `fw.c` (scheduler, sampling, outputs,
  hold-up), `conv.c` (pure conversions), `holdup.c` (pure gap logic); add a recording mock HAL and host tests.
- **Status:** FIXED. Layers `hal_avr.c` / `fw.c` / `app.c` / `conv.c` / `holdup.c`; six host suites (531 checks) in `firmware/build.py`, mock constants checked against avr-libc by `tests/test_firmware_build.py`; 15/15 mutants killed.

#### AUD-FW-18 CC pin polarity (info, risk)
- SLVSFC5 Table 5-1 says only "Constant current output indication"; the electrical table gives open-drain
  characteristics (I_CC_H leakage, V_CC_L at 4 mA). The sibling TPS552892 (SLVSH28A, pin 4) states "open drain
  output … outputs low level" when the current limit triggers. The firmware's active-low assumption is plausible
  and stays a bench item (T1.10). **Status:** DOCUMENTED.

#### AUD-FW-19 DAC2 reference in the wrong register (high, defect)
- **Files:** `firmware/src/main.c` `analog_init()` (before DD-28).
- **Existing:** `VREF.CTRLC = VREF_ADC1REFSEL_2V5_gc | VREF_DAC2REFSEL_2V5_gc;`. DS40001997C §18.5.3/18.5.4 and the
  avr-libc header put ADC1REFSEL and DAC1REFSEL in CTRLC and DAC2REFSEL in CTRLD (reset 0x00 = 0.55 V). The write set
  DAC1's reference (unused) and left DAC2 at 0.55 V, so AC2 compared VBAT/2 with 133/256 × 0.55 V = 0.29 V: the
  "battery removed" event fired near VBAT 0.57 V instead of 2.6 V.
- **Consequence:** after a click, VBAT decays slowly through the dividers (tens of kΩ against 66 µF, about a second
  to 0.57 V) while the MCU drains C16 in milliseconds, so the MCU browns out before AC2 fires: the short-click mode
  change cannot work and the AC2 "laser off" path never acts. The hardware UVLO (2.83 V) still stops the converter,
  so there is no emission hazard.
- **Root cause:** register field mapping not verified; no host test of the register configuration.
- **Correction:** write `VREF.CTRLD`; the register-model test (`firmware/tests/test_hal.c`) asserts every reference
  register; the mutation check re-injects this defect.
- **Status:** FIXED. **Validation:** `test_hal.c` asserts `VREF.CTRLD`; mutant (write to CTRLC) killed. Bench: T1.9.

#### AUD-FW-20 DAC2 stops in standby (medium, defect)
- **Existing:** `DAC2.CTRLA = DAC_ENABLE_bm` without RUNSTDBY. DS40001997C §31.3.3: with RUNSTDBY = 0 the DAC stops
  in standby, which is the sleep mode used during the hold-up, so AC2's negative input is undefined exactly when it
  must detect the battery's return.
- **Correction:** `DAC_RUNSTDBY_bm`; asserted by the register-model test. Hold-up current impact UNKNOWN until T1.9.
- **Status:** FIXED. **Validation:** `test_hal.c`; mutant killed. Bench: T1.9 (hold-up current).

### Validation and evidence

#### AUD-VAL-01 Calculation evidence not bound to inputs (high, defect)
- **Files:** `automation/validation/validate.py` `calculations()`; `engineering/calculations/power_stage.py`.
- **Existing:** the validator reads `power-stage-results.json` and copies each saved status. Editing
  `parameters.yaml` (or `power_stage.py`, or `automation/nubm44/calc/*.py`) leaves every VAL-CALC entry PASS.
- **Reproduction:** change `current.i_set_a` and run `validate.py` without rerunning the calculation: all
  VAL-CALC entries stay PASS.
- **Correction:** the calculation writes an evidence manifest (input hashes, Python and package versions); the
  validator recomputes hashes and fails stale or missing manifests.
- **Status:** OPEN. **Validation:** —

#### AUD-VAL-02 Simulation evidence not bound to inputs (high, defect)
- As VAL-01 for `simulation/results/results.json` (inputs: `parameters.yaml`, `run_sims.py`, the calculation
  results SIM-11 reads, the ngspice version). **Status:** OPEN.

#### AUD-VAL-03 Malformed evidence handling (medium, defect)
- `calculations()` indexes `d["checks"]` and `c["status"]` directly: a malformed file raises `KeyError` (the
  validator crashes instead of recording FAIL). Saved status strings are trusted without re-checking value
  against limit, and the number of expected checks/simulations is not enforced. **Status:** OPEN.

#### AUD-VAL-04 SIM-11 is not a simulation (medium, defect)
- `run_sims.py` `loop_ac()` re-reads `power-stage-results.json`. Gate C counts it as simulation evidence, so the
  loop is "verified" twice by one model. **Correction:** a frequency-response analysis (sinusoidal injection in the
  transient behavioural deck, Middlebrook voltage injection at the CSA output) compared with the Python model.
  **Status:** OPEN.

#### AUD-VAL-05 No regression signal (high, defect)
- `validate.py` exits 1 whenever any entry fails. The parked compact board always fails `VAL-ROUTE`/`VAL-DRC`, so
  every run fails and a new regression is indistinguishable. **Correction:** an explicit, documented
  known-limitations file (`engineering/known-limitations.yaml`) with the exact accepted detail; the register keeps
  the FAIL, but the exit code separates "known, unchanged" from "new or changed"; per-board readiness levels.
  **Status:** OPEN.

#### AUD-VAL-06 Evidence type hidden in gate statuses (medium, defect)
- Gate C reads "PASS" (model-level only); Gate F "PASS" means internal export consistency. **Correction:** gate
  details state the evidence class; per-board readiness table. **Status:** OPEN.

#### AUD-VAL-07 Firmware evidence (medium, defect)
- `validate.py` `firmware()` compiles `main.c` + `app.c` only (a new source file would break or be silently
  omitted), without warnings for the host build, and records no tool versions. **Status:** OPEN.

#### AUD-VAL-08 Modification-time freshness (low, defect)
- `freshness_problems()` compares mtimes; a checkout or copy changes mtimes, which can make fresh evidence look
  stale or stale evidence look fresh. The schematic summary has no hashes. **Status:** OPEN (low priority; DRC
  and export evidence already use hashes).

#### AUD-VAL-09 Generators exit 0 on failure (medium, defect)
- `run_sims.py` `main()` always returns 0; `power_stage.py` exits 0 with failing checks. **Status:** OPEN.

#### AUD-VAL-10 No bench-evidence channel (medium, enhancement)
- Gate G is a fixed string. The test plan asks for results in `documentation/testing/results/<serial>/` but there
  is no schema, importer, comparison with predictions or report. **Status:** OPEN.

### Simulation and calculation

#### AUD-SIM-01 Model limits (medium, risk)
- The ngspice model is cycle-averaged (no ripple, no saturation, no dead time). The inner current loop (about
  60 kHz crossover) and the ISP/ISN loop strength are assumptions; no vendor model exists. Claims are limited to
  "model-level". **Status:** DOCUMENTED (kept visible in the register and dashboard).

#### AUD-SIM-02 SIM-08 placeholder (low, defect)
- `short_circuit()` computes an unused `ish = … * 0` and uses a 25 A inductor limit with no source.
  **Status:** OPEN.

#### AUD-SIM-03 No sensitivity sweep (medium, enhancement)
- Loop robustness against output-capacitance DC bias, inductance tolerance, error-amplifier gm and CSA bandwidth is
  not swept. **Status:** OPEN.

#### AUD-CAL-01 RMS check uses average (low, defect)
- `power_stage.py`: "Inductor RMS current vs Irms" passes `max(i_l_avg)`. With ripple, RMS = √(avg² + ripple²/12)
  (7.42 A vs 7.39 A at the worst point). **Status:** OPEN.

#### AUD-CAL-02 Thin efficiency margin (medium, risk)
- 94.59 % model, about 94.1 % with evaluation copper, against ≥ 94 %. Bench T1.7 decides. **Status:** DOCUMENTED.

### PCB and electrical

#### AUD-PCB-01 Evaluation layout items (medium, risk)
- Independently re-read from `reports/layout-review-evaluation-board.md`: NECK-SW2 0.75 mm (package-limited),
  SW1 crowding at the DR1H via, ISP/ISN of U1 on two layers, VCC through In2 (7.8 mm), C5/BOOT1 loop, AGND/PGND
  offset +0.28 %. The dispositions in `engineering/layout-review.md` are consistent with the copper data. Options
  and trade-offs are in `engineering/pcb-review-2026-10-26.md`. **Status:** DOCUMENTED (no CAD change without a
  new router session and owner agreement).

#### AUD-PCB-02 Compact board incomplete (high, risk)
- 20 unconnected items (DRC evidence of 2026-10-25). Strategy comparison in
  `engineering/pcb-review-2026-10-26.md`. **Status:** DOCUMENTED (DD-27).

#### AUD-PCB-03 Footprints needing independent review (medium, risk)
- U1 land pattern extracted from PDF vectors (LEAD-01); L1 "XGL5030 uses the XAL5030 land pattern (verify)" in
  `connectivity.yaml`; DD-20 already states independent footprint review is required before release.
  **Status:** OPEN (release blocker recorded in the manufacturing gate).

#### AUD-PCB-04 Q6 gate overstress in a multiple fault (low, risk)
- DMG1012T VGSS ±6 V (DS31783 p.2). Q6 gate = VOUT − V_Z(D3) across R20; above about 12 V of VOUT the gate is
  overstressed. Normal operation and SIM-09 stay below 7 V; only a second failure (converter running against an
  ineffective EN pull-down up to the 23.5 V OVP) reaches it. A gate clamp would be a hardware change needing owner
  approval. **Status:** DOCUMENTED.

#### AUD-PCB-05 CS_OUT above VMCU (low, risk)
- INA186 is supplied from VBAT, the MCU from VBAT − D2. Only a saturated INA output (fault) can exceed VMCU, by at
  most the D2 drop; the INA output current is limited. **Status:** DOCUMENTED.

### Manufacturing

#### AUD-MFG-01 Incomplete board exported without a marker (high, defect)
- `export_pcbway.py` writes `compact-22mm-gerbers.zip` and `export-check.json` status PASS for a board with 20
  unconnected items. The ZIP (what a user uploads) contains only Gerbers and drills; `REVIEW_ONLY.md` is generic.
- **Correction:** read the DRC evidence at export time; mark the package and the ZIP (`DO_NOT_FABRICATE.txt`
  inside, release level in `export-check.json` and `REVIEW_ONLY.md`).
- **Status:** OPEN.

#### AUD-MFG-02 No release levels (medium, defect)
- **Correction:** `automation/export/release_check.py` computes DRAFT_REVIEW → PROTOTYPE_CANDIDATE →
  MANUFACTURING_RELEASE from hashed evidence (ERC, netlist, DRC 0/0/0/0, layout review, export, BOM MPN
  completeness, open footprint reviews, Gate G evidence, signed human approval file). **Status:** OPEN.

#### AUD-MFG-03 Compact BOM description mismatch (medium, defect)
- `connectivity.yaml` has one `desc` per part, but compact parts use 0201 MPNs: the compact BOM reads e.g.
  "100 nF 16 V X7R 0402 output HF" for GRM033R61A104KE15D (0201, 10 V, X5R). **Correction:** variant-specific
  descriptions require a schematic/PCB regeneration (connectivity hash invalidates DRC evidence) and are deferred
  to the next CAD regeneration; an automated check reports the mismatch until then. **Status:** OPEN.

#### AUD-MFG-04 PCBWay centroid convention (medium, risk)
- The exporter checks CPL against KiCad's own position file, not against PCBWay's rotation convention. PCBWay DFM
  review must confirm. **Status:** DOCUMENTED.

### Sourcing

#### AUD-SRC-01 Ratings table unchecked (medium, defect)
- `sourcing/build_sourcing.py` hard-codes ratings; nothing checks that `components.csv` matches the current
  `connectivity.yaml`, that capacitor voltage ratings exceed the net's worst voltage, or that resistor power
  ratings cover dissipation. **Status:** OPEN.

#### AUD-SRC-02 No data age flag (low, enhancement)
- All supplier data is from 2026-10-24 with no expiry. **Status:** OPEN.

#### AUD-SRC-03 DC-bias retention assumed (medium, risk)
- 50–55 % retention for 22 µF 0805 X5R at 4–7 V is UNKNOWN from vendors (DD-10). **Status:** DOCUMENTED.

### Documentation, CI, process

#### AUD-DOC-01 AGENTS.md control characters (medium, defect)
- The avr-gcc and TinyCC rows contain BEL/BS/TAB bytes where `\a`, `\b`, `\t` were meant as path separators
  (`cat -A` shows `tools^Gvr-gcc…`). **Status:** OPEN.

#### AUD-DOC-02 Firmware docs out of date (low, defect) — **Status:** FIXED: firmware README rewritten (behaviour, fault codes, measurement chain, fuses, files, build).

#### AUD-DOC-03 Requirement statuses (low, defect)
- REQ-SAFE-06 is VERIFIED-CALC although its method is TEST only; REQ-SAFE-08 says the thermal latch is
  "unit-tested" while FW-01 shows a sensor failure bypasses it. **Status:** OPEN.

#### AUD-CI-01 No CI (medium, enhancement) — **Status:** OPEN.

#### AUD-PROC-01 Duplicated compile flags (low, defect)
- `firmware/build.ps1` and `validate.py` each spell the compiler command; they already differ (`-ffunction-sections`
  and `--gc-sections` only in `build.ps1`). **Status:** OPEN.

## 5. Opportunities to simplify

- One firmware build driver in Python (`firmware/build.py`) used by `build.ps1`, the validator and CI.
- One evidence-manifest helper (`automation/nubm44/evidence.py`) for calculations, simulations, firmware and bench
  data instead of per-tool ad-hoc hash code.
- Per-board readiness computed once and consumed by the register, the export, the dashboard and CI.
