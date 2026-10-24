/*
 * NUBM44 driver firmware: ATtiny1616 (tinyAVR 1-series), 5 MHz (20 MHz oscillator / 4).
 * Build: see firmware/README.md (avr-gcc 15.2.0, -mmcu=attiny1616).
 *
 * Pin map (engineering/design-decisions.md DD-07; schematic U3):
 *   PA0 UPDI           PA1 LASER_EN_N (low = enable)   PA2 INTLK sense (low = closed)
 *   PA3 SW (pull-up)   PA4 NTC_PWR                     PA5 NTC board (ADC0 AIN5)
 *   PA6 CS_OUT (ADC0 AIN6, 0.5 V/A)                    PA7 VOUT/6 (AC0 AINP0, ADC1 AIN3)
 *   PB0 PG (pull-up)   PB1 CC flag (pull-up, low = backup limit active, verify on bench)
 *   PB2 IND            PB4 NTC laser (ADC0 AIN9)       PB5 VBAT/2 (ADC0 AIN8, AC2 AINP2)
 */
#include <avr/interrupt.h>
#include <avr/io.h>
#include <avr/sleep.h>
#include <stdbool.h>
#include <stdint.h>

#include "app.h"

#define F_CPU_HZ        5000000UL
#define VREF_MV         2500UL
#define OV_THRESHOLD_MV 5625UL          /* AC0: VOUT/6 vs DAC0 (2.5 V * 96 / 256 = 0.9375 V) */
#define PWR_LOSS_MV     2600UL          /* AC2: VBAT/2 below 1.3 V -> power removed */
#define SHORT_GAP_TICKS 512u            /* RTC at 1024 Hz: < 0.5 s gap = mode change */
#define NOINIT_MAGIC    0x4C44u         /* "LD" */

/* survives a software reset and short power gaps (RAM held up by C16 through D2) */
static volatile uint16_t noinit_magic __attribute__((section(".noinit")));
static volatile uint8_t noinit_mode __attribute__((section(".noinit")));
static volatile uint8_t noinit_short_gap __attribute__((section(".noinit")));

static volatile bool tick_flag;
static volatile bool ov_latched;
static volatile bool power_lost;
static app_t app;

/* ------------------------------------------------------------------------------ low level */
static inline void laser_disable_now(void) { PORTA.OUTSET = PIN1_bm; }
static inline void laser_enable_now(void) { PORTA.OUTCLR = PIN1_bm; }

static void clock_init(void)
{
    /* 20 MHz oscillator (fuse FREQSEL) divided by 4 -> 5 MHz: valid down to 1.8 V */
    _PROTECTED_WRITE(CLKCTRL.MCLKCTRLB, CLKCTRL_PDIV_4X_gc | CLKCTRL_PEN_bm);
}

static void gpio_init(void)
{
    PORTA.OUTSET = PIN1_bm;                       /* converter disabled before anything else */
    PORTA.DIRSET = PIN1_bm | PIN4_bm;
    PORTA.OUTCLR = PIN4_bm;
    PORTA.PIN3CTRL = PORT_PULLUPEN_bm;            /* e-switch */
    PORTA.PIN5CTRL = PORT_ISC_INPUT_DISABLE_gc;   /* analog pins: digital input buffer off */
    PORTA.PIN6CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTA.PIN7CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTB.PIN0CTRL = PORT_PULLUPEN_bm;            /* PG open drain */
    PORTB.PIN1CTRL = PORT_PULLUPEN_bm;            /* CC open drain */
    PORTB.PIN4CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTB.PIN5CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTB.DIRSET = PIN2_bm | PIN3_bm;             /* indicator; PB3 unused -> output low */
    PORTB.OUTCLR = PIN2_bm | PIN3_bm;
    PORTC.DIRSET = PIN0_bm | PIN1_bm | PIN2_bm | PIN3_bm;   /* unused -> output low */
    PORTC.OUTCLR = PIN0_bm | PIN1_bm | PIN2_bm | PIN3_bm;
}

