#include "app.h"

static void enter(app_t *a, app_state_t s)
{
    a->state = s;
    a->t_state_ms = 0;
}

static void fail(app_t *a, app_fault_t f, uint8_t detail)
{
    if (a->state != ST_FAULT) {       /* first fault wins; latched until power is removed */
        a->fault = f;
        a->fault_detail = detail;
        enter(a, ST_FAULT);
    }
}

/* Count consecutive ticks with `cond`; true once the count reaches `limit`. */
static bool confirm(uint16_t *ms, bool cond, uint16_t limit)
{
    if (!cond) {
        *ms = 0;
        return false;
    }
    if (*ms < 0xFFFFu) {
        (*ms)++;
    }
    return *ms >= limit;
}

void app_init(app_t *a, app_start_t start, app_mode_t stored_mode)
{
    a->state = ST_BOOT;
    a->fault = FAULT_NONE;
    a->fault_detail = DETAIL_NONE;
    a->laser_ntc = LASER_NTC_UNKNOWN;
    a->t_state_ms = 0;
    a->t_enabled_ms = 0;
    a->t_disabled_ms = APP_OFF_BLANK_MS;   /* never enabled: the output-off check is active at once */
    a->lowbat_ms = a->open_ms = a->short_ms = a->cc_ms = a->ireg_ms = 0;
    a->sens_board_ms = a->sens_laser_ms = a->meas_ms = a->offcur_ms = 0;
    a->sw_stable_ms = a->sw_lockout_ms = 0;
    a->sw_raw = false;
    a->sw_armed = false;              /* a switch held at power-up is not a press */
    a->lowbat_warning = false;
    a->was_enabled = false;
    if (stored_mode >= MODE_COUNT || start == APP_START_FRESH) {
        a->mode = MODE_CONTINUOUS;
    } else if (start == APP_START_NEXT_MODE) {
        a->mode = (app_mode_t)((stored_mode + 1) % MODE_COUNT);
    } else {
        a->mode = stored_mode;
    }
}

void app_force_fault(app_t *a, app_fault_t f, uint8_t detail)
{
    fail(a, f, detail);
}

/* Debounced e-switch: true once per accepted press. A press counts only after a debounced release, so a
 * switch held at power-up or stuck closed never changes the mode, and presses closer than the lockout
 * are ignored. */
static bool switch_press(app_t *a, bool closed)
{
    bool press = false;
    if (a->sw_lockout_ms > 0u) {
        a->sw_lockout_ms--;
    }
    if (closed != a->sw_raw) {
        a->sw_raw = closed;
        a->sw_stable_ms = 0;
        return false;
    }
    if (a->sw_stable_ms < APP_SW_DEBOUNCE_MS && ++a->sw_stable_ms == APP_SW_DEBOUNCE_MS) {
        if (!closed) {
            a->sw_armed = true;
        } else if (a->sw_armed) {
            a->sw_armed = false;
            if (a->sw_lockout_ms == 0u) {
                press = true;
                a->sw_lockout_ms = APP_SW_LOCKOUT_MS;
            }
        }
    }
    return press;
}

