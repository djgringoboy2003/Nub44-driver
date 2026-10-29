/* Host unit tests for firmware/src/app.c (state machine). Build and run: firmware/build.py */
#include <stdlib.h>

#include "../src/app.h"
#include "check.h"

/* Time from power-up to the last tick without emission: boot settling + emission delay. */
#define T_TO_EMIT (APP_BOOT_MS + APP_EMISSION_DELAY_MS)

/* A minimal plant: the measured current and VOUT follow the previous tick's enable output. */
typedef struct {
    app_t a;
    app_inputs_t in;
    uint16_t i_on, i_off, vout_on, vout_off;
    bool en;
    app_outputs_t o;
} sim_t;

static app_inputs_t nominal(void)
{
    app_inputs_t in;
    in.vbat_mv = 3800; in.vout_mv = 0; in.i_laser_ma = 0;
    in.t_board_c10 = 300; in.t_board_status = SENSOR_OK;
    in.t_laser_c10 = APP_T_NONE; in.t_laser_status = SENSOR_OPEN;        /* laser NTC not fitted */
    in.meas_valid = true;
    in.interlock_closed = true; in.switch_closed = false; in.cc_flag = false; in.ov_trip = false;
    return in;
}

static void sim_init(sim_t *s, app_start_t start, app_mode_t mode)
{
    app_init(&s->a, start, mode);
    s->in = nominal();
    s->i_on = 4500; s->i_off = 0; s->vout_on = 4500; s->vout_off = 0;
    s->en = false;
    s->o.laser_enable = s->o.indicator = s->o.cc_sense = false;
}

static app_outputs_t sim_tick(sim_t *s)
{
    s->in.i_laser_ma = s->en ? s->i_on : s->i_off;
    s->in.vout_mv = s->en ? s->vout_on : s->vout_off;
    s->o = app_tick(&s->a, &s->in);
    s->en = s->o.laser_enable;
    return s->o;
}

/* run n ticks; return number of ticks with emission enabled */
static unsigned sim_run(sim_t *s, unsigned n)
{
    unsigned on = 0;
    for (unsigned i = 0; i < n; i++) {
        on += sim_tick(s).laser_enable;
    }
    return on;
}

/* The default-build tests below assume the optional laser NTC; the APP_LASER_NTC_REQUIRED build runs only
 * test_laser_ntc_required(), so gcc -Wunused-function would reject them there. */
