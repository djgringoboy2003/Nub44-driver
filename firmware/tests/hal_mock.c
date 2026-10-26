/*
 * Scripted implementation of firmware/src/hal.h for host tests of fw.c (audit AUD-FW-17).
 * The test sets raw readings, flags and a supply waveform; the mock records every call.
 */
#include "hal_mock.h"

mock_hal_t mock;

void mock_reset(void)
{
    hal_noinit_t ni = mock.noinit;                /* RAM content survives a "software reset" */
    unsigned i;
    for (i = 0; i < sizeof mock; i++) ((unsigned char *)&mock)[i] = 0;
    mock.noinit = ni;
    mock.config_ok = true;
    mock.supply_present = true;
    /* nominal raw readings at VDD 3.5 V: VBAT 3.8 V, NTC 30 C, laser NTC not fitted, no current */
    mock.sample.ref = 322;
    mock.sample.vbat = 556;
    mock.sample.cs = 0;
    mock.sample.ntc_board = 445;
    mock.sample.ntc_laser = 1023;
    mock.sample.vout = 0;
    mock.sample.interlock_closed = true;
}

static void log_event(mock_event_t e)
{
    if (mock.n_events < MOCK_MAX_EVENTS) mock.events[mock.n_events++] = e;
}

int mock_event_index(mock_event_t e)
{
    for (unsigned i = 0; i < mock.n_events; i++) if (mock.events[i] == e) return (int)i;
    return -1;
}

unsigned mock_event_count(mock_event_t e)
{
    unsigned n = 0;
    for (unsigned i = 0; i < mock.n_events; i++) n += mock.events[i] == e;
    return n;
}

void hal_init(void) { mock.laser = false; log_event(EV_INIT); }
uint8_t hal_reset_cause(void) { uint8_t c = mock.reset_cause; mock.reset_cause = 0; return c; }
bool hal_config_ok(void) { return mock.config_ok; }
void hal_interrupts_on(void) { mock.interrupts = true; log_event(EV_INTERRUPTS); }
hal_noinit_t *hal_noinit(void) { return &mock.noinit; }

uint8_t hal_ticks_take(void)
{
    uint8_t n = mock.ticks;
    mock.ticks = 0;
    return n;
}

void hal_sample(hal_sample_t *s)
{
    /* plant: the laser current follows the enable output of the previous cycle */
    mock.sample.cs = mock.laser ? mock.cs_on : mock.cs_off;
    mock.sample.vout = mock.laser ? mock.vout_on : 0;
    *s = mock.sample;
    mock.samples++;
    log_event(EV_SAMPLE);
}

void hal_outputs(bool laser_enable, bool indicator, bool cc_sense)
{
    mock.laser = laser_enable && !mock.ov;
    mock.indicator = indicator;
    mock.cc_sense = cc_sense && mock.laser;
    if (mock.laser) mock.ever_enabled = true;
    log_event(mock.laser ? EV_LASER_ON : EV_LASER_OFF);
}

void hal_wdt_clear(void) { mock.wdt_clears++; log_event(EV_WDT); }
bool hal_ov_latched(void) { return mock.ov; }
bool hal_power_lost(void) { return mock.power_lost; }

void hal_holdup_enter(void)
{
    mock.laser = false;
    mock.in_holdup = true;
    log_event(EV_HOLDUP_ENTER);
}

/* each hal_rtc_ticks() call is one loop iteration: time advances by one RTC tick */
uint32_t hal_rtc_ticks(void) { return mock.rtc++; }

bool hal_supply_present(void)
{
    return mock.supply ? mock.supply(mock.rtc) : mock.supply_present;
}

void hal_holdup_guard(bool on)
{
    if (on != mock.guard) log_event(on ? EV_GUARD_ON : EV_GUARD_OFF);
    mock.guard = on;
}

void hal_holdup_sleep(void)
{
    uint32_t i;
    if (mock.guard) mock.slept_with_guard = true;
    log_event(EV_SLEEP);
    /* sleep until the supply returns (an AC2 edge), bounded so a broken test cannot hang */
    for (i = 0; i < 1000000UL && !hal_supply_present(); i++) mock.rtc++;
}

void hal_restart(void)
{
    mock.restarts++;
    mock.in_holdup = false;
    log_event(EV_RESTART);
}