static void analog_init(void)
{
    /* ADC0/ADC1 and DAC0 referenced to the internal 2.5 V reference */
    VREF.CTRLA = VREF_ADC0REFSEL_2V5_gc | VREF_DAC0REFSEL_2V5_gc;
    VREF.CTRLC = VREF_ADC1REFSEL_2V5_gc | VREF_DAC2REFSEL_2V5_gc;
    ADC0.CTRLC = ADC_PRESC_DIV16_gc | ADC_REFSEL_INTREF_gc | ADC_SAMPCAP_bm;
    ADC0.CTRLA = ADC_ENABLE_bm;
    ADC1.CTRLC = ADC_PRESC_DIV16_gc | ADC_REFSEL_INTREF_gc | ADC_SAMPCAP_bm;
    ADC1.CTRLA = ADC_ENABLE_bm;

    /* DAC0 (internal only) -> AC0 negative input: over-voltage trip on VOUT/6 */
    DAC0.DATA = (uint8_t)((OV_THRESHOLD_MV / 6UL) * 256UL / VREF_MV);
    DAC0.CTRLA = DAC_ENABLE_bm;
    AC0.MUXCTRLA = AC_MUXPOS_PIN0_gc | AC_MUXNEG_DAC_gc;     /* PA7 vs DAC0 */
    AC0.INTCTRL = AC_CMP_bm;
    AC0.CTRLA = AC_ENABLE_bm | AC_INTMODE_POSEDGE_gc | AC_HYSMODE_25mV_gc;

    /* DAC2 (internal) -> AC2 negative input: battery removal detection on VBAT/2 */
    DAC2.DATA = (uint8_t)((PWR_LOSS_MV / 2UL) * 256UL / VREF_MV);
    DAC2.CTRLA = DAC_ENABLE_bm;
    AC2.MUXCTRLA = AC_MUXPOS_PIN2_gc | AC_MUXNEG_DAC_gc;     /* PB5 vs DAC2 */
    AC2.INTCTRL = AC_CMP_bm;
    AC2.CTRLA = AC_ENABLE_bm | AC_INTMODE_NEGEDGE_gc | AC_HYSMODE_25mV_gc | AC_RUNSTDBY_bm;
}

static void timers_init(void)
{
    /* TCB0 periodic interrupt at 1 kHz */
    TCB0.CCMP = (uint16_t)(F_CPU_HZ / 1000UL - 1UL);
    TCB0.INTCTRL = TCB_CAPT_bm;
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV1_gc | TCB_ENABLE_bm;
    /* RTC from the 32 kHz ULP oscillator / 32 = 1024 Hz, used to time power gaps */
    while (RTC.STATUS) {}
    RTC.CLKSEL = RTC_CLKSEL_INT32K_gc;
    RTC.PER = 0xFFFF;
    RTC.CTRLA = RTC_PRESCALER_DIV32_gc | RTC_RUNSTDBY_bm | RTC_RTCEN_bm;
    /* watchdog: 64 ms */
    _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_64CLK_gc);
}

static uint16_t adc_read(ADC_t *adc, uint8_t muxpos, bool vdd_ref)
{
    adc->CTRLC = (uint8_t)((adc->CTRLC & ~ADC_REFSEL_gm) | (vdd_ref ? ADC_REFSEL_VDDREF_gc : ADC_REFSEL_INTREF_gc));
    adc->MUXPOS = muxpos;
    adc->COMMAND = ADC_STCONV_bm;
    while (!(adc->INTFLAGS & ADC_RESRDY_bm)) {}
    adc->INTFLAGS = ADC_RESRDY_bm;
    return adc->RES;                              /* 10-bit */
}

static uint16_t to_mv(uint16_t raw, uint16_t scale)    /* scale = divider ratio */
{
    return (uint16_t)(((uint32_t)raw * VREF_MV * scale) / 1023UL);
}

/* 10k NTC (B 3380) against 10k to NTC_PWR, ratiometric -> tenths of a degree (piecewise linear).
 * Table from R(T) = 10k * exp(3380 * (1/T - 1/298.15)), raw = 1023 * R / (R + 10k). */
static int16_t ntc_c10(uint16_t raw)
{
    static const uint16_t tab_raw[] = {903, 838, 755, 661, 512, 376, 268, 189, 133, 95, 69};
    static const int16_t tab_t[] = {-200, -100, 0, 100, 250, 400, 550, 700, 850, 1000, 1150};
    if (raw >= 1015 || raw <= 8) {
        return APP_T_NONE;                        /* open or shorted sensor */
    }
    for (uint8_t i = 0; (uint8_t)(i + 1u) < (uint8_t)(sizeof(tab_raw) / sizeof(tab_raw[0])); i++) {
        if (raw <= tab_raw[i] && raw >= tab_raw[i + 1]) {
            int32_t span = (int32_t)tab_raw[i] - tab_raw[i + 1];
            return (int16_t)(tab_t[i] + (int32_t)(tab_t[i + 1] - tab_t[i]) * (tab_raw[i] - raw) / span);
        }
    }
    return raw > tab_raw[0] ? tab_t[0] : tab_t[10];
}

