/*
 * ATtiny1616 implementation of hal.h: tinyAVR 1-series, 5 MHz (20 MHz oscillator / 4).
 *
 * Pin map (engineering/design-decisions.md DD-07; schematic U3):
 *   PA0 UPDI           PA1 LASER_EN_N (low = enable)   PA2 INTLK sense (low = closed)
 *   PA3 SW (pull-up)   PA4 NTC_PWR                     PA5 NTC board (ADC0 AIN5)
 *   PA6 CS_OUT (ADC0 AIN6, 0.5 V/A)                    PA7 VOUT/6 (AC0 AINP0, ADC1 AIN3)
 *   PB0 PG (unused)    PB1 CC flag (low = backup limit active, verify on bench: T1.10)
 *   PB2 IND            PB4 NTC laser (ADC0 AIN9)       PB5 VBAT/2 (ADC0 AIN8, AC2 AINP2)
 *
 * References (audit AUD-FW-04/05/19/20, DS40001997C): ADC0 always uses VDD and measures the 1.1 V
 * reference as an input; ADC1, DAC0 and DAC2 use the 1.5 V reference (specified down to VDD 1.9 V).
 * VREF.CTRLD (not CTRLC) holds the DAC2 reference; DAC2 must run in standby for the hold-up wake-up.
 *
 * The HAL_* macros below are the only seams used by the host register-model test
 * (firmware/tests/test_hal.c); on the target they are plain register accesses.
 */
#include <avr/interrupt.h>
#include <avr/io.h>
#include <avr/sleep.h>

#include "conv.h"
#include "fuses.h"
#include "hal.h"

#ifndef HAL_PORT_SET
#define HAL_PORT_SET(port, mask)    ((port).OUTSET = (mask))
#define HAL_PORT_CLR(port, mask)    ((port).OUTCLR = (mask))
#define HAL_PORT_DIR(port, mask)    ((port).DIRSET = (mask))
#endif
#ifndef HAL_ADC_CONVERT
#define HAL_ADC_CONVERT(adc) do { (adc)->COMMAND = ADC_STCONV_bm; \
        while (!((adc)->INTFLAGS & ADC_RESRDY_bm)) {} } while (0)
#endif
#ifndef HAL_WDR
#define HAL_WDR()                   __asm__ __volatile__("wdr")
#endif

#define F_CPU_HZ        5000000UL
#define OV_THRESHOLD_MV 5625UL          /* AC0: VOUT/6 vs DAC0 -> 0.9375 V at the pin (DD-05) */
#define PWR_LOSS_MV     2600UL          /* AC2: VBAT/2 vs DAC2 -> 1.3 V at the pin */
#define OV_DAC_CODE     CONV_DAC_CODE(OV_THRESHOLD_MV / CONV_VOUT_DIV)
#define PWR_DAC_CODE    CONV_DAC_CODE(PWR_LOSS_MV / CONV_VBAT_DIV)

static volatile uint8_t ticks_pending;
static volatile bool ov_latched;
static volatile bool power_lost;
static volatile uint16_t rtc_overflows;
static bool guard_on;
static hal_noinit_t noinit __attribute__((section(".noinit")));

static inline void laser_disable_now(void) { HAL_PORT_SET(PORTA, PIN1_bm); }

static void wdt_write(uint8_t ctrla)
{
    while (WDT.STATUS & WDT_SYNCBUSY_bm) {}
    _PROTECTED_WRITE(WDT.CTRLA, ctrla);
}

static void gpio_init(void)
{
    HAL_PORT_SET(PORTA, PIN1_bm);                 /* converter disabled before anything else */
    HAL_PORT_DIR(PORTA, PIN1_bm | PIN4_bm);
    HAL_PORT_CLR(PORTA, PIN4_bm);
    PORTA.PIN3CTRL = PORT_PULLUPEN_bm;            /* e-switch */
    PORTA.PIN5CTRL = PORT_ISC_INPUT_DISABLE_gc;   /* analog pins: digital input buffer off */
    PORTA.PIN6CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTA.PIN7CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTB.PIN0CTRL = PORT_ISC_INPUT_DISABLE_gc;   /* PG: unused, no pull-up into the converter (AUD-FW-10) */
    PORTB.PIN1CTRL = PORT_ISC_INPUT_DISABLE_gc;   /* CC: pull-up only while the converter runs */
    PORTB.PIN4CTRL = PORT_ISC_INPUT_DISABLE_gc;
    PORTB.PIN5CTRL = PORT_ISC_INPUT_DISABLE_gc;
    HAL_PORT_DIR(PORTB, PIN2_bm | PIN3_bm);       /* indicator; PB3 unused -> output low */
    HAL_PORT_CLR(PORTB, PIN2_bm | PIN3_bm);
    HAL_PORT_DIR(PORTC, PIN0_bm | PIN1_bm | PIN2_bm | PIN3_bm);   /* unused -> output low */
    HAL_PORT_CLR(PORTC, PIN0_bm | PIN1_bm | PIN2_bm | PIN3_bm);
}

