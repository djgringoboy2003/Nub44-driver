/*
 * Host register model of the ATtiny1616 peripherals used by firmware/src/hal_avr.c (tests only).
 *
 * Registers are plain memory. Constant values are copied from avr-libc iotn1616.h (avr-gcc 15.2.0);
 * tests/test_firmware_mock_header.py fails if any value here differs from the real header. The HAL_*
 * seam macros route port writes, ADC conversions and the watchdog instruction to mock_avr.c so the test
 * can check order, reference selection and bias state at every conversion.
 */
#ifndef MOCK_AVR_IO_H
#define MOCK_AVR_IO_H

#include <stdint.h>

typedef volatile uint8_t register8_t;
typedef volatile uint16_t register16_t;

typedef struct {
    register8_t DIR, DIRSET, DIRCLR, OUT, OUTSET, OUTCLR, IN;
    register8_t PIN0CTRL, PIN1CTRL, PIN2CTRL, PIN3CTRL, PIN4CTRL, PIN5CTRL, PIN6CTRL, PIN7CTRL;
} PORT_t;
typedef struct { register8_t CTRLA, CTRLB, CTRLC, CTRLD; } VREF_t;
typedef struct {
    register8_t CTRLA, CTRLB, CTRLC, CTRLD, CTRLE, SAMPCTRL, MUXPOS, COMMAND, INTFLAGS;
    register16_t RES;
} ADC_t;
typedef struct { register8_t CTRLA, DATA; } DAC_t;
typedef struct { register8_t CTRLA, MUXCTRLA, INTCTRL, STATUS; } AC_t;
typedef struct { register8_t CTRLA, INTCTRL, INTFLAGS; register16_t CCMP; } TCB_t;
typedef struct { register8_t CTRLA, STATUS, INTCTRL, INTFLAGS, CLKSEL; register16_t CNT, PER; } RTC_t;
typedef struct { register8_t CTRLA, STATUS; } WDT_t;
typedef struct { register8_t CTRLA; } SLPCTRL_t;
typedef struct { register8_t RSTFR, SWRR; } RSTCTRL_t;
typedef struct { register8_t MCLKCTRLB; } CLKCTRL_t;
typedef struct { register8_t WDTCFG, BODCFG, OSCCFG; } FUSE_t;

extern PORT_t PORTA, PORTB, PORTC;
extern VREF_t VREF;
extern ADC_t ADC0, ADC1;
extern DAC_t DAC0, DAC2;
extern AC_t AC0, AC2;
extern TCB_t TCB0;
extern RTC_t RTC;
extern WDT_t WDT;
extern SLPCTRL_t SLPCTRL;
extern RSTCTRL_t RSTCTRL;
extern CLKCTRL_t CLKCTRL;
extern FUSE_t FUSE;
extern volatile uint8_t SREG;

#define _PROTECTED_WRITE(reg, value)    ((reg) = (value))

/* seams (see firmware/src/hal_avr.c) */
void mock_port_set(PORT_t *p, uint8_t mask);
void mock_port_clr(PORT_t *p, uint8_t mask);
void mock_port_dir(PORT_t *p, uint8_t mask);
void mock_adc_convert(ADC_t *adc);
void mock_wdr(void);
#define HAL_PORT_SET(port, mask)        mock_port_set(&(port), (mask))
#define HAL_PORT_CLR(port, mask)        mock_port_clr(&(port), (mask))
#define HAL_PORT_DIR(port, mask)        mock_port_dir(&(port), (mask))
#define HAL_ADC_CONVERT(adc)            mock_adc_convert(adc)
#define HAL_WDR()                       mock_wdr()

/* interrupt vectors become plain functions the test can call */
#define TCB0_INT_vect                   mock_isr_tcb0
#define AC0_AC_vect                     mock_isr_ac0
#define AC2_AC_vect                     mock_isr_ac2
#define RTC_CNT_vect                    mock_isr_rtc

