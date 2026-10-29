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

#include "conv.h"

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
#define APP_I_SET_MA            4500u   /* DD-36: 4.5 A setpoint (was 4.0 A) */
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
#define APP_T_NONE              CONV_T_NONE

/* --- supervision timing (DD-28, audit 2026-10-26). These add checks; none relaxes a threshold above. */
#define APP_BOOT_MS             20u     /* settle the inputs before deciding (sensor presence, start voltage) */
#define APP_SENSOR_FAULT_MS     50u     /* an invalid NTC reading must persist this long to latch */
#define APP_MEAS_FAULT_MS       10u     /* an invalid reference measurement must persist this long */
#define APP_SW_DEBOUNCE_MS      20u     /* switch level must be stable this long */
#define APP_SW_LOCKOUT_MS       250u    /* minimum time between accepted presses */
#define APP_CC_ARM_MS           3u      /* CC pull-up settles after enable before the flag is read */
#define APP_OFF_BLANK_MS        10u     /* turn-off decay allowed before checking for current while off */
#define APP_OFF_I_MA            200u    /* current above this while disabled = enable path failed */
#define APP_OFF_MS              20u
#define APP_BLINK_MS            300u    /* fault code: n blinks of 150 ms in 300 ms slots, then a pause */
#define APP_BLINK_ON_MS         150u
#define APP_BLINK_PAUSE_MS      1500u

/* Optional external laser NTC (TP10). 0: absent at power-up is accepted and ignored for that session
 * (a fitted sensor that later opens or shorts latches FAULT_SENSOR_LASER). 1: the sensor is mandatory. */
#ifndef APP_LASER_NTC_REQUIRED
#define APP_LASER_NTC_REQUIRED  0
#endif

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

/* The number is the blink code; existing codes keep their numbers. */
typedef enum {
    FAULT_NONE = 0,
    FAULT_LOW_BATTERY_START,    /* 1: resting voltage below 3.2 V at power-up or at the end of arming */
    FAULT_LOW_BATTERY,          /* 2 */
    FAULT_INTERLOCK,            /* 3 */
    FAULT_OPEN_LOAD,            /* 4 */
    FAULT_SHORT,                /* 5 */
    FAULT_OVERCURRENT,          /* 6: TPS552882 CC flag (backup limit) */
    FAULT_REGULATION,           /* 7 */
    FAULT_OVERTEMP_BOARD,       /* 8 */
    FAULT_OVERTEMP_LASER,       /* 9 */
    FAULT_OVERVOLTAGE,          /* 10 */
    FAULT_SENSOR_BOARD,         /* 11: board NTC open or shorted (mandatory sensor) */
    FAULT_SENSOR_LASER,         /* 12: laser NTC shorted, or failed after being present at power-up */
    FAULT_OUTPUT_WHILE_OFF,     /* 13: laser current while the firmware holds the converter off */
    FAULT_INTERNAL,             /* 14: watchdog/unexpected reset, tick overrun, reference measurement */
    FAULT_CONFIG,               /* 15: fuses differ from firmware/src/fuses.h */
} app_fault_t;

typedef enum {
    DETAIL_NONE = 0,
    DETAIL_WATCHDOG_RESET = 1,
    DETAIL_UNEXPECTED_RESET = 2,
    DETAIL_TICK_OVERRUN = 3,
    DETAIL_MEASUREMENT = 4,
    DETAIL_ARMING_RECHECK = 5,  /* FAULT_LOW_BATTERY_START raised at the end of arming */
} app_detail_t;

typedef enum {
    APP_START_FRESH = 0,        /* power-up or long gap: continuous mode */
    APP_START_KEEP_MODE = 1,    /* glitch: restart in the stored mode */
    APP_START_NEXT_MODE = 2,    /* short power interruption (clicky switch): next mode */
} app_start_t;

typedef enum {
    LASER_NTC_UNKNOWN = 0,      /* decided at the end of ST_BOOT */
    LASER_NTC_ABSENT,
    LASER_NTC_FITTED,
} app_laser_ntc_t;

typedef struct {
    uint16_t vbat_mv;           /* VBAT at the board */
    uint16_t vout_mv;           /* converter output */
    uint16_t i_laser_ma;        /* from the INA186 (0.5 V/A) */
    int16_t t_board_c10;        /* board NTC, tenths of a degree (valid when the status is SENSOR_OK) */
    int16_t t_laser_c10;        /* external NTC (valid when the status is SENSOR_OK) */
    sensor_status_t t_board_status;
    sensor_status_t t_laser_status;
    bool meas_valid;            /* reference measurement plausible: vbat_mv and i_laser_ma are meaningful */
    bool interlock_closed;
    bool switch_closed;         /* raw e-switch level; debounced by app_tick() */
    bool cc_flag;               /* TPS552882 CC pin active; meaningful only while the converter runs */
    bool ov_trip;               /* AC0 over-voltage comparator event (latched by the ISR) */
} app_inputs_t;

typedef struct {
    bool laser_enable;          /* true -> drive LASER_EN_N low (converter allowed to run) */
    bool indicator;             /* emission / status indicator output */
    bool cc_sense;              /* true -> enable the CC pull-up (only while the converter runs) */
} app_outputs_t;

typedef struct {
    app_state_t state;
    app_fault_t fault;
    uint8_t fault_detail;       /* app_detail_t or the sensor_status_t of a sensor fault */
    app_mode_t mode;
    app_laser_ntc_t laser_ntc;
    uint32_t t_state_ms;        /* time in the current state */
    uint32_t t_enabled_ms;      /* time since the converter was last enabled */
    uint32_t t_disabled_ms;     /* time since the converter was last disabled */
    uint16_t lowbat_ms, open_ms, short_ms, cc_ms, ireg_ms;
    uint16_t sens_board_ms, sens_laser_ms, meas_ms, offcur_ms;
    uint16_t sw_stable_ms, sw_lockout_ms;
    bool sw_raw;                /* last raw switch sample */
    bool sw_armed;              /* a debounced release was seen: the next debounced press counts */
    bool lowbat_warning;
    bool was_enabled;           /* converter enable output of the previous tick */
} app_t;

/* Power-up. `start` comes from the hold-up logic (clicky tail switch); `stored_mode` is the mode before
 * the gap. */
void app_init(app_t *a, app_start_t start, app_mode_t stored_mode);

/* Called every APP_TICK_MS. Pure function of state + inputs. */
app_outputs_t app_tick(app_t *a, const app_inputs_t *in);

/* Latch a fault detected outside the state machine (reset cause, scheduler). First fault wins. */
void app_force_fault(app_t *a, app_fault_t f, uint8_t detail);

#endif
