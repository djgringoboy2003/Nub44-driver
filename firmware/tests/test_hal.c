/*
 * Register-model test of firmware/src/hal_avr.c on the host (audit AUD-FW-17).
 * Compiled with -Ifirmware/tests/mock so <avr/io.h> resolves to the register model; constants are checked
 * against the real avr-libc header by tests/test_firmware_mock_header.py.
 */
#include <string.h>

#include <avr/interrupt.h>
#include <avr/io.h>

#include "../src/conv.h"
#include "../src/fuses.h"
#include "../src/hal.h"
#include "check.h"

PORT_t PORTA, PORTB, PORTC;
VREF_t VREF;
ADC_t ADC0, ADC1;
DAC_t DAC0, DAC2;
AC_t AC0, AC2;
TCB_t TCB0;
RTC_t RTC;
WDT_t WDT;
SLPCTRL_t SLPCTRL;
RSTCTRL_t RSTCTRL;
CLKCTRL_t CLKCTRL;
FUSE_t FUSE;
volatile uint8_t SREG;
bool mock_irq_enabled;

void mock_isr_tcb0(void);
void mock_isr_ac0(void);
void mock_isr_ac2(void);
void mock_isr_rtc(void);

/* ------------------------------------------------------------------ seams */
typedef struct { char port; char op; uint8_t mask; } port_op_t;
static port_op_t ops[64];
static unsigned n_ops, wdr_count, sleeps;
static bool irq_at_sleep;

typedef struct { uint8_t mux; uint8_t refsel; bool bias; bool adc1; } conv_t;
static conv_t convs[32];
static unsigned n_convs;
static uint16_t adc0_value[32], adc1_value[32];

static char port_name(PORT_t *p) { return p == &PORTA ? 'A' : p == &PORTB ? 'B' : 'C'; }
static void log_op(PORT_t *p, char op, uint8_t mask)
{
    if (n_ops < 64u) { ops[n_ops].port = port_name(p); ops[n_ops].op = op; ops[n_ops].mask = mask; n_ops++; }
}
void mock_port_set(PORT_t *p, uint8_t mask) { p->OUT |= mask; log_op(p, 'S', mask); }
void mock_port_clr(PORT_t *p, uint8_t mask) { p->OUT &= (uint8_t)~mask; log_op(p, 'C', mask); }
void mock_port_dir(PORT_t *p, uint8_t mask) { p->DIR |= mask; log_op(p, 'D', mask); }
void mock_wdr(void) { wdr_count++; }
void mock_sleep_cpu(void) { sleeps++; irq_at_sleep = mock_irq_enabled; }
void mock_adc_convert(ADC_t *adc)
{
    bool is1 = adc == &ADC1;
    if (n_convs < 32u) {
        convs[n_convs].mux = adc->MUXPOS;
        convs[n_convs].refsel = adc->CTRLC & ADC_REFSEL_gm;
        convs[n_convs].bias = (PORTA.OUT & PIN4_bm) != 0;
        convs[n_convs].adc1 = is1;
        n_convs++;
    }
    adc->RES = is1 ? adc1_value[adc->MUXPOS & 31u] : adc0_value[adc->MUXPOS & 31u];
    adc->INTFLAGS |= ADC_RESRDY_bm;
}

static void reset_model(void)
{
    memset(&PORTA, 0, sizeof PORTA); memset(&PORTB, 0, sizeof PORTB); memset(&PORTC, 0, sizeof PORTC);
    memset(&VREF, 0, sizeof VREF); memset(&ADC0, 0, sizeof ADC0); memset(&ADC1, 0, sizeof ADC1);
    memset(&DAC0, 0, sizeof DAC0); memset(&DAC2, 0, sizeof DAC2); memset(&AC0, 0, sizeof AC0);
    memset(&AC2, 0, sizeof AC2); memset(&TCB0, 0, sizeof TCB0); memset(&RTC, 0, sizeof RTC);
    memset(&WDT, 0, sizeof WDT); memset(&SLPCTRL, 0, sizeof SLPCTRL);
    n_ops = n_convs = wdr_count = sleeps = 0;
    mock_irq_enabled = false;
}

