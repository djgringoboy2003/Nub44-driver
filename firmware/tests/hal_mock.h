/* Scripted HAL for host tests of fw.c; see hal_mock.c. */
#ifndef HAL_MOCK_H
#define HAL_MOCK_H

#include "../src/hal.h"

#define MOCK_MAX_EVENTS 256u

typedef enum {
    EV_INIT = 1, EV_INTERRUPTS, EV_SAMPLE, EV_LASER_ON, EV_LASER_OFF, EV_WDT,
    EV_HOLDUP_ENTER, EV_SLEEP, EV_GUARD_ON, EV_GUARD_OFF, EV_RESTART,
} mock_event_t;

typedef struct {
    /* scripted inputs */
    hal_sample_t sample;
    uint16_t cs_on, cs_off, vout_on;
    uint8_t reset_cause;
    bool config_ok;
    uint8_t ticks;
    bool ov, power_lost;
    bool supply_present;
    bool (*supply)(uint32_t rtc);
    uint32_t rtc;
    hal_noinit_t noinit;
    /* observed outputs */
    bool laser, indicator, cc_sense, interrupts, guard, in_holdup, ever_enabled, slept_with_guard;
    unsigned samples, wdt_clears, restarts;
    mock_event_t events[MOCK_MAX_EVENTS];
    unsigned n_events;
} mock_hal_t;

extern mock_hal_t mock;

void mock_reset(void);          /* keeps the no-init RAM, like a software reset */
int mock_event_index(mock_event_t e);
unsigned mock_event_count(mock_event_t e);

#endif
