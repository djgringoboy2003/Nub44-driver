#include "app.h"

static void enter(app_t *a, app_state_t s)
{
    a->state = s;
    a->t_state_ms = 0;
}

static void fail(app_t *a, app_fault_t f)
{
    if (a->state != ST_FAULT) {       /* first fault wins; latched until power is removed */
        a->fault = f;
        enter(a, ST_FAULT);
    }
}

void app_init(app_t *a, bool short_interruption, app_mode_t stored_mode)
{
    a->state = ST_BOOT;
    a->fault = FAULT_NONE;
    a->t_state_ms = 0;
    a->t_enabled_ms = 0;
    a->lowbat_ms = a->open_ms = a->short_ms = a->cc_ms = a->ireg_ms = 0;
    a->lowbat_warning = false;
    a->prev_switch = false;
    if (short_interruption && stored_mode < MODE_COUNT) {
        a->mode = (app_mode_t)((stored_mode + 1) % MODE_COUNT);
    } else {
        a->mode = MODE_CONTINUOUS;
    }
}

/* fault checks that only make sense while the converter runs */
static void check_running(app_t *a, const app_inputs_t *in)
{
    if (in->ov_trip) {
        fail(a, FAULT_OVERVOLTAGE);
        return;
    }
    if (in->cc_flag) {
        if (++a->cc_ms >= APP_CC_FLAG_MS) { fail(a, FAULT_OVERCURRENT); return; }
    } else {
        a->cc_ms = 0;
    }
    if (a->t_enabled_ms < APP_SETTLE_MS) {
        return;                         /* soft start in progress */
    }
    if (in->vout_mv > APP_OPEN_VOUT_MV && in->i_laser_ma < APP_OPEN_I_MA) {
        if (++a->open_ms >= APP_OPEN_MS) { fail(a, FAULT_OPEN_LOAD); return; }
    } else {
        a->open_ms = 0;
    }
    if (in->vout_mv < APP_SHORT_VOUT_MV) {
        if (++a->short_ms >= APP_SHORT_MS) { fail(a, FAULT_SHORT); return; }
    } else {
        a->short_ms = 0;
    }
    {
        uint32_t lo = (uint32_t)APP_I_SET_MA * (100u - APP_I_TOL_PCT) / 100u;
        uint32_t hi = (uint32_t)APP_I_SET_MA * (100u + APP_I_TOL_PCT) / 100u;
        if (in->i_laser_ma < lo || in->i_laser_ma > hi) {
            if (++a->ireg_ms >= APP_I_FAULT_MS) { fail(a, FAULT_REGULATION); return; }
        } else {
            a->ireg_ms = 0;
        }
    }
}

app_outputs_t app_tick(app_t *a, const app_inputs_t *in)
{
    app_outputs_t out = {false, false};
    bool enable = false;
    bool pressed_edge = in->switch_pressed && !a->prev_switch;
    a->prev_switch = in->switch_pressed;
    a->t_state_ms += APP_TICK_MS;

    /* conditions that apply in every non-fault state */
    if (a->state != ST_FAULT) {
        if (in->t_board_c10 != APP_T_NONE && in->t_board_c10 > APP_T_BOARD_MAX_C10) {
            fail(a, FAULT_OVERTEMP_BOARD);
        } else if (in->t_laser_c10 != APP_T_NONE && in->t_laser_c10 > APP_T_LASER_MAX_C10) {
            fail(a, FAULT_OVERTEMP_LASER);
        }
    }

    switch (a->state) {
    case ST_BOOT:
        if (in->vbat_mv < APP_VBAT_START_MIN_MV) {
            fail(a, FAULT_LOW_BATTERY_START);
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
        } else if (pressed_edge) {
            a->mode = (app_mode_t)((a->mode + 1) % MODE_COUNT);
        } else if (a->t_state_ms >= APP_EMISSION_DELAY_MS) {
            enter(a, ST_EMIT);
            a->t_enabled_ms = 0;
        }
        break;

    case ST_EMIT:
        out.indicator = true;
        if (!in->interlock_closed) {   /* hardware already disabled; require a manual reset */
            fail(a, FAULT_INTERLOCK);
            break;
        }
        if (pressed_edge) {
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
                    fail(a, FAULT_LOW_BATTERY);
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
        /* blink the fault code: n short blinks, pause */
        {
            uint32_t phase = a->t_state_ms % 3000u;
            uint32_t n = (uint32_t)a->fault;
            out.indicator = phase < n * 300u && (phase % 300u) < 150u;
        }
        break;
    }

    out.laser_enable = (a->state == ST_EMIT) && enable;
    return out;
}
