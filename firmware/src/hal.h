/*
 * Hardware abstraction for the NUBM44 driver firmware.
 *
 * hal_avr.c implements it for the ATtiny1616 (registers and interrupt handlers only, no decisions);
 * firmware/tests/hal_mock.c implements it on the host so fw.c can be tested with scripted hardware.
 * Pin map: engineering/design-decisions.md DD-07, schematic U3.
 */
#ifndef HAL_H
#define HAL_H

#include <stdbool.h>
#include <stdint.h>

/* Reset causes (RSTCTRL.RSTFR) */
#define HAL_RST_POWER_ON    0x01u
#define HAL_RST_BROWN_OUT   0x02u
#define HAL_RST_EXTERNAL    0x04u
#define HAL_RST_WATCHDOG    0x08u
#define HAL_RST_SOFTWARE    0x10u
#define HAL_RST_UPDI        0x20u

/* Raw readings of one supervision tick. ADC0 uses VDD as its reference for every channel. */
typedef struct {
    uint16_t ref;               /* ADC0: 1.1 V internal reference as input (calibrates VDD) */
    uint16_t vbat;              /* ADC0 AIN8: VBAT/2 */
    uint16_t cs;                /* ADC0 AIN6: INA186 output, 0.5 V/A */
    uint16_t ntc_board;         /* ADC0 AIN5: board NTC divider (bias on) */
    uint16_t ntc_laser;         /* ADC0 AIN9: external NTC divider (bias on) */
    uint16_t vout;              /* ADC1 AIN3: VOUT/6 against the 1.5 V reference */
    bool interlock_closed;      /* PA2 low */
    bool switch_closed;         /* PA3 low */
    bool cc_active;             /* PB1 low (only meaningful while the CC pull-up is on) */
} hal_sample_t;

/* Survives a software reset (RAM held up by C16 through D2). */
typedef struct {
    uint16_t magic;
    uint8_t mode;
    uint8_t start;              /* app_start_t for the next boot */
    uint8_t fault;              /* latched fault kept across a glitch restart */
    uint8_t check;
} hal_noinit_t;

void hal_init(void);                /* GPIO first (converter disabled), clock, analog, timers, watchdog */
uint8_t hal_reset_cause(void);      /* HAL_RST_* flags of the last reset; clears them */
bool hal_config_ok(void);           /* fuses match firmware/src/fuses.h */
void hal_interrupts_on(void);
hal_noinit_t *hal_noinit(void);

uint8_t hal_ticks_take(void);       /* pending 1 ms ticks since the last call (saturates at 255) */
void hal_sample(hal_sample_t *s);
void hal_outputs(bool laser_enable, bool indicator, bool cc_sense);
void hal_wdt_clear(void);
bool hal_ov_latched(void);          /* AC0 over-voltage event since reset */
bool hal_power_lost(void);          /* AC2 battery-loss event */

/* hold-up */
void hal_holdup_enter(void);        /* loads off, watchdog off, AC2 on both edges, standby sleep mode */
bool hal_supply_present(void);      /* AC2 output: VBAT above the power-loss threshold */
uint32_t hal_rtc_ticks(void);       /* 1024 Hz, extended to 32 bits */
void hal_holdup_guard(bool on);     /* 1 s watchdog while polling with the supply present */
void hal_holdup_sleep(void);        /* sleep until an AC2 or RTC event (no lost wake-up) */
void hal_restart(void);             /* software reset; does not return on the target */

#endif