static void clock_init(void)
{
    /* 20 MHz oscillator (fuse FREQSEL) divided by 4 -> 5 MHz: valid down to 1.8 V */
    _PROTECTED_WRITE(CLKCTRL.MCLKCTRLB, CLKCTRL_PDIV_4X_gc | CLKCTRL_PEN_bm);
}

static void analog_init(void)
{
    VREF.CTRLA = VREF_ADC0REFSEL_1V1_gc | VREF_DAC0REFSEL_1V5_gc;
    VREF.CTRLB = VREF_ADC0REFEN_bm;               /* keep 1.1 V running: it is an ADC0 input every tick */
    VREF.CTRLC = VREF_ADC1REFSEL_1V5_gc;
    VREF.CTRLD = VREF_DAC2REFSEL_1V5_gc;
    ADC0.CTRLC = ADC_PRESC_DIV16_gc | ADC_REFSEL_VDDREF_gc | ADC_SAMPCAP_bm;
    ADC0.CTRLD = ADC_INITDLY_DLY64_gc;
    ADC0.SAMPCTRL = 2;
    ADC0.CTRLA = ADC_ENABLE_bm;
    ADC1.CTRLC = ADC_PRESC_DIV16_gc | ADC_REFSEL_INTREF_gc | ADC_SAMPCAP_bm;
    ADC1.CTRLD = ADC_INITDLY_DLY64_gc;
    ADC1.SAMPCTRL = 2;
    ADC1.MUXPOS = ADC_MUXPOS_AIN3_gc;
    ADC1.CTRLA = ADC_ENABLE_bm;

    /* DAC0 (internal only) -> AC0 negative input: over-voltage trip on VOUT/6 */
    DAC0.DATA = OV_DAC_CODE;
    DAC0.CTRLA = DAC_ENABLE_bm;
    AC0.MUXCTRLA = AC_MUXPOS_PIN0_gc | AC_MUXNEG_DAC_gc;     /* PA7 vs DAC0 */
    AC0.INTCTRL = AC_CMP_bm;
    AC0.CTRLA = AC_ENABLE_bm | AC_INTMODE_POSEDGE_gc | AC_HYSMODE_25mV_gc;

    /* DAC2 (internal) -> AC2 negative input: battery removal detection on VBAT/2 */
    DAC2.DATA = PWR_DAC_CODE;
    DAC2.CTRLA = DAC_ENABLE_bm | DAC_RUNSTDBY_bm;
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
    RTC.INTCTRL = RTC_OVF_bm;                     /* extends the counter to 32 bits */
    RTC.CTRLA = RTC_PRESCALER_DIV32_gc | RTC_RUNSTDBY_bm | RTC_RTCEN_bm;
    /* watchdog: 64 ms, cleared only after a complete supervision cycle (AUD-FW-03) */
    wdt_write(WDT_PERIOD_64CLK_gc);
}

void hal_init(void)
{
    gpio_init();
    clock_init();
    analog_init();
    timers_init();
}

uint8_t hal_reset_cause(void)
{
    uint8_t f = RSTCTRL.RSTFR;
    uint8_t c = 0;
    RSTCTRL.RSTFR = f;
    if (f & RSTCTRL_PORF_bm) c |= HAL_RST_POWER_ON;
    if (f & RSTCTRL_BORF_bm) c |= HAL_RST_BROWN_OUT;
    if (f & RSTCTRL_EXTRF_bm) c |= HAL_RST_EXTERNAL;
    if (f & RSTCTRL_WDRF_bm) c |= HAL_RST_WATCHDOG;
    if (f & RSTCTRL_SWRF_bm) c |= HAL_RST_SOFTWARE;
    if (f & RSTCTRL_UPDIRF_bm) c |= HAL_RST_UPDI;
    return c;
}

bool hal_config_ok(void)
{
    return FUSE.BODCFG == FW_FUSE_BODCFG && (FUSE.OSCCFG & FW_FUSE_OSCCFG_MASK) == FW_FUSE_OSCCFG;
}

void hal_interrupts_on(void)
{
    sei();
}

hal_noinit_t *hal_noinit(void)
{
    return &noinit;
}

uint8_t hal_ticks_take(void)
{
    uint8_t n;
    cli();
    n = ticks_pending;
    ticks_pending = 0;
    sei();
    return n;
}

static uint16_t adc_read(ADC_t *adc, uint8_t muxpos)
{
    adc->MUXPOS = muxpos;
    HAL_ADC_CONVERT(adc);
    adc->INTFLAGS = ADC_RESRDY_bm;
    return adc->RES;                              /* 10-bit */
}