#if !APP_LASER_NTC_REQUIRED
static void emitting(sim_t *s)
{
    sim_init(s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(s, T_TO_EMIT + 1);
}

/* ------------------------------------------------------------------ start-up and interlock */
static void test_emission_delay_and_default_off(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    CHECK(sim_run(&s, APP_BOOT_MS) == 0 && !s.o.indicator, "boot: no emission, no indication");
    CHECK(sim_run(&s, APP_EMISSION_DELAY_MS) == 0, "no emission during the emission delay");
    CHECK(s.o.indicator, "indicator on while arming");
    CHECK(sim_run(&s, 100) == 100, "continuous emission after the delay");
}

static void test_interlock_open_at_boot(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.interlock_closed = false;
    CHECK(sim_run(&s, 10000) == 0, "never emits with interlock open");
    CHECK(s.a.state == ST_WAIT_INTERLOCK, "waits for the interlock");
    s.in.interlock_closed = true;
    sim_run(&s, 1);                               /* WAIT -> ARMING transition tick */
    CHECK(sim_run(&s, APP_EMISSION_DELAY_MS) == 0, "closing interlock restarts the full delay");
    CHECK(sim_run(&s, 50) == 50, "emits after the delay once closed");
}

static void test_interlock_reopens_while_arming(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(&s, APP_BOOT_MS + 1500);
    s.in.interlock_closed = false;
    sim_run(&s, 10);
    s.in.interlock_closed = true;
    sim_run(&s, 1);                               /* WAIT -> ARMING transition tick */
    CHECK(sim_run(&s, APP_EMISSION_DELAY_MS) == 0, "re-closing the interlock restarts the full delay");
    CHECK(sim_run(&s, 10) == 10, "then emits");
}

static void test_interlock_opens_during_emission(void)
{
    sim_t s;
    emitting(&s);
    sim_run(&s, 100);
    s.in.interlock_closed = false;
    CHECK(!sim_tick(&s).laser_enable, "disabled in the same tick the interlock opens");
    CHECK(s.a.state == ST_FAULT && s.a.fault == FAULT_INTERLOCK, "interlock fault latched");
    s.in.interlock_closed = true;
    CHECK(sim_run(&s, 10000) == 0, "no restart without power cycle (manual reset)");
}

/* ------------------------------------------------------------------ battery */
static void test_low_battery_start(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.vbat_mv = 3150;
    CHECK(sim_run(&s, 5000) == 0, "refuses to start below 3.2 V");
    CHECK(s.a.fault == FAULT_LOW_BATTERY_START && s.a.fault_detail == DETAIL_NONE, "low battery start fault");
}

static void test_start_voltage_rechecked_before_emission(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.interlock_closed = false;                /* long wait with the interlock open */
    sim_run(&s, 30000);
    s.in.vbat_mv = 3150;                          /* the cell has run down meanwhile */
    s.in.interlock_closed = true;
    CHECK(sim_run(&s, APP_EMISSION_DELAY_MS + 100) == 0, "no emission below 3.2 V after re-arming");
    CHECK(s.a.fault == FAULT_LOW_BATTERY_START && s.a.fault_detail == DETAIL_ARMING_RECHECK,
          "start voltage re-checked at the end of arming");
}

static void test_voltage_dip_during_arming_recovers(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(&s, APP_BOOT_MS + 500);
    s.in.vbat_mv = 3000;                          /* a transient while arming (converter off) */
    sim_run(&s, 200);
    s.in.vbat_mv = 3500;
    sim_run(&s, APP_EMISSION_DELAY_MS - 700);
    CHECK(sim_run(&s, 10) == 10 && s.a.state == ST_EMIT, "only the voltage at the end of arming decides");
}

static void test_low_battery_cutoff(void)
{
    sim_t s;
    emitting(&s);
    sim_run(&s, 50);
    s.in.vbat_mv = 2850;
    CHECK(sim_run(&s, APP_VBAT_CUTOFF_MS - 5) == APP_VBAT_CUTOFF_MS - 5, "short sag tolerated");
    s.in.vbat_mv = 3000;
    sim_run(&s, 1);                               /* recovery resets the timer */
    s.in.vbat_mv = 2850;
    CHECK(sim_run(&s, APP_VBAT_CUTOFF_MS - 5) == APP_VBAT_CUTOFF_MS - 5, "timer restarts after recovery");
    sim_run(&s, 10);
    CHECK(s.a.fault == FAULT_LOW_BATTERY, "latches off after 200 ms below 2.9 V");
    s.in.vbat_mv = 3600;                          /* cell recovers at rest */
    CHECK(sim_run(&s, 10000) == 0, "low-battery latch needs a power cycle");
}

static void test_low_battery_warning_blinks(void)
{
    sim_t s;
    unsigned on = 0;
    emitting(&s);
    s.in.vbat_mv = 3050;
    for (unsigned i = 0; i < 1000; i++) {
        on += sim_tick(&s).indicator;
    }
    CHECK(s.a.state == ST_EMIT && s.a.lowbat_warning, "warning below 3.1 V while emitting");
    CHECK(on > 400 && on < 600, "indicator blinks at 4 Hz, 50 %");
}

/* ------------------------------------------------------------------ output faults */
static void test_open_load(void)
{
    sim_t s;
    emitting(&s);
    s.vout_on = 5500; s.i_on = 50;
    sim_run(&s, APP_SETTLE_MS - 3);
    CHECK(s.a.state == ST_EMIT, "not judged during soft start");
    sim_run(&s, APP_OPEN_MS + 4);
    CHECK(s.a.fault == FAULT_OPEN_LOAD, "open load detected");
}

static void test_short(void)
{
    sim_t s;
    emitting(&s);
    sim_run(&s, APP_SETTLE_MS);
    s.vout_on = 900;
    sim_run(&s, APP_SHORT_MS + 1);
    CHECK(s.a.fault == FAULT_SHORT, "short detected");
}

static void test_backup_limit_flag(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(&s, T_TO_EMIT);
    s.in.cc_flag = true;                          /* floating CC pin before the pull-up is on */
    CHECK(sim_tick(&s).laser_enable && !s.o.cc_sense, "first enabled tick: CC pull-up still off");
    CHECK(sim_tick(&s).laser_enable && s.o.cc_sense, "CC pull-up on from the second enabled tick");
    CHECK(s.a.state == ST_EMIT, "CC ignored until the pull-up has settled");
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_OVERCURRENT && !s.o.laser_enable, "backup current limit -> fault 3 ms after enable");

    emitting(&s);
    sim_run(&s, 100);
    s.in.cc_flag = true;
    CHECK(!sim_tick(&s).laser_enable && s.a.fault == FAULT_OVERCURRENT, "CC during emission -> fault in 1 ms");
}

