/* Host unit tests for firmware/src/app.c. Build and run: firmware/tests/run_tests.ps1 */
#include <stdio.h>
#include <stdlib.h>

#include "../src/app.h"

static int failures = 0, checks = 0;
#define CHECK(cond, msg) do { checks++; if (!(cond)) { failures++; printf("FAIL %s:%d %s\n", __FILE__, __LINE__, msg); } } while (0)

static app_inputs_t nominal(void)
{
    app_inputs_t in;
    in.vbat_mv = 3800; in.vout_mv = 4500; in.i_laser_ma = 4000;
    in.t_board_c10 = 300; in.t_laser_c10 = APP_T_NONE;
    in.interlock_closed = true; in.switch_pressed = false; in.cc_flag = false; in.ov_trip = false;
    return in;
}

/* run n ticks; return number of ticks with emission enabled */
static unsigned run(app_t *a, const app_inputs_t *in, unsigned n, app_outputs_t *last)
{
    unsigned on = 0;
    for (unsigned i = 0; i < n; i++) {
        app_outputs_t o = app_tick(a, in);
        on += o.laser_enable;
        if (last) *last = o;
    }
    return on;
}

static void test_emission_delay_and_default_off(void)
{
    app_t a; app_inputs_t in = nominal(); app_outputs_t o;
    app_init(&a, false, MODE_CONTINUOUS);
    CHECK(run(&a, &in, APP_EMISSION_DELAY_MS, &o) == 0, "no emission during the emission delay");
    CHECK(o.indicator, "indicator on while arming");
    run(&a, &in, 2, NULL);                        /* boot tick + arming->emit transition tick */
    CHECK(run(&a, &in, 100, &o) == 100, "continuous emission after the delay");
}

static void test_interlock_open_at_boot(void)
{
    app_t a; app_inputs_t in = nominal();
    in.interlock_closed = false;
    app_init(&a, false, MODE_CONTINUOUS);
    CHECK(run(&a, &in, 10000, NULL) == 0, "never emits with interlock open");
    in.interlock_closed = true;
    CHECK(run(&a, &in, APP_EMISSION_DELAY_MS, NULL) == 0, "closing interlock restarts the full delay");
    run(&a, &in, 1, NULL);                        /* transition tick */
    CHECK(run(&a, &in, 50, NULL) == 50, "emits after the delay once closed");
}

static void test_interlock_opens_during_emission(void)
{
    app_t a; app_inputs_t in = nominal(); app_outputs_t o;
    app_init(&a, false, MODE_CONTINUOUS);
    run(&a, &in, APP_EMISSION_DELAY_MS + 100, NULL);
    in.interlock_closed = false;
    o = app_tick(&a, &in);
    CHECK(!o.laser_enable, "disabled in the same tick the interlock opens");
    CHECK(a.state == ST_FAULT && a.fault == FAULT_INTERLOCK, "interlock fault latched");
    in.interlock_closed = true;
    CHECK(run(&a, &in, 10000, NULL) == 0, "no restart without power cycle (manual reset)");
}

static void test_low_battery_start(void)
{
    app_t a; app_inputs_t in = nominal();
    in.vbat_mv = 3150;
    app_init(&a, false, MODE_CONTINUOUS);
    CHECK(run(&a, &in, 5000, NULL) == 0, "refuses to start below 3.2 V");
    CHECK(a.fault == FAULT_LOW_BATTERY_START, "low battery start fault");
}

static void test_low_battery_cutoff(void)
{
    app_t a; app_inputs_t in = nominal();
    app_init(&a, false, MODE_CONTINUOUS);
    run(&a, &in, APP_EMISSION_DELAY_MS + 50, NULL);
    in.vbat_mv = 2850;
    CHECK(run(&a, &in, APP_VBAT_CUTOFF_MS - 5, NULL) == APP_VBAT_CUTOFF_MS - 5, "short sag tolerated");
    run(&a, &in, 10, NULL);
    CHECK(a.fault == FAULT_LOW_BATTERY, "latches off after 200 ms below 2.9 V");
}

