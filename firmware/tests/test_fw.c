/*
 * Host tests of firmware/src/fw.c against the scripted HAL (hal_mock.c): start-up and reset causes,
 * watchdog servicing, tick backlog, the measurement chain and the hold-up sequence.
 */
#include "../src/fw.h"
#include "check.h"
#include "hal_mock.h"

#define T_TO_EMIT (APP_BOOT_MS + APP_EMISSION_DELAY_MS)

static void boot(uint8_t cause)
{
    mock_reset();
    mock.reset_cause = cause;
    mock.cs_on = 585;                             /* 4.0 A at VDD 3.5 V */
    mock.vout_on = 512;                           /* 4.5 V */
    fw_init();
}

static unsigned ticks(unsigned n)                 /* n polls with one tick each; returns enabled polls */
{
    unsigned on = 0;
    for (unsigned i = 0; i < n; i++) {
        mock.ticks = 1;
        fw_poll();
        on += mock.laser;
    }
    return on;
}

static void test_start_up(void)
{
    boot(HAL_RST_POWER_ON);
    CHECK(mock_event_index(EV_INIT) == 0, "hardware init (converter disabled) comes first");
    CHECK(mock_event_index(EV_INTERRUPTS) == (int)mock.n_events - 1, "interrupts enabled last");
    CHECK(!mock.laser && mock.wdt_clears == 0, "laser off; watchdog not yet cleared");
    CHECK(ticks(T_TO_EMIT) == 0, "no emission before the delay");
    CHECK(ticks(100) == 100 && fw_app()->state == ST_EMIT, "emission through the real measurement chain");
    CHECK(mock.cc_sense, "CC pull-up on while running");
}

static void test_watchdog_only_after_supervision(void)
{
    boot(HAL_RST_POWER_ON);
    for (unsigned i = 0; i < 1000u; i++) {
        mock.ticks = 0;                           /* the tick interrupt has stopped */
        fw_poll();
    }
    CHECK(mock.wdt_clears == 0 && mock.samples == 0, "no tick: no sampling and no watchdog clear (AUD-FW-03)");
    ticks(3);
    CHECK(mock.wdt_clears == 3 && mock.samples == 3, "one clear per completed cycle");
    CHECK(mock_event_index(EV_WDT) > mock_event_index(EV_LASER_OFF), "clear after the outputs were written");
}

static void test_tick_backlog(void)
{
    boot(HAL_RST_POWER_ON);
    ticks(10);
    mock.ticks = 3;
    fw_poll();
    CHECK(fw_app()->t_state_ms == 13u && fw_app()->state == ST_BOOT, "three pending ticks advance time by 3 ms");
    mock.ticks = FW_MAX_TICK_BACKLOG + 1u;
    fw_poll();
    CHECK(fw_app()->fault == FAULT_INTERNAL && fw_app()->fault_detail == DETAIL_TICK_OVERRUN, "overrun latches");
    CHECK(ticks(5000) == 0, "and never emits");
}

static void test_reset_causes(void)
{
    boot(HAL_RST_WATCHDOG | HAL_RST_POWER_ON);
    CHECK(fw_app()->fault == FAULT_INTERNAL && fw_app()->fault_detail == DETAIL_WATCHDOG_RESET,
          "watchdog reset latches a fault (AUD-FW-07)");
    CHECK(ticks(T_TO_EMIT + 1000) == 0, "no automatic re-arm after a watchdog reset");

    mock.noinit.magic = 0;
    boot(HAL_RST_SOFTWARE);
    CHECK(fw_app()->fault == FAULT_INTERNAL && fw_app()->fault_detail == DETAIL_UNEXPECTED_RESET,
          "software reset without the hold-up record");

    mock.noinit.magic = FW_NOINIT_MAGIC; mock.noinit.start = APP_START_NEXT_MODE; mock.noinit.check = 0x5A;
    boot(HAL_RST_SOFTWARE);
    CHECK(fw_app()->fault == FAULT_INTERNAL, "corrupt hold-up record is not trusted");

    mock_reset(); mock.config_ok = false; fw_init();
    CHECK(fw_app()->fault == FAULT_CONFIG && ticks(T_TO_EMIT + 10) == 0, "wrong fuses -> FAULT_CONFIG, no emission");

    boot(HAL_RST_UPDI);
    CHECK(fw_app()->state == ST_BOOT, "programming reset boots normally");
}

static void test_measurement_faults_through_hal(void)
{
    boot(HAL_RST_POWER_ON);
    mock.sample.ref = 0;                          /* reference reading broken */
    ticks(APP_MEAS_FAULT_MS);
    CHECK(fw_app()->fault == FAULT_INTERNAL && fw_app()->fault_detail == DETAIL_MEASUREMENT, "invalid reference");

    boot(HAL_RST_POWER_ON);
    mock.sample.ntc_board = 1023;                 /* RT1 open */
    CHECK(ticks(T_TO_EMIT + 100) == 0 && fw_app()->fault == FAULT_SENSOR_BOARD, "open board NTC through the HAL");

    boot(HAL_RST_POWER_ON);
    mock.sample.ntc_board = 0;                    /* RT1 shorted or NTC bias missing */
    CHECK(ticks(T_TO_EMIT + 100) == 0 && fw_app()->fault == FAULT_SENSOR_BOARD, "shorted board NTC through the HAL");

    boot(HAL_RST_POWER_ON);
    ticks(T_TO_EMIT + 50);
    mock.ov = true;                               /* AC0 interrupt */
    ticks(1);
    CHECK(!mock.laser && fw_app()->fault == FAULT_OVERVOLTAGE, "over-voltage latch through the HAL");
}

