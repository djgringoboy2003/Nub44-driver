# NUBM44 driver firmware (ATtiny1616)

The MCU decides **when** emission is allowed. It never sets **how much** current flows:

- **Current setpoint:** set in hardware by the FB divider (R8/R9).
- **Hardware current ceiling:** the TPS552882 ISP/ISN loop (4.8–5.2 A).
- **Hardware disables:** an open interlock or the over-voltage Zener pulls EN/UVLO low regardless of firmware.
- **Default off:** the reset state of PA1 plus pull-up R17 keeps the converter off until firmware drives PA1 low.

## Behaviour

| Situation | Response |
|---|---|
| Power-up | Indicator on for a 2 s emission delay; no emission. Refuses to start below 3.2 V resting (latched fault). |
| Interlock open at power-up | Waits, never emits. Closing it starts a new full 2 s delay. |
| Interlock opens during emission | Hardware disables at once. Firmware latches FAULT_INTERLOCK; a power cycle is required (manual reset). |
| Continuous mode | Converter enabled. |
| Flash mode | 2 Hz, 50 % (each flash goes through the 4 ms hardware soft start). |
| Mode change | A short power interruption (< 0.5 s, timed by the RTC while C16 holds the MCU up) advances the mode. A long one returns to continuous. The optional switch pad also advances the mode. |
| Battery < 3.1 V loaded | Indicator blinks 4 Hz during emission. (The current cannot be reduced in firmware: it is set in hardware.) |
| Battery < 2.9 V loaded for 200 ms | Latched off (FAULT_LOW_BATTERY). Hardware UVLO stops the converter at 2.83 V anyway. |
| VOUT > 5.6 V (AC0 comparator, interrupt) | Disabled within microseconds, latched (FAULT_OVERVOLTAGE). Zener backstop near 6.5 V acts without firmware. |
| Open load / short / regulation error / backup-limit flag | Latched fault after 2 / 5 / 50 / 1 ms (checked only after the 20 ms soft-start window). |
| Board > 85 °C or laser NTC > 60 °C | Latched fault. |

Faults are shown as N short blinks every 3 s; N is the `app_fault_t` number in `src/app.h`.

## Files

- `src/app.h`, `src/app.c`: hardware-independent state machine (all safety logic).
- `src/main.c`: ATtiny1616 drivers (clock, GPIO, ADC0/ADC1, AC0/AC2 with internal DACs, TCB0 tick, RTC, watchdog, hold-up sleep).
- `tests/test_app.c`: host unit tests (26 checks).
- `build.ps1`: runs the tests, builds `build/nubm44_fw.hex`, and optionally programs the part.

## Build

```powershell
.\firmware\build.ps1            # tests + build (tools from scripts\setup.ps1)
```

Last build: avr-gcc 15.2.0, 2.4 kB flash of 16 kB, 33 B RAM, no warnings with `-Wall -Wextra -Werror`.

## Programming

- **Interface:** UPDI on pad TP6 (PA0), with TP7 (VMCU) and TP8 (GND).
- **Programmer:** use a SerialUPDI adapter (a USB-UART with a 4.7 kΩ series resistor or a Schottky diode on TX)
  and `pymcuprog` (`pip install pymcuprog` in `.venv`), or any UPDI programmer:

```powershell
.\firmware\build.ps1 -Flash COM5
```

**Disconnect the laser diode before programming or bench work.** Use a dummy load (power resistor or diode
string, see `documentation/testing/`). Supply the board from a current-limited bench supply at 3.7–4.2 V on the
battery contacts, not from the programmer.

## Not yet verified (Gate G)

- **Fuses:** OSC20M is assumed; the default fuse already selects 20 MHz. Set the BOD level to 1.8 V so short
  power gaps do not reset RAM. These settings must be checked on hardware.
- **CC pin polarity:** the TPS552882 CC pin is assumed active-low. Verify it on the bench.
- **Mode switching:** the hold-up time with the real C16, and the AC2 power-loss detection, need measuring
  with the actual tail switch.