static void enter_emission(app_t *a, app_inputs_t *in)
{
    app_init(a, false, MODE_CONTINUOUS);
    run(a, in, APP_EMISSION_DELAY_MS + 1, NULL);
}

static void test_open_load(void)
{
    app_t a; app_inputs_t in = nominal();
    enter_emission(&a, &in);
    in.vout_mv = 5500; in.i_laser_ma = 50;
    run(&a, &in, APP_SETTLE_MS - 2, NULL);
    CHECK(a.state == ST_EMIT, "not judged during soft start");
    run(&a, &in, APP_OPEN_MS + 4, NULL);
    CHECK(a.fault == FAULT_OPEN_LOAD, "open load detected");
}

static void test_short(void)
{
    app_t a; app_inputs_t in = nominal();
    enter_emission(&a, &in);
    run(&a, &in, APP_SETTLE_MS, NULL);
    in.vout_mv = 900;
    run(&a, &in, APP_SHORT_MS + 1, NULL);
    CHECK(a.fault == FAULT_SHORT, "short detected");
}

static void test_backup_limit_flag(void)
{
    app_t a; app_inputs_t in = nominal();
    enter_emission(&a, &in);
    in.cc_flag = true;
    app_tick(&a, &in);
    CHECK(a.fault == FAULT_OVERCURRENT, "backup current limit -> fault in 1 ms");
}

static void test_regulation(void)
{
    app_t a; app_inputs_t in = nominal();
    enter_emission(&a, &in);
    run(&a, &in, APP_SETTLE_MS, NULL);
    in.i_laser_ma = 4500;                         /* +12.5 %: inside the 15 % window */
    run(&a, &in, 500, NULL);
    CHECK(a.state == ST_EMIT, "within window keeps running");
    in.i_laser_ma = 3000;                         /* -25 % */
    run(&a, &in, APP_I_FAULT_MS + 1, NULL);
    CHECK(a.fault == FAULT_REGULATION, "regulation fault after 50 ms");
}

static void test_overtemp_and_overvoltage(void)
{
    app_t a; app_inputs_t in = nominal();
    app_init(&a, false, MODE_CONTINUOUS);
    in.t_board_c10 = 860;
    app_tick(&a, &in);
    CHECK(a.fault == FAULT_OVERTEMP_BOARD, "board over-temperature even while arming");

    in = nominal(); in.t_laser_c10 = 610;
    enter_emission(&a, &in);
    CHECK(a.fault == FAULT_OVERTEMP_LASER, "laser over-temperature");

    in = nominal();
    enter_emission(&a, &in);
    in.ov_trip = true;
    CHECK(!app_tick(&a, &in).laser_enable && a.fault == FAULT_OVERVOLTAGE, "over-voltage latch");
}

static void test_flash_and_modes(void)
{
    app_t a; app_inputs_t in = nominal();
    app_init(&a, true, MODE_CONTINUOUS);          /* short power gap after continuous -> flash */
    CHECK(a.mode == MODE_FLASH, "short interruption advances the mode");
    run(&a, &in, APP_EMISSION_DELAY_MS + 1, NULL);
    unsigned on = run(&a, &in, 10 * APP_FLASH_PERIOD_MS, NULL);
    CHECK(on == 10 * APP_FLASH_ON_MS, "2 Hz, 50 % duty");
    app_init(&a, false, MODE_FLASH);
    CHECK(a.mode == MODE_CONTINUOUS, "long interruption returns to continuous");
    app_init(&a, true, MODE_FLASH);
    CHECK(a.mode == MODE_CONTINUOUS, "mode wraps around");
}

int main(void)
{
    test_emission_delay_and_default_off();
    test_interlock_open_at_boot();
    test_interlock_opens_during_emission();
    test_low_battery_start();
    test_low_battery_cutoff();
    test_open_load();
    test_short();
    test_backup_limit_flag();
    test_regulation();
    test_overtemp_and_overvoltage();
    test_flash_and_modes();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