static void test_regulation(void)
{
    sim_t s;
    emitting(&s);
    sim_run(&s, APP_SETTLE_MS);
    s.i_on = 5062;                                /* +12.5 %: inside the 15 % window */
    sim_run(&s, 500);
    CHECK(s.a.state == ST_EMIT, "within window keeps running");
    s.i_on = 3375;                                /* -25 % */
    sim_run(&s, APP_I_FAULT_MS + 1);
    CHECK(s.a.fault == FAULT_REGULATION, "regulation fault after 50 ms");
}

static void test_overvoltage_in_every_state(void)
{
    sim_t s;
    emitting(&s);
    s.in.ov_trip = true;
    CHECK(!sim_tick(&s).laser_enable && s.a.fault == FAULT_OVERVOLTAGE, "over-voltage latch while emitting");

    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(&s, APP_BOOT_MS + 100);
    s.in.ov_trip = true;
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_OVERVOLTAGE, "over-voltage event while arming is latched at once");

    sim_init(&s, APP_START_NEXT_MODE, MODE_CONTINUOUS);   /* flash */
    sim_run(&s, T_TO_EMIT + APP_FLASH_ON_MS + 10);        /* inside an off phase */
    CHECK(s.a.state == ST_EMIT && !s.o.laser_enable, "in a flash off phase");
    s.in.ov_trip = true;
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_OVERVOLTAGE && !s.o.laser_enable, "latched during the off phase");
}

static void test_output_while_off(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(&s, APP_BOOT_MS + 100);
    s.i_off = 150;                                /* below the threshold: noise or offset */
    sim_run(&s, 500);
    CHECK(s.a.state == ST_ARMING, "150 mA while off is tolerated");
    s.i_off = 800;                                /* converter running although firmware holds it off */
    sim_run(&s, APP_OFF_MS - 1);
    CHECK(s.a.state == ST_ARMING, "confirmation time");
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_OUTPUT_WHILE_OFF, "current while disabled latches a fault");
    CHECK(sim_run(&s, 5000) == 0, "and never emits");

    /* normal turn-off decay in flash mode is inside the blanking time */
    sim_init(&s, APP_START_NEXT_MODE, MODE_CONTINUOUS);
    sim_run(&s, T_TO_EMIT);
    for (unsigned i = 0; i < 20 * APP_FLASH_PERIOD_MS; i++) {
        s.in.i_laser_ma = s.en ? 4500 : (s.a.t_disabled_ms < 5u ? 1500 : 0);
        s.in.vout_mv = s.en ? 4500 : 0;
        s.o = app_tick(&s.a, &s.in);
        s.en = s.o.laser_enable;
    }
    CHECK(s.a.state == ST_EMIT, "turn-off decay within the blanking time is not a fault");
}