static int find_op(char port, char op, uint8_t mask)
{
    for (unsigned i = 0; i < n_ops; i++) {
        if (ops[i].port == port && ops[i].op == op && (ops[i].mask & mask)) return (int)i;
    }
    return -1;
}

/* ------------------------------------------------------------------ tests */
static void test_init_order_and_pins(void)
{
    reset_model();
    hal_init();
    CHECK(n_ops > 0 && ops[0].port == 'A' && ops[0].op == 'S' && (ops[0].mask & PIN1_bm),
          "first action: LASER_EN_N high (converter disabled)");
    CHECK(find_op('A', 'D', PIN1_bm) > find_op('A', 'S', PIN1_bm), "PA1 driven high before it becomes an output");
    CHECK((PORTA.OUT & PIN1_bm) && (PORTA.DIR & PIN1_bm), "laser disabled and driven after init");
    CHECK(!(PORTA.OUT & PIN4_bm) && (PORTA.DIR & PIN4_bm), "NTC bias off");
    CHECK(PORTA.PIN3CTRL == PORT_PULLUPEN_bm, "switch pull-up");
    CHECK(PORTB.PIN1CTRL == PORT_ISC_INPUT_DISABLE_gc, "CC: no pull-up while the converter is off (AUD-FW-10)");
    CHECK(PORTB.PIN0CTRL == PORT_ISC_INPUT_DISABLE_gc, "PG: no pull-up, unused");
    CHECK((PORTB.DIR & PIN2_bm) && !(PORTB.OUT & PIN2_bm), "indicator output, off");
    CHECK(!mock_irq_enabled && wdr_count == 0, "interrupts and watchdog clearing left to the caller");
}

static void test_references_and_comparators(void)
{
    reset_model();
    hal_init();
    CHECK(VREF.CTRLA == (VREF_ADC0REFSEL_1V1_gc | VREF_DAC0REFSEL_1V5_gc), "ADC0 INTREF 1.1 V, DAC0 1.5 V");
    CHECK(VREF.CTRLB & VREF_ADC0REFEN_bm, "1.1 V reference forced on");
    CHECK(VREF.CTRLC == VREF_ADC1REFSEL_1V5_gc, "ADC1 1.5 V (DAC1 unused)");
    CHECK(VREF.CTRLD == VREF_DAC2REFSEL_1V5_gc, "DAC2/AC2 reference in CTRLD (AUD-FW-19)");
    CHECK((ADC0.CTRLC & ADC_REFSEL_gm) == ADC_REFSEL_VDDREF_gc, "ADC0 always referenced to VDD");
    CHECK((ADC1.CTRLC & ADC_REFSEL_gm) == ADC_REFSEL_INTREF_gc, "ADC1 internal (1.5 V) reference");
    CHECK(DAC0.DATA == 160u && DAC2.DATA == 222u, "comparator thresholds 5.625 V / 2.60 V");
    CHECK(DAC2.CTRLA == (DAC_ENABLE_bm | DAC_RUNSTDBY_bm), "DAC2 runs in standby for the hold-up wake-up (AUD-FW-20)");
    CHECK(AC0.MUXCTRLA == (AC_MUXPOS_PIN0_gc | AC_MUXNEG_DAC_gc) && (AC0.CTRLA & AC_INTMODE_gm) == AC_INTMODE_POSEDGE_gc,
          "AC0: VOUT/6 rising above DAC0");
    CHECK(AC2.MUXCTRLA == (AC_MUXPOS_PIN2_gc | AC_MUXNEG_DAC_gc) && (AC2.CTRLA & AC_INTMODE_gm) == AC_INTMODE_NEGEDGE_gc
          && (AC2.CTRLA & AC_RUNSTDBY_bm), "AC2: VBAT/2 falling below DAC2, runs in standby");
    CHECK(TCB0.CCMP == 4999u && WDT.CTRLA == WDT_PERIOD_64CLK_gc, "1 kHz tick, 64 ms watchdog");
    CHECK(RTC.INTCTRL == RTC_OVF_bm && RTC.PER == 0xFFFFu, "RTC overflow extends the gap timer");
}