/* Checks that apply in every non-fault state. */
static void supervise(app_t *a, const app_inputs_t *in)
{
    bool tolerated;

    if (in->ov_trip) {                                  /* AUD-FW-14: latch even while the converter is off */
        fail(a, FAULT_OVERVOLTAGE, DETAIL_NONE);
        return;
    }
    if (confirm(&a->meas_ms, !in->meas_valid, APP_MEAS_FAULT_MS)) {
        fail(a, FAULT_INTERNAL, DETAIL_MEASUREMENT);
        return;
    }

    /* board NTC: fitted on every board, mandatory (AUD-FW-01) */
    if (in->t_board_status == SENSOR_OK) {
        a->sens_board_ms = 0;
        if (in->t_board_c10 > APP_T_BOARD_MAX_C10) {
            fail(a, FAULT_OVERTEMP_BOARD, DETAIL_NONE);
            return;
        }
    } else if (confirm(&a->sens_board_ms, true, APP_SENSOR_FAULT_MS)) {
        fail(a, FAULT_SENSOR_BOARD, (uint8_t)in->t_board_status);
        return;
    }

    /* laser NTC: optional; absent (open) at power-up means not fitted (AUD-FW-02) */
    if (in->t_laser_status == SENSOR_OK) {
        a->sens_laser_ms = 0;
        if (in->t_laser_c10 > APP_T_LASER_MAX_C10) {
            fail(a, FAULT_OVERTEMP_LASER, DETAIL_NONE);
            return;
        }
    } else {
        tolerated = in->t_laser_status == SENSOR_OPEN && !APP_LASER_NTC_REQUIRED
                    && a->laser_ntc != LASER_NTC_FITTED;
        if (tolerated) {
            a->sens_laser_ms = 0;
        } else if (confirm(&a->sens_laser_ms, true, APP_SENSOR_FAULT_MS)) {
            fail(a, FAULT_SENSOR_LASER, (uint8_t)in->t_laser_status);
            return;
        }
    }

    /* enable path cross-check (AUD-FW-15): no laser current while the firmware holds the converter off */
    if (!a->was_enabled && in->meas_valid) {
        if (confirm(&a->offcur_ms, a->t_disabled_ms > APP_OFF_BLANK_MS && in->i_laser_ma > APP_OFF_I_MA,
                    APP_OFF_MS)) {
            fail(a, FAULT_OUTPUT_WHILE_OFF, DETAIL_NONE);
        }
    } else {
        a->offcur_ms = 0;
    }
}

/* fault checks that only make sense while the converter runs */
static void check_running(app_t *a, const app_inputs_t *in)
{
    if (a->t_enabled_ms >= APP_CC_ARM_MS && in->cc_flag) {
        if (++a->cc_ms >= APP_CC_FLAG_MS) { fail(a, FAULT_OVERCURRENT, DETAIL_NONE); return; }
    } else {
        a->cc_ms = 0;
    }
    if (a->t_enabled_ms < APP_SETTLE_MS) {
        return;                         /* soft start in progress */
    }
    if (in->vout_mv > APP_OPEN_VOUT_MV && in->i_laser_ma < APP_OPEN_I_MA) {
        if (++a->open_ms >= APP_OPEN_MS) { fail(a, FAULT_OPEN_LOAD, DETAIL_NONE); return; }
    } else {
        a->open_ms = 0;
    }
    if (in->vout_mv < APP_SHORT_VOUT_MV) {
        if (++a->short_ms >= APP_SHORT_MS) { fail(a, FAULT_SHORT, DETAIL_NONE); return; }
    } else {
        a->short_ms = 0;
    }
    {
        uint32_t lo = (uint32_t)APP_I_SET_MA * (100u - APP_I_TOL_PCT) / 100u;
        uint32_t hi = (uint32_t)APP_I_SET_MA * (100u + APP_I_TOL_PCT) / 100u;
        if (in->i_laser_ma < lo || in->i_laser_ma > hi) {
            if (++a->ireg_ms >= APP_I_FAULT_MS) { fail(a, FAULT_REGULATION, DETAIL_NONE); return; }
        } else {
            a->ireg_ms = 0;
        }
    }
}