/* ------------------------------------------------------------------ temperature sensors */
static void test_board_overtemp_boundary(void)
{
    sim_t s;
    emitting(&s);
    s.in.t_board_c10 = APP_T_BOARD_MAX_C10;       /* 85.0 C: at the limit, not above */
    sim_run(&s, 100);
    CHECK(s.a.state == ST_EMIT, "85.0 C does not trip");
    s.in.t_board_c10 = APP_T_BOARD_MAX_C10 + 1;
    CHECK(!sim_tick(&s).laser_enable && s.a.fault == FAULT_OVERTEMP_BOARD, "85.1 C trips at once");

    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.t_board_c10 = 860;
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_OVERTEMP_BOARD, "board over-temperature even while booting");
}

static void test_board_ntc_open_and_short(void)
{
    sim_t s;
    emitting(&s);
    s.in.t_board_status = SENSOR_OPEN; s.in.t_board_c10 = APP_T_NONE;
    CHECK(sim_run(&s, APP_SENSOR_FAULT_MS - 1) == APP_SENSOR_FAULT_MS - 1, "one invalid reading is not yet a fault");
    CHECK(!sim_tick(&s).laser_enable, "open board NTC stops emission");
    CHECK(s.a.fault == FAULT_SENSOR_BOARD && s.a.fault_detail == SENSOR_OPEN, "open NTC -> sensor fault");

    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.t_board_status = SENSOR_SHORT; s.in.t_board_c10 = APP_T_NONE;
    CHECK(sim_run(&s, 10000) == 0, "shorted board NTC at power-up: never emits");
    CHECK(s.a.fault == FAULT_SENSOR_BOARD && s.a.fault_detail == SENSOR_SHORT, "short -> sensor fault");

    emitting(&s);                                 /* a glitch shorter than the confirmation time */
    s.in.t_board_status = SENSOR_OPEN;
    sim_run(&s, APP_SENSOR_FAULT_MS - 1);
    s.in.t_board_status = SENSOR_OK;
    CHECK(sim_run(&s, 1000) == 1000 && s.a.state == ST_EMIT, "a 49 ms glitch is tolerated and recovers");
}

static void test_laser_ntc_optional(void)
{
    sim_t s;
    emitting(&s);                                 /* absent at power-up */
    CHECK(s.a.laser_ntc == LASER_NTC_ABSENT, "absent at boot -> not fitted");
    CHECK(sim_run(&s, 5000) == 5000, "absent laser NTC is ignored");

    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);   /* fitted, then the wire breaks */
    s.in.t_laser_status = SENSOR_OK; s.in.t_laser_c10 = 300;
    sim_run(&s, T_TO_EMIT + 100);
    CHECK(s.a.laser_ntc == LASER_NTC_FITTED && s.a.state == ST_EMIT, "fitted at boot");
    s.in.t_laser_status = SENSOR_OPEN; s.in.t_laser_c10 = APP_T_NONE;
    sim_run(&s, APP_SENSOR_FAULT_MS);
    CHECK(s.a.fault == FAULT_SENSOR_LASER && s.a.fault_detail == SENSOR_OPEN, "fitted NTC that opens -> fault");

    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);   /* shorted at power-up */
    s.in.t_laser_status = SENSOR_SHORT;
    CHECK(sim_run(&s, 5000) == 0 && s.a.fault == FAULT_SENSOR_LASER, "a short is never 'not fitted'");

    emitting(&s);                                 /* absent at boot, later reads a valid hot value */
    s.in.t_laser_status = SENSOR_OK; s.in.t_laser_c10 = 610;
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_OVERTEMP_LASER, "any valid laser reading is checked against the limit");

    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.t_laser_status = SENSOR_OK; s.in.t_laser_c10 = 610;
    sim_run(&s, T_TO_EMIT);
    CHECK(s.a.fault == FAULT_OVERTEMP_LASER, "laser over-temperature");
}