/* ------------------------------------------------------------------------------ interrupts */
ISR(TCB0_INT_vect)
{
    TCB0.INTFLAGS = TCB_CAPT_bm;
    tick_flag = true;
}

ISR(AC0_AC_vect)                                  /* VOUT over-voltage: stop now, latch */
{
    laser_disable_now();
    AC0.STATUS = AC_CMP_bm;
    ov_latched = true;
}

ISR(AC2_AC_vect)                                  /* battery removed (clicky switch) */
{
    laser_disable_now();
    AC2.STATUS = AC_CMP_bm;
    power_lost = true;
}

/* Hold-up: sleep on the C16 charge while the battery is gone, timing the gap with the RTC. */
static void handle_power_loss(void)
{
    uint16_t t0 = RTC.CNT;
    PORTA.OUTCLR = PIN4_bm;                       /* NTC bias off */
    PORTB.OUTCLR = PIN2_bm;                       /* indicator off */
    PORTB.PIN0CTRL = 0;                           /* drop pull-ups into the unpowered converter */
    PORTB.PIN1CTRL = 0;
    PORTA.PIN3CTRL = 0;
    AC0.CTRLA = 0;
    ADC0.CTRLA = 0;
    ADC1.CTRLA = 0;
    AC2.CTRLA = (uint8_t)((AC2.CTRLA & ~AC_INTMODE_gm) | AC_INTMODE_POSEDGE_gc);   /* wake on return */
    _PROTECTED_WRITE(WDT.CTRLA, 0);
    SLPCTRL.CTRLA = SLPCTRL_SMODE_STDBY_gc | SLPCTRL_SEN_bm;
    power_lost = false;
    while (!power_lost) {
        sleep_cpu();                              /* AC2 rising edge sets power_lost again */
    }
    uint16_t gap = (uint16_t)(RTC.CNT - t0);
    noinit_short_gap = gap < SHORT_GAP_TICKS;
    noinit_mode = (uint8_t)app.mode;
    noinit_magic = NOINIT_MAGIC;
    _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm); /* restart cleanly with the new mode */
}

/* ------------------------------------------------------------------------------ main */
int main(void)
{
    uint8_t reset_flags = RSTCTRL.RSTFR;
    RSTCTRL.RSTFR = reset_flags;
    gpio_init();
    clock_init();
    bool short_gap = (reset_flags & RSTCTRL_SWRF_bm) && noinit_magic == NOINIT_MAGIC && noinit_short_gap;
    app_mode_t stored = (app_mode_t)(noinit_magic == NOINIT_MAGIC ? noinit_mode : 0);
    noinit_magic = 0;
    app_init(&app, short_gap, stored);
    analog_init();
    timers_init();
    sei();

    for (;;) {
        __asm__ __volatile__("wdr");
        if (power_lost) {
            handle_power_loss();
        }
        if (!tick_flag) {
            continue;
        }
        tick_flag = false;

        app_inputs_t in;
        in.vbat_mv = to_mv(adc_read(&ADC0, ADC_MUXPOS_AIN8_gc, false), 2);
        in.vout_mv = to_mv(adc_read(&ADC1, ADC_MUXPOS_AIN3_gc, false), 6);
        in.i_laser_ma = (uint16_t)(((uint32_t)adc_read(&ADC0, ADC_MUXPOS_AIN6_gc, false) * VREF_MV * 2UL) / 1023UL);
        PORTA.OUTSET = PIN4_bm;                   /* NTC bias on only while sampling */
        in.t_board_c10 = ntc_c10(adc_read(&ADC0, ADC_MUXPOS_AIN5_gc, true));
        in.t_laser_c10 = ntc_c10(adc_read(&ADC0, ADC_MUXPOS_AIN9_gc, true));
        PORTA.OUTCLR = PIN4_bm;
        in.interlock_closed = !(PORTA.IN & PIN2_bm);
        in.switch_pressed = !(PORTA.IN & PIN3_bm);
        in.cc_flag = !(PORTB.IN & PIN1_bm);
        in.ov_trip = ov_latched;

        app_outputs_t out = app_tick(&app, &in);
        if (out.laser_enable && !ov_latched) {
            laser_enable_now();
        } else {
            laser_disable_now();
        }
        if (out.indicator) {
            PORTB.OUTSET = PIN2_bm;
        } else {
            PORTB.OUTCLR = PIN2_bm;
        }
    }
}
