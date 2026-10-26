# NUBM44 driver firmware (ATtiny1616)

The MCU decides **when** emission is allowed. It never sets **how much** current flows:

- **Current setpoint:** set in hardware by the FB divider (R8/R9).
- **Hardware current ceiling:** the TPS552882 ISP/ISN loop (4.8–5.2 A).
- **Hardware disables:** an open interlock or the over-voltage Zener pulls EN/UVLO low regardless of firmware.
- **Default off:** the reset state of PA1 plus pull-up R17 keeps the converter off until firmware drives PA1 low.

## Behaviour

| Situation | Response |
|---|---|
| Power-up | 20 ms input settling (no indication), then the indicator is on for a 2 s emission delay; no emission. Refuses to start below 3.2 V resting (latched fault). |
| Interlock open at power-up | Waits, never emits. Closing it starts a new full 2 s delay. |
| End of every emission delay | The resting battery voltage is checked again; below 3.2 V latches FAULT_LOW_BATTERY_START. |
| Interlock opens during emission | Hardware disables at once. Firmware latches FAULT_INTERLOCK; a power cycle is required (manual reset). |
| Continuous mode | Converter enabled. |
| Flash mode | 2 Hz, 50 % (each flash goes through the 4 ms hardware soft start). |
| Mode change by power gap | The battery-loss comparator (AC2, 2.6 V) stops emission and the MCU sleeps on C16, timing the gap. After the supply has been back for 20 ms: gap < 30 ms = glitch (same mode, a latched fault is kept); 30 ms–0.5 s = click (next mode, faults cleared); ≥ 0.5 s = continuous. Every restart re-arms with the 2 s delay. |
| Mode change by switch | Optional switch pad: a press counts after 20 ms of stable contact and only after a release; presses closer than 250 ms are ignored; a switch held at power-up or stuck closed never changes the mode. |
| Battery < 3.1 V loaded | Indicator blinks 4 Hz during emission. (The current cannot be reduced in firmware: it is set in hardware.) |
| Battery < 2.9 V loaded for 200 ms | Latched off (FAULT_LOW_BATTERY). Hardware UVLO stops the converter at 2.83 V anyway. |
| VOUT > 5.6 V (AC0 comparator, interrupt) | Disabled within microseconds and latched (FAULT_OVERVOLTAGE) in every state. The Zener backstop (about 6.4–7.3 V, DD-05) acts without firmware. |
| Open load / short / regulation error | Latched fault after 2 / 5 / 50 ms (checked only after the 20 ms soft-start window). |
| Backup-limit flag (CC) | Latched FAULT_OVERCURRENT 1 ms after it asserts, read from 3 ms after each enable (the CC pull-up is only on while the converter runs). |
| Board > 85 °C or laser NTC > 60 °C | Latched fault. |
| Board NTC open or shorted for 50 ms | Latched FAULT_SENSOR_BOARD (the board sensor is mandatory). |
| Laser NTC | Open at power-up = not fitted, ignored for that session. Shorted at any time, or open after being present at power-up, latches FAULT_SENSOR_LASER. Build with `-DAPP_LASER_NTC_REQUIRED=1` to make it mandatory. |
| Laser current > 200 mA for 20 ms while firmware holds the converter off (after 10 ms blanking) | Latched FAULT_OUTPUT_WHILE_OFF: the enable path (Q4/PA1) has failed. Firmware cannot stop the converter in that case; the interlock still can. |
| Watchdog reset, unexpected software reset, tick overrun, invalid reference reading | Latched FAULT_INTERNAL; a watchdog reset never re-arms emission by itself. |
| Fuses differ from `src/fuses.h` | Latched FAULT_CONFIG. |

The thresholds above are unchanged from DD-06/DD-08. The supervision timings added on 2026-10-26 (DD-28) only
add checks.

## Fault codes

The indicator blinks the code N (150 ms on in 300 ms slots), then pauses 1.5 s, and repeats.

| N | Fault | N | Fault |
|---|---|---|---|
| 1 | Low battery at start (or at the end of arming) | 9 | Laser over-temperature |
| 2 | Low battery while emitting | 10 | Over-voltage |
| 3 | Interlock opened | 11 | Board NTC open or shorted |
| 4 | Open load | 12 | Laser NTC shorted or lost |
| 5 | Short circuit | 13 | Current while the converter should be off |
| 6 | Backup current limit (CC) | 14 | Internal (watchdog, reset, timing, reference) |
| 7 | Regulation error | 15 | Fuses not as required |
| 8 | Board over-temperature | | |

`app_t.fault_detail` (debugger) gives the cause of 11, 12 and 14.

## Measurement chain

The 2.5 V internal reference needs VDD ≥ 2.9 V (DS40001997C Table 37-22), but VMCU is one Schottky drop below
VBAT, so it is at or below that limit near the battery thresholds (audit AUD-FW-04). The firmware therefore:

- references ADC0 to VDD for every channel and measures the 1.1 V reference (specified from VDD 1.8 V) each tick;
  VBAT and the laser current are computed ratiometrically (`conv.c`);
- uses the 1.5 V reference (specified from VDD 1.9 V) for ADC1 (VOUT), DAC0 (AC0, 5.625 V trip) and DAC2 (AC2,
  2.60 V power-loss trip). DAC2's reference lives in `VREF.CTRLD`; the earlier firmware wrote it to `CTRLC`, which
  left AC2 on the 0.55 V reset reference (trip at about 0.57 V, audit AUD-FW-19).

Bench check T1.11 compares the firmware's VBAT reading with a DMM.

## Files

- `src/app.h`, `src/app.c`: hardware-independent state machine (all safety decisions).
- `src/conv.h`, `src/conv.c`: measurement conversions and NTC classification.
- `src/holdup.h`, `src/holdup.c`: power-gap timing and classification.
- `src/fw.h`, `src/fw.c`: start-up, reset causes, the supervision cycle and the hold-up sequence (uses only `hal.h`).
- `src/hal.h`, `src/hal_avr.c`: ATtiny1616 registers and interrupt handlers.
- `src/fuses.h`: required fuse values. `src/main.c`: entry point.
- `tests/`: host tests: `test_app.c` (state machine), `test_conv.c`, `test_holdup.c`, `test_fw.c` (runtime against the
  scripted HAL in `hal_mock.c`) and `test_hal.c` (`hal_avr.c` compiled against the register model in `tests/mock/`,
  whose constants `tests/test_firmware_build.py` checks against the real avr-libc header).
- `build.py`: the build driver used by `build.ps1`, the validator and CI; `--mutation` re-injects each audited defect
  and requires a test to fail.

## Build

```powershell
.venv\Scripts\python.exe firmware\build.py --mutation   # host tests, target build, mutation check
.\firmware\build.ps1                                     # the same through PowerShell (optional -Flash COM5)
```

`build.py` writes `reports/firmware-evidence.json` (source hashes, compiler versions, suite results, HEX hash and
size). Build of 2026-10-26: avr-gcc 15.2.0, 4134 B flash of 16 KB, 59 B RAM, no warnings with `-Wall -Wextra -Werror`;
six host suites with 531 checks; 15 of 15 mutants caught.

## Programming

- **Interface:** UPDI on pad TP6 (PA0), with TP7 (VMCU) and TP8 (GND).
- **Programmer:** use a SerialUPDI adapter (a USB-UART with a 4.7 kΩ series resistor or a Schottky diode on TX)
  and `pymcuprog` (`pip install pymcuprog` in `.venv`), or any UPDI programmer:

```powershell
.\firmware\build.ps1 -Flash COM5
```

- **Fuses (once per board, then verify; test plan T0.4).** The firmware refuses to run with other values (fault 15):

```powershell
.venv\Scripts\python.exe -m pymcuprog.pymcuprog write -t uart -u COM5 -d attiny1616 -m fuses -o 1 -l 0x06   # BODCFG
.venv\Scripts\python.exe -m pymcuprog.pymcuprog write -t uart -u COM5 -d attiny1616 -m fuses -o 2 -l 0x02   # OSCCFG
.venv\Scripts\python.exe -m pymcuprog.pymcuprog read  -t uart -u COM5 -d attiny1616 -m fuses -o 0 -b 9
```

  BODCFG 0x06 = brown-out detection at 1.8 V, enabled when active, sampled in sleep; OSCCFG 0x02 = 20 MHz
  oscillator. The pymcuprog options are as documented by Microchip for pymcuprog 3.x; confirm them against
  `pymcuprog --help` of the installed version before use.

**Disconnect the laser diode before programming or bench work.** Use the diode-string dummy load described in
`documentation/testing/test-plan.md` (a resistor alone does not reproduce the diode knee). Supply the board
from a current-limited bench supply at 3.7–4.2 V on the battery contacts, not from the programmer.

## Not yet verified (Gate G)

- **Fuses:** programming and readback (T0.4).
- **CC pin polarity:** the TPS552882 datasheet only names the pin "constant current output indication"; the sibling
  TPS552892 states active-low open drain. Verify on the bench (T1.10).
- **Mode switching:** hold-up time with the real C16, the AC2 trip at 2.6 V and the glitch/click boundaries with the
  actual tail switch (T1.8, T1.9).
- **Measurement chain:** VBAT and current readings against a DMM (T1.11); the TPS552882 VCC start-up time assumed
  below 1 ms for the CC pull-up timing.
- **Tick budget:** seven ADC conversions per tick are estimated at about 0.45 ms of the 1 ms tick; the firmware
  latches FAULT_INTERNAL on an overrun, but the margin is unmeasured.