/* constants (values from iotn1616.h) */
#define AC_CMP_bm                        0x01
#define AC_ENABLE_bm                     0x01
#define AC_HYSMODE_25mV_gc               (0x04)
#define AC_INTMODE_BOTHEDGE_gc           (0x00)
#define AC_INTMODE_NEGEDGE_gc            (0x20)
#define AC_INTMODE_POSEDGE_gc            (0x30)
#define AC_INTMODE_gm                    0x30
#define AC_MUXNEG_DAC_gc                 (0x03)
#define AC_MUXPOS_PIN0_gc                (0x00)
#define AC_MUXPOS_PIN2_gc                (0x10)
#define AC_RUNSTDBY_bm                   0x80
#define AC_STATE_bm                      0x10
#define ADC_ENABLE_bm                    0x01
#define ADC_INITDLY_DLY64_gc             (0x60)
#define ADC_MUXPOS_AIN3_gc               (0x03)
#define ADC_MUXPOS_AIN5_gc               (0x05)
#define ADC_MUXPOS_AIN6_gc               (0x06)
#define ADC_MUXPOS_AIN8_gc               (0x08)
#define ADC_MUXPOS_AIN9_gc               (0x09)
#define ADC_MUXPOS_INTREF_gc             (0x1D)
#define ADC_PRESC_DIV16_gc               (0x03)
#define ADC_REFSEL_INTREF_gc             (0x00)
#define ADC_REFSEL_VDDREF_gc             (0x10)
#define ADC_REFSEL_gm                    0x30
#define ADC_RESRDY_bm                    0x01
#define ADC_SAMPCAP_bm                   0x40
#define ADC_STCONV_bm                    0x01
#define CLKCTRL_PDIV_4X_gc               (0x02)
#define CLKCTRL_PEN_bm                   0x01
#define DAC_ENABLE_bm                    0x01
#define DAC_RUNSTDBY_bm                  0x80
#define PIN0_bm                          0x01
#define PIN1_bm                          0x02
#define PIN2_bm                          0x04
#define PIN3_bm                          0x08
#define PIN4_bm                          0x10
#define PIN5_bm                          0x20
#define PIN6_bm                          0x40
#define PIN7_bm                          0x80
#define PORT_ISC_INPUT_DISABLE_gc        (0x04)
#define PORT_PULLUPEN_bm                 0x08
#define RSTCTRL_BORF_bm                  0x02
#define RSTCTRL_EXTRF_bm                 0x04
#define RSTCTRL_PORF_bm                  0x01
#define RSTCTRL_SWRE_bm                  0x01
#define RSTCTRL_SWRF_bm                  0x10
#define RSTCTRL_UPDIRF_bm                0x20
#define RSTCTRL_WDRF_bm                  0x08
#define RTC_CLKSEL_INT32K_gc             (0x00)
#define RTC_OVF_bm                       0x01
#define RTC_PRESCALER_DIV32_gc           (0x28)
#define RTC_RTCEN_bm                     0x01
#define RTC_RUNSTDBY_bm                  0x80
#define SLPCTRL_SEN_bm                   0x01
#define SLPCTRL_SMODE_STDBY_gc           (0x02)
#define TCB_CAPT_bm                      0x01
#define TCB_CLKSEL_CLKDIV1_gc            (0x00)
#define TCB_ENABLE_bm                    0x01
#define VREF_ADC0REFEN_bm                0x02
#define VREF_ADC0REFSEL_1V1_gc           (0x10)
#define VREF_ADC1REFSEL_1V5_gc           (0x40)
#define VREF_DAC0REFSEL_1V5_gc           (0x04)
#define VREF_DAC2REFSEL_1V5_gc           (0x04)
#define WDT_PERIOD_1KCLK_gc              (0x08)
#define WDT_PERIOD_64CLK_gc              (0x04)
#define WDT_SYNCBUSY_bm                  0x01

#endif