static void test_sample_sequence(void)
{
    hal_sample_t s;
    reset_model();
    hal_init();
    n_convs = 0;
    adc0_value[0x1D] = 322; adc0_value[8] = 555; adc0_value[6] = 584; adc0_value[5] = 445; adc0_value[9] = 1023;
    adc1_value[3] = 512;
    PORTA.IN = PIN3_bm;                           /* PA2 low (interlock closed), PA3 high (switch open) */
    PORTB.IN = 0;                                 /* PB1 low: CC active */
    hal_sample(&s);
    CHECK(s.ref == 322 && s.vbat == 555 && s.cs == 584 && s.ntc_board == 445 && s.ntc_laser == 1023 && s.vout == 512,
          "each channel read from its multiplexer input");
    CHECK(n_convs == 7 && convs[0].mux == ADC_MUXPOS_INTREF_gc && convs[1].mux == ADC_MUXPOS_INTREF_gc,
          "reference read twice (settling) first");
    for (unsigned i = 0; i < n_convs; i++) {
        bool ntc = !convs[i].adc1 && (convs[i].mux == ADC_MUXPOS_AIN5_gc || convs[i].mux == ADC_MUXPOS_AIN9_gc);
        if (!convs[i].adc1) CHECK(convs[i].refsel == ADC_REFSEL_VDDREF_gc, "every ADC0 conversion on VDD");
        CHECK(convs[i].bias == ntc, "NTC bias on exactly during the NTC conversions");
    }
    CHECK(!(PORTA.OUT & PIN4_bm), "bias off after sampling");
    CHECK(s.interlock_closed && !s.switch_closed && s.cc_active, "digital polarity: low = closed / active");
}

static void test_outputs_and_overvoltage_latch(void)
{
    reset_model();
    hal_init();
    hal_outputs(true, true, false);
    CHECK(!(PORTA.OUT & PIN1_bm) && (PORTB.OUT & PIN2_bm), "enable: LASER_EN_N low, indicator on");
    CHECK(PORTB.PIN1CTRL == PORT_ISC_INPUT_DISABLE_gc, "CC pull-up still off on the first enabled tick");
    hal_outputs(true, true, true);
    CHECK(PORTB.PIN1CTRL == PORT_PULLUPEN_bm, "CC pull-up on while running");
    mock_isr_ac0();
    CHECK((PORTA.OUT & PIN1_bm) && hal_ov_latched(), "AC0 interrupt disables at once and latches");
    hal_outputs(true, true, true);
    CHECK((PORTA.OUT & PIN1_bm) && PORTB.PIN1CTRL == PORT_ISC_INPUT_DISABLE_gc,
          "after an over-voltage event the HAL refuses to enable");
    hal_outputs(false, false, false);
    CHECK((PORTA.OUT & PIN1_bm) && !(PORTB.OUT & PIN2_bm), "disable");
}

static void test_tick_counter_and_flags(void)
{
    reset_model();
    hal_init();
    for (unsigned i = 0; i < 300u; i++) mock_isr_tcb0();
    CHECK(hal_ticks_take() == 255u && hal_ticks_take() == 0u, "pending ticks saturate, then clear");
    CHECK(mock_irq_enabled, "tick handover re-enables interrupts");
    mock_isr_ac2();
    CHECK(hal_power_lost() && (PORTA.OUT & PIN1_bm), "AC2 interrupt: laser off, power-loss flag");
    hal_wdt_clear();
    CHECK(wdr_count == 1, "watchdog clear is one wdr");
}