static void test_measurement_reference_invalid(void)
{
    sim_t s;
    emitting(&s);
    s.in.meas_valid = false;
    sim_run(&s, APP_MEAS_FAULT_MS - 1);
    CHECK(s.a.state == ST_EMIT, "single invalid reference readings are tolerated briefly");
    sim_tick(&s);
    CHECK(s.a.fault == FAULT_INTERNAL && s.a.fault_detail == DETAIL_MEASUREMENT, "persistent invalid reference");
}

/* ------------------------------------------------------------------ switch and modes */
static unsigned press(sim_t *s, unsigned bounces, unsigned hold, unsigned release)
{
    app_mode_t before = s->a.mode;
    unsigned changes = 0;
    for (unsigned i = 0; i < bounces; i++) {
        s->in.switch_closed = (i % 2u) == 0u;
        sim_tick(s);
        changes += s->a.mode != before; before = s->a.mode;
    }
    s->in.switch_closed = true;
    for (unsigned i = 0; i < hold; i++) { sim_tick(s); changes += s->a.mode != before; before = s->a.mode; }
    for (unsigned i = 0; i < bounces; i++) {
        s->in.switch_closed = (i % 2u) != 0u;
        sim_tick(s);
        changes += s->a.mode != before; before = s->a.mode;
    }
    s->in.switch_closed = false;
    for (unsigned i = 0; i < release; i++) { sim_tick(s); changes += s->a.mode != before; before = s->a.mode; }
    return changes;
}

static void test_switch_debounce(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    sim_run(&s, APP_BOOT_MS + 10);
    CHECK(press(&s, 15, 100, 300) == 1, "a noisy press changes the mode exactly once");
    CHECK(s.a.mode == MODE_FLASH, "mode advanced");
    CHECK(press(&s, 0, APP_SW_DEBOUNCE_MS - 1, 300) == 0, "a contact shorter than the debounce time is ignored");
    CHECK(press(&s, 0, 40, 40) == 1, "a clean press counts");
    CHECK(press(&s, 0, 40, 40) == 0, "a second press inside the lockout is ignored");
    sim_run(&s, APP_SW_LOCKOUT_MS);
    CHECK(press(&s, 0, 40, 40) == 1, "a press after the lockout counts");
}

static void test_switch_held_at_boot_and_stuck(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.switch_closed = true;                    /* held while the battery is inserted */
    sim_run(&s, APP_BOOT_MS + 1000);
    CHECK(s.a.mode == MODE_CONTINUOUS, "a switch held at power-up is not a press");
    sim_run(&s, 30000);
    CHECK(s.a.mode == MODE_CONTINUOUS, "a stuck switch never changes the mode");
    s.in.switch_closed = false;
    sim_run(&s, 100);
    CHECK(press(&s, 0, 40, 40) == 1, "after a release the switch works");
}

static void test_flash_and_modes(void)
{
    sim_t s;
    unsigned on;
    sim_init(&s, APP_START_NEXT_MODE, MODE_CONTINUOUS);   /* short power gap after continuous -> flash */
    CHECK(s.a.mode == MODE_FLASH, "short interruption advances the mode");
    sim_run(&s, T_TO_EMIT);
    on = sim_run(&s, 10 * APP_FLASH_PERIOD_MS);
    CHECK(on == 10 * APP_FLASH_ON_MS, "2 Hz, 50 % duty");
    app_init(&s.a, APP_START_FRESH, MODE_FLASH);
    CHECK(s.a.mode == MODE_CONTINUOUS, "long interruption returns to continuous");
    app_init(&s.a, APP_START_NEXT_MODE, MODE_FLASH);
    CHECK(s.a.mode == MODE_CONTINUOUS, "mode wraps around");
    app_init(&s.a, APP_START_KEEP_MODE, MODE_FLASH);
    CHECK(s.a.mode == MODE_FLASH, "a glitch keeps the mode");
    app_init(&s.a, APP_START_NEXT_MODE, (app_mode_t)7);
    CHECK(s.a.mode == MODE_CONTINUOUS, "corrupt stored mode -> continuous");

    emitting(&s);                                  /* switch during continuous emission -> flash */
    sim_run(&s, 100);
    press(&s, 0, 40, 0);
    on = sim_run(&s, 10 * APP_FLASH_PERIOD_MS - 40);
    CHECK(s.a.mode == MODE_FLASH && on > 4 * APP_FLASH_PERIOD_MS && on < 6 * APP_FLASH_PERIOD_MS,
          "switch changes to flash while emitting");
}

