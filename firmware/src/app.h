/*
 * NUBM44 driver application logic (hardware independent, unit-tested on the host).
 *
 * Safety model: the laser current is set in hardware (FB divider) and capped in hardware (ISP/ISN
 * 4.8-5.2 A). The interlock and the over-voltage backstop disable the converter in hardware. This
 * code can only ENABLE emission when every condition below holds, and it latches faults until
 * power is removed (manual reset, as expected for Class 4 products).
 */
#ifndef APP_H
#define APP_H

#include <stdbool.h>
#include <stdint.h>

/* --- thresholds (engineering/design/parameters.yaml, DD-06/DD-08) ------------------------- */
#define APP_TICK_MS             1u
#define APP_EMISSION_DELAY_MS   2000u   /* indicator on, no emission, after every power-up */
#define APP_FLASH_PERIOD_MS     500u    /* 2 Hz */
#define APP_FLASH_ON_MS         250u    /* 50 % */
#define APP_SETTLE_MS           20u     /* 4 ms soft start + margin before regulation checks */
#define APP_VBAT_START_MIN_MV   3200u   /* refuse to start below this resting voltage */
#define APP_VBAT_WARN_MV        3100u   /* loaded: warning indication */
#define APP_VBAT_CUTOFF_MV      2900u   /* loaded: latch off */
#define APP_VBAT_CUTOFF_MS      200u
#define APP_I_SET_MA            4000u
#define APP_I_TOL_PCT           15u     /* regulation fault window (hardware accuracy is +-3.6 %) */
#define APP_I_FAULT_MS          50u
#define APP_OPEN_VOUT_MV        5000u   /* open load: VOUT high while current is low */
#define APP_OPEN_I_MA           500u
#define APP_OPEN_MS             2u
#define APP_SHORT_VOUT_MV       2000u   /* short: VOUT collapsed while current flows */
#define APP_SHORT_MS            5u
#define APP_CC_FLAG_MS          1u      /* TPS552882 backup limit active = primary loop failed */
#define APP_T_BOARD_MAX_C10     850     /* 85.0 C, tenths of a degree */
#define APP_T_LASER_MAX_C10     600     /* 60.0 C (NUBM44 case limit 65 C) */
#define APP_T_NONE              (-32768)

typedef enum {
    MODE_CONTINUOUS = 0,
    MODE_FLASH = 1,
    MODE_COUNT
} app_mode_t;

typedef enum {
    ST_BOOT = 0,
    ST_WAIT_INTERLOCK,
    ST_ARMING,
    ST_EMIT,
    ST_FAULT,
} app_state_t;

typedef enum {
    FAULT_NONE = 0,
    FAULT_LOW_BATTERY_START,
    FAULT_LOW_BATTERY,
    FAULT_INTERLOCK,
    FAULT_OPEN_LOAD,
    FAULT_SHORT,
    FAULT_OVERCURRENT,
    FAULT_REGULATION,
    FAULT_OVERTEMP_BOARD,
    FAULT_OVERTEMP_LASER,
    FAULT_OVERVOLTAGE,
} app_fault_t;

typedef struct {
    uint16_t vbat_mv;        /* VBAT at the board */
    uint16_t vout_mv;        /* converter output */
    uint16_t i_laser_ma;     /* from the INA186 (0.5 V/A) */
    int16_t t_board_c10;     /* board NTC, tenths of a degree */
    int16_t t_laser_c10;     /* external NTC or APP_T_NONE when not fitted */
    bool interlock_closed;
    bool switch_pressed;     /* debounced e-switch level */
    bool cc_flag;            /* TPS552882 CC pin: backup current limit active */
    bool ov_trip;            /* AC0 over-voltage comparator event (latched by the ISR) */
} app_inputs_t;

typedef struct {
    bool laser_enable;       /* true -> drive LASER_EN_N low (converter allowed to run) */
    bool indicator;          /* emission / status indicator output */
} app_outputs_t;

typedef struct {
    app_state_t state;
    app_fault_t fault;
    app_mode_t mode;
    uint32_t t_state_ms;     /* time in the current state */
    uint32_t t_enabled_ms;   /* time since the converter was last enabled */
    uint16_t lowbat_ms, open_ms, short_ms, cc_ms, ireg_ms;
    bool lowbat_warning;
    bool prev_switch;
} app_t;

/* Power-up. `short_interruption` is true when the hold-up logic saw a power gap short enough to
 * count as a mode change (clicky tail switch); `stored_mode` is the mode before the gap. */
void app_init(app_t *a, bool short_interruption, app_mode_t stored_mode);

/* Called every APP_TICK_MS. Pure function of state + inputs. */
app_outputs_t app_tick(app_t *a, const app_inputs_t *in);

#endif