static void test_holdup_hardware(void)
{
    reset_model();
    hal_init();
    PORTA.OUT |= PIN4_bm;
    hal_holdup_enter();
    CHECK(WDT.CTRLA == 0 && SLPCTRL.CTRLA == (SLPCTRL_SMODE_STDBY_gc | SLPCTRL_SEN_bm), "watchdog off, standby sleep");
    CHECK((AC2.CTRLA & AC_INTMODE_gm) == AC_INTMODE_BOTHEDGE_gc && (AC2.CTRLA & AC_ENABLE_bm), "AC2 wakes on return");
    CHECK(ADC0.CTRLA == 0 && ADC1.CTRLA == 0 && AC0.CTRLA == 0 && VREF.CTRLB == 0, "loads on the hold-up charge off");
    CHECK(PORTB.PIN1CTRL == PORT_ISC_INPUT_DISABLE_gc && PORTA.PIN3CTRL == PORT_ISC_INPUT_DISABLE_gc
          && !(PORTA.OUT & PIN4_bm), "no pull-ups or bias draining C16");
    AC2.STATUS = 0;
    CHECK(!hal_supply_present(), "AC2 state low: supply absent");
    hal_holdup_sleep();
    CHECK(sleeps == 1 && irq_at_sleep, "sleeps with interrupts enabled (sei; sleep)");
    AC2.STATUS = AC_STATE_bm;
    hal_holdup_sleep();
    CHECK(sleeps == 1 && hal_supply_present(), "never sleeps when the supply is already back (AUD-FW-08)");
    hal_holdup_guard(true);
    CHECK(WDT.CTRLA == WDT_PERIOD_1KCLK_gc, "1 s guard watchdog while polling");
    hal_holdup_guard(false);
    CHECK(WDT.CTRLA == 0, "guard off before sleeping");
}

static void test_rtc_extension(void)
{
    reset_model();
    hal_init();
    RTC.CNT = 0x1234;
    CHECK(hal_rtc_ticks() == 0x1234u, "low word");
    mock_isr_rtc();
    CHECK(RTC.INTFLAGS == RTC_OVF_bm, "ISR acknowledges the overflow (write-1-to-clear)");
    RTC.INTFLAGS = 0;                             /* what the hardware does with that write */
    CHECK(hal_rtc_ticks() == 0x11234u, "overflow counted");
    RTC.CNT = 0x0002; RTC.INTFLAGS = RTC_OVF_bm;  /* wrapped, interrupt not yet serviced */
    CHECK(hal_rtc_ticks() == 0x20002u, "pending overflow counted once");
}

static void test_reset_cause_and_fuses(void)
{
    RSTCTRL.RSTFR = RSTCTRL_WDRF_bm | RSTCTRL_BORF_bm;
    CHECK(hal_reset_cause() == (HAL_RST_WATCHDOG | HAL_RST_BROWN_OUT), "reset flags mapped");
    FUSE.BODCFG = FW_FUSE_BODCFG; FUSE.OSCCFG = FW_FUSE_OSCCFG | 0x80u;
    CHECK(hal_config_ok(), "required fuses (OSCLOCK ignored)");
    FUSE.BODCFG = 0x00;                           /* factory default: BOD disabled */
    CHECK(!hal_config_ok(), "BOD disabled is rejected");
    FUSE.BODCFG = FW_FUSE_BODCFG; FUSE.OSCCFG = 0x01; /* 16 MHz oscillator: every timer 20 % slow */
    CHECK(!hal_config_ok(), "wrong oscillator is rejected");
}

int main(void)
{
    test_init_order_and_pins();
    test_references_and_comparators();
    test_sample_sequence();
    test_outputs_and_overvoltage_latch();
    test_tick_counter_and_flags();
    test_holdup_hardware();
    test_rtc_extension();
    test_reset_cause_and_fuses();
    return CHECK_SUMMARY();
}