/* ------------------------------------------------------------------ fault indication */
static unsigned blinks_in(sim_t *s, unsigned ms, unsigned *longest_off)
{
    unsigned rises = 0, off = 0;
    bool prev = s->o.indicator;
    *longest_off = 0;
    for (unsigned i = 0; i < ms; i++) {
        bool now = sim_tick(s).indicator;
        rises += now && !prev;
        off = now ? 0 : off + 1;
        if (off > *longest_off) *longest_off = off;
        prev = now;
    }
    return rises;
}

static void test_fault_blink_codes_readable(void)
{
    sim_t s;
    unsigned pause, period;
    for (app_fault_t f = FAULT_LOW_BATTERY_START; f <= FAULT_CONFIG; f++) {
        emitting(&s);
        app_force_fault(&s.a, f, DETAIL_NONE);
        period = (unsigned)f * APP_BLINK_MS + APP_BLINK_PAUSE_MS;
        sim_run(&s, 1);                           /* align to the start of a period */
        sim_run(&s, period - 1);
        CHECK(blinks_in(&s, period, &pause) == (unsigned)f, "n blinks per period");
        CHECK(pause >= APP_BLINK_PAUSE_MS, "a pause separates repetitions");
    }
}

static void test_forced_fault_and_latch(void)
{
    sim_t s;
    emitting(&s);
    app_force_fault(&s.a, FAULT_INTERNAL, DETAIL_TICK_OVERRUN);
    CHECK(!sim_tick(&s).laser_enable && s.a.fault == FAULT_INTERNAL, "forced fault stops emission");
    app_force_fault(&s.a, FAULT_SHORT, DETAIL_NONE);
    CHECK(s.a.fault == FAULT_INTERNAL && s.a.fault_detail == DETAIL_TICK_OVERRUN, "first fault wins");
    CHECK(sim_run(&s, 20000) == 0 && !s.o.cc_sense, "latched: no emission, no CC pull-up");
}

#endif /* !APP_LASER_NTC_REQUIRED */

#if APP_LASER_NTC_REQUIRED
static void test_laser_ntc_required(void)
{
    sim_t s;
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    CHECK(sim_run(&s, 5000) == 0 && s.a.fault == FAULT_SENSOR_LASER, "required laser NTC missing at boot -> fault");
    sim_init(&s, APP_START_FRESH, MODE_CONTINUOUS);
    s.in.t_laser_status = SENSOR_OK; s.in.t_laser_c10 = 300;
    CHECK(sim_run(&s, T_TO_EMIT + 10) == 10, "required laser NTC present -> emits");
}
#endif

int main(void)
{
#if APP_LASER_NTC_REQUIRED
    test_laser_ntc_required();
#else
    test_emission_delay_and_default_off();
    test_interlock_open_at_boot();
    test_interlock_reopens_while_arming();
    test_interlock_opens_during_emission();
    test_low_battery_start();
    test_start_voltage_rechecked_before_emission();
    test_voltage_dip_during_arming_recovers();
    test_low_battery_cutoff();
    test_low_battery_warning_blinks();
    test_open_load();
    test_short();
    test_backup_limit_flag();
    test_regulation();
    test_overvoltage_in_every_state();
    test_output_while_off();
    test_board_overtemp_boundary();
    test_board_ntc_open_and_short();
    test_laser_ntc_optional();
    test_measurement_reference_invalid();
    test_switch_debounce();
    test_switch_held_at_boot_and_stuck();
    test_flash_and_modes();
    test_fault_blink_codes_readable();
    test_forced_fault_and_latch();
#endif
    return CHECK_SUMMARY();
}