app_outputs_t app_tick(app_t *a, const app_inputs_t *in)
{
    app_outputs_t out = {false, false, false};
    bool enable = false;
    bool pressed = switch_press(a, in->switch_closed);
    a->t_state_ms += APP_TICK_MS;
    if (!a->was_enabled && a->t_disabled_ms < 0xFFFFFFFFu) {
        a->t_disabled_ms += APP_TICK_MS;
    }

    if (a->state != ST_FAULT) {
        supervise(a, in);
    }

    switch (a->state) {
    case ST_BOOT:                      /* inputs settle; no indication, no emission */
        if (a->t_state_ms < APP_BOOT_MS) {
            break;
        }
        a->laser_ntc = in->t_laser_status == SENSOR_OK ? LASER_NTC_FITTED : LASER_NTC_ABSENT;
        if (in->vbat_mv < APP_VBAT_START_MIN_MV) {
            fail(a, FAULT_LOW_BATTERY_START, DETAIL_NONE);
        } else if (!in->interlock_closed) {
            enter(a, ST_WAIT_INTERLOCK);
        } else {
            enter(a, ST_ARMING);
        }
        break;

    case ST_WAIT_INTERLOCK:            /* interlock open at power-up: wait, never emit */
        if (in->interlock_closed) {
            enter(a, ST_ARMING);
        }
        break;

    case ST_ARMING:                    /* emission delay with the indicator on */
        out.indicator = true;
        if (!in->interlock_closed) {
            enter(a, ST_WAIT_INTERLOCK);
        } else if (pressed) {
            a->mode = (app_mode_t)((a->mode + 1) % MODE_COUNT);
        } else if (a->t_state_ms >= APP_EMISSION_DELAY_MS) {
            if (in->vbat_mv < APP_VBAT_START_MIN_MV) {   /* AUD-FW-11: resting voltage before every start */
                fail(a, FAULT_LOW_BATTERY_START, DETAIL_ARMING_RECHECK);
            } else {
                enter(a, ST_EMIT);
                a->t_enabled_ms = 0;
            }
        }
        break;

    case ST_EMIT:
        out.indicator = true;
        if (!in->interlock_closed) {   /* hardware already disabled; require a manual reset */
            fail(a, FAULT_INTERLOCK, DETAIL_NONE);
            break;
        }
        if (pressed) {
            a->mode = (app_mode_t)((a->mode + 1) % MODE_COUNT);
            a->t_state_ms = 0;
            a->t_enabled_ms = 0;
        }
        if (a->mode == MODE_CONTINUOUS) {
            enable = true;
        } else {
            enable = (a->t_state_ms % APP_FLASH_PERIOD_MS) < APP_FLASH_ON_MS;
        }
        if (enable) {
            a->t_enabled_ms += APP_TICK_MS;
            if (in->vbat_mv < APP_VBAT_CUTOFF_MV) {
                if ((a->lowbat_ms += APP_TICK_MS) >= APP_VBAT_CUTOFF_MS) {
                    fail(a, FAULT_LOW_BATTERY, DETAIL_NONE);
                }
            } else {
                a->lowbat_ms = 0;
            }
            a->lowbat_warning = a->lowbat_warning || in->vbat_mv < APP_VBAT_WARN_MV;
            if (a->state == ST_EMIT) {
                check_running(a, in);
            }
        } else {
            a->t_enabled_ms = 0;        /* each flash restarts the soft start */
            a->open_ms = a->short_ms = a->ireg_ms = a->cc_ms = 0;
        }
        if (a->lowbat_warning && a->state == ST_EMIT) {
            out.indicator = (a->t_state_ms / 125u) % 2u == 0u;   /* 4 Hz blink while emitting */
        }
        break;

    case ST_FAULT:
    default:
        enable = false;
        /* blink the fault code: n short blinks, then a pause (AUD-FW-13) */
        {
            uint32_t n = (uint32_t)a->fault;
            uint32_t phase = a->t_state_ms % (n * APP_BLINK_MS + APP_BLINK_PAUSE_MS);
            out.indicator = phase < n * APP_BLINK_MS && (phase % APP_BLINK_MS) < APP_BLINK_ON_MS;
        }
        break;
    }

    out.laser_enable = (a->state == ST_EMIT) && enable;
    /* CC pull-up from the second enabled tick: the TPS552882 VCC rail is up by then (AUD-FW-10) */
    out.cc_sense = out.laser_enable && a->t_enabled_ms >= APP_CC_ARM_MS - 1u;
    if (out.laser_enable) {
        a->t_disabled_ms = 0;
    }
    a->was_enabled = out.laser_enable;
    return out;
}