void hal_sample(hal_sample_t *s)
{
    (void)adc_read(&ADC0, ADC_MUXPOS_INTREF_gc);  /* settle the sample capacitor on the reference */
    s->ref = adc_read(&ADC0, ADC_MUXPOS_INTREF_gc);
    s->vbat = adc_read(&ADC0, ADC_MUXPOS_AIN8_gc);
    s->cs = adc_read(&ADC0, ADC_MUXPOS_AIN6_gc);
    HAL_PORT_SET(PORTA, PIN4_bm);                 /* NTC bias on only while sampling */
    s->ntc_board = adc_read(&ADC0, ADC_MUXPOS_AIN5_gc);
    s->ntc_laser = adc_read(&ADC0, ADC_MUXPOS_AIN9_gc);
    HAL_PORT_CLR(PORTA, PIN4_bm);
    s->vout = adc_read(&ADC1, ADC_MUXPOS_AIN3_gc);
    s->interlock_closed = !(PORTA.IN & PIN2_bm);
    s->switch_closed = !(PORTA.IN & PIN3_bm);
    s->cc_active = !(PORTB.IN & PIN1_bm);
}

void hal_outputs(bool laser_enable, bool indicator, bool cc_sense)
{
    if (laser_enable && !ov_latched) {
        PORTB.PIN1CTRL = cc_sense ? PORT_PULLUPEN_bm : PORT_ISC_INPUT_DISABLE_gc;
        HAL_PORT_CLR(PORTA, PIN1_bm);
    } else {
        laser_disable_now();
        PORTB.PIN1CTRL = PORT_ISC_INPUT_DISABLE_gc;
    }
    if (indicator) {
        HAL_PORT_SET(PORTB, PIN2_bm);
    } else {
        HAL_PORT_CLR(PORTB, PIN2_bm);
    }
}

void hal_wdt_clear(void)
{
    HAL_WDR();
}

bool hal_ov_latched(void)
{
    return ov_latched;
}

bool hal_power_lost(void)
{
    return power_lost;
}

void hal_holdup_enter(void)
{
    laser_disable_now();
    HAL_PORT_CLR(PORTA, PIN4_bm);                 /* NTC bias off */
    HAL_PORT_CLR(PORTB, PIN2_bm);                 /* indicator off */
    PORTB.PIN1CTRL = PORT_ISC_INPUT_DISABLE_gc;   /* no pull-ups into the unpowered converter or switch */
    PORTA.PIN3CTRL = PORT_ISC_INPUT_DISABLE_gc;
    AC0.CTRLA = 0;
    ADC0.CTRLA = 0;
    ADC1.CTRLA = 0;
    VREF.CTRLB = 0;                               /* release the forced 1.1 V reference */
    wdt_write(0);
    guard_on = false;
    AC2.CTRLA = (uint8_t)((AC2.CTRLA & ~AC_INTMODE_gm) | AC_INTMODE_BOTHEDGE_gc);   /* wake on return */
    SLPCTRL.CTRLA = SLPCTRL_SMODE_STDBY_gc | SLPCTRL_SEN_bm;
}

bool hal_supply_present(void)
{
    return (AC2.STATUS & AC_STATE_bm) != 0;
}

uint32_t hal_rtc_ticks(void)
{
    uint8_t sreg = SREG;
    uint16_t lo, hi;
    cli();
    lo = RTC.CNT;
    hi = rtc_overflows;
    if ((RTC.INTFLAGS & RTC_OVF_bm) && lo < 0x8000u) {
        hi++;                                     /* overflow pending, not yet counted by the ISR */
    }
    SREG = sreg;
    return ((uint32_t)hi << 16) | lo;
}

void hal_holdup_guard(bool on)
{
    if (on != guard_on) {
        wdt_write(on ? WDT_PERIOD_1KCLK_gc : 0);
        guard_on = on;
    }
}

void hal_holdup_sleep(void)
{
    cli();
    if (!(AC2.STATUS & AC_STATE_bm)) {
        sei();
        sleep_cpu();                              /* sei + sleep: a pending wake-up cannot be lost */
    }
    sei();
}

void hal_restart(void)
{
    _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
    for (;;) {
    }
}

/* ------------------------------------------------------------------------------ interrupts */
ISR(TCB0_INT_vect)
{
    TCB0.INTFLAGS = TCB_CAPT_bm;
    if (ticks_pending < 255u) {
        ticks_pending++;
    }
}

ISR(AC0_AC_vect)                                  /* VOUT over-voltage: stop now, latch */
{
    laser_disable_now();
    AC0.STATUS = AC_CMP_bm;
    ov_latched = true;
}

ISR(AC2_AC_vect)                                  /* battery removed (clicky switch) or returned */
{
    laser_disable_now();
    AC2.STATUS = AC_CMP_bm;
    power_lost = true;
}

ISR(RTC_CNT_vect)
{
    RTC.INTFLAGS = RTC_OVF_bm;
    rtc_overflows++;
}
