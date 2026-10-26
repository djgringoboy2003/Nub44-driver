#include "fw.h"

#include "conv.h"
#include "holdup.h"

static app_t app;

static uint8_t noinit_check(const hal_noinit_t *n)
{
    return (uint8_t)~(n->mode ^ n->start ^ n->fault ^ (uint8_t)n->magic ^ (uint8_t)(n->magic >> 8));
}

const app_t *fw_app(void)
{
    return &app;
}

void fw_init(void)
{
    hal_noinit_t *ni = hal_noinit();
    app_start_t start = APP_START_FRESH;
    app_mode_t mode = MODE_CONTINUOUS;
    uint8_t kept_fault = FAULT_NONE;
    uint8_t cause;
    bool holdup_restart;

    hal_init();                                   /* converter disabled before anything else */
    cause = hal_reset_cause();
    holdup_restart = (cause & HAL_RST_SOFTWARE) && ni->magic == FW_NOINIT_MAGIC
                     && ni->check == noinit_check(ni) && ni->start <= APP_START_NEXT_MODE;
    if (holdup_restart) {
        start = (app_start_t)ni->start;
        mode = (app_mode_t)ni->mode;
        kept_fault = ni->fault;
    }
    ni->magic = 0;
    app_init(&app, start, mode);

    if (cause & HAL_RST_WATCHDOG) {               /* AUD-FW-07: a hang never re-arms emission by itself */
        app_force_fault(&app, FAULT_INTERNAL, DETAIL_WATCHDOG_RESET);
    } else if ((cause & HAL_RST_SOFTWARE) && !holdup_restart) {
        app_force_fault(&app, FAULT_INTERNAL, DETAIL_UNEXPECTED_RESET);
    } else if (kept_fault != FAULT_NONE && start == APP_START_KEEP_MODE) {
        app_force_fault(&app, (app_fault_t)kept_fault, DETAIL_NONE);   /* a glitch is not a manual reset */
    }
    if (!hal_config_ok()) {
        app_force_fault(&app, FAULT_CONFIG, DETAIL_NONE);
    }
    hal_interrupts_on();
}

app_inputs_t fw_inputs_from(const hal_sample_t *s, bool ov_latched)
{
    app_inputs_t in;
    in.meas_valid = conv_ref_valid(s->ref);
    in.vbat_mv = conv_vbat_mv(s->vbat, s->ref);
    in.i_laser_ma = conv_laser_ma(s->cs, s->ref);
    in.vout_mv = conv_vout_mv(s->vout);
    in.t_board_status = conv_ntc(s->ntc_board, &in.t_board_c10);
    in.t_laser_status = conv_ntc(s->ntc_laser, &in.t_laser_c10);
    in.interlock_closed = s->interlock_closed;
    in.switch_closed = s->switch_closed;
    in.cc_flag = s->cc_active;
    in.ov_trip = ov_latched;
    return in;
}

/* Sleep on the C16 charge while the battery is gone; restart once it has been back for a debounce time. */
static void holdup(void)
{
    hal_noinit_t *ni = hal_noinit();
    holdup_t h;
    holdup_action_t act;
    app_start_t start;

    hal_holdup_enter();
    holdup_begin(&h, hal_rtc_ticks());
    for (;;) {
        act = holdup_step(&h, hal_rtc_ticks(), hal_supply_present());
        if (act == HOLDUP_RESTART) {
            break;
        }
        if (act == HOLDUP_SLEEP) {
            hal_holdup_guard(false);
            hal_holdup_sleep();
        } else {
            hal_holdup_guard(true);               /* polling with the supply present: 1 s watchdog */
        }
    }
    switch (holdup_classify(&h)) {
    case GAP_GLITCH:
        start = APP_START_KEEP_MODE;
        break;
    case GAP_CLICK:
        start = APP_START_NEXT_MODE;
        break;
    default:
        start = APP_START_FRESH;
        break;
    }
    ni->mode = (uint8_t)app.mode;
    ni->start = (uint8_t)start;
    ni->fault = (uint8_t)(app.state == ST_FAULT ? app.fault : FAULT_NONE);
    ni->magic = FW_NOINIT_MAGIC;
    ni->check = noinit_check(ni);
    hal_restart();
}

void fw_poll(void)
{
    hal_sample_t s;
    app_inputs_t in;
    app_outputs_t out = {false, false, false};
    uint8_t n;

    if (hal_power_lost()) {
        holdup();
        return;                                   /* only reached on the host mock */
    }
    n = hal_ticks_take();
    if (n == 0u) {
        return;                                   /* no tick: the watchdog is NOT cleared (AUD-FW-03) */
    }
    if (n > FW_MAX_TICK_BACKLOG) {
        app_force_fault(&app, FAULT_INTERNAL, DETAIL_TICK_OVERRUN);
    }
    hal_sample(&s);
    in = fw_inputs_from(&s, hal_ov_latched());
    while (n-- > 0u) {                            /* keep application time equal to real time */
        out = app_tick(&app, &in);
    }
    hal_outputs(out.laser_enable && !hal_ov_latched(), out.indicator, out.cc_sense);
    hal_wdt_clear();                              /* only after a complete supervision cycle */
}