/* ------------------------------------------------------------------ hold-up sequences */
static uint32_t g_back;
static bool back_at(uint32_t rtc) { return rtc >= g_back; }
static bool bounce(uint32_t rtc) { return (rtc >= g_back && rtc < g_back + 3u) || rtc >= g_back + 6u; }

static void power_gap(bool (*supply)(uint32_t), uint32_t back_after)
{
    mock.n_events = 0;                            /* log only the hold-up sequence */
    mock.rtc = 1000;
    g_back = 1000u + back_after;
    mock.supply = supply;
    mock.power_lost = true;
    mock.ticks = 1;
    fw_poll();
}

static void reboot_after_restart(void)
{
    boot(HAL_RST_SOFTWARE);
}

static void test_click_advances_mode(void)
{
    boot(HAL_RST_POWER_ON);
    ticks(T_TO_EMIT + 100);
    power_gap(back_at, 200);                      /* 200 ms click */
    CHECK(mock.restarts == 1 && mock_event_count(EV_SLEEP) >= 1, "slept through the gap, one restart");
    CHECK(!mock.slept_with_guard, "watchdog guard never active while sleeping");
    CHECK(mock.noinit.start == APP_START_NEXT_MODE, "click recorded");
    reboot_after_restart();
    CHECK(fw_app()->mode == MODE_FLASH && fw_app()->state == ST_BOOT, "restarted in flash mode");
    CHECK(ticks(T_TO_EMIT) == 0, "the emission delay applies again after the click");
}

static void test_glitch_keeps_mode_and_fault(void)
{
    boot(HAL_RST_POWER_ON);
    ticks(T_TO_EMIT + 100);
    power_gap(back_at, 5);                        /* 5 ms sag or bounce */
    CHECK(mock.noinit.start == APP_START_KEEP_MODE, "glitch recorded");
    reboot_after_restart();
    CHECK(fw_app()->mode == MODE_CONTINUOUS && fw_app()->state == ST_BOOT, "glitch: same mode, re-armed");

    ticks(T_TO_EMIT + 100);
    mock.sample.interlock_closed = false;
    ticks(1);
    CHECK(fw_app()->fault == FAULT_INTERLOCK, "interlock fault latched");
    power_gap(back_at, 5);
    reboot_after_restart();
    CHECK(fw_app()->fault == FAULT_INTERLOCK, "a glitch is not a manual reset: fault kept");
    mock.sample.interlock_closed = true;
    CHECK(ticks(T_TO_EMIT + 100) == 0, "no emission after the glitch");

    power_gap(back_at, 300);                      /* a deliberate click is a power cycle */
    reboot_after_restart();
    CHECK(fw_app()->state == ST_BOOT && fw_app()->fault == FAULT_NONE, "click clears the latched fault");
}

static void test_long_gap_and_bounce(void)
{
    boot(HAL_RST_POWER_ON);
    ticks(10);
    power_gap(back_at, 2000);
    CHECK(mock.noinit.start == APP_START_FRESH, "long gap: fresh start");

    boot(HAL_RST_POWER_ON);
    ticks(T_TO_EMIT + 100);
    mock.n_events = 0;
    power_gap(bounce, 150);
    CHECK(mock.restarts == 1 && mock.noinit.start == APP_START_NEXT_MODE, "a bouncing return is one click");
    CHECK(mock_event_count(EV_SLEEP) >= 2, "slept again while the contact bounced");
    reboot_after_restart();
    CHECK(fw_app()->mode == MODE_FLASH, "mode advanced exactly once");
}

static void test_supply_already_back(void)
{
    boot(HAL_RST_POWER_ON);
    ticks(T_TO_EMIT + 100);
    mock.n_events = 0;
    power_gap(back_at, 0);                        /* the supply never really went away */
    CHECK(mock.restarts == 1 && mock_event_count(EV_SLEEP) == 0, "no sleep (the old code slept forever here)");
    CHECK(mock_event_index(EV_GUARD_ON) >= 0, "polling ran under the 1 s guard watchdog");
    CHECK(mock.noinit.start == APP_START_KEEP_MODE, "classified as a glitch");
    CHECK(!mock.laser, "laser off throughout");
}

int main(void)
{
    test_start_up();
    test_watchdog_only_after_supervision();
    test_tick_backlog();
    test_reset_causes();
    test_measurement_faults_through_hal();
    test_click_advances_mode();
    test_glitch_keeps_mode_and_fault();
    test_long_gap_and_bounce();
    test_supply_already_back();
    return CHECK_SUMMARY();
}
