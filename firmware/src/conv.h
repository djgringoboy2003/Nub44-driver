/*
 * Measurement conversions (hardware independent, unit-tested on the host).
 *
 * Measurement chain (audit AUD-FW-04/05). The 2.5 V internal reference needs VDD >= 2.9 V
 * (ATtiny1616 DS40001997C Table 37-22), but VMCU sits one Schottky drop (D2) below VBAT, so near the
 * 3.2/3.1/2.9 V battery thresholds VDD is at or below that limit. Therefore:
 *   - ADC0 always uses VDD as its reference (no reference switching between conversions). Each tick
 *     it measures the 1.1 V internal reference (INT11V, specified for VDD 1.8-5.5 V) as an input, which
 *     calibrates VDD; VBAT and the laser current are then computed ratiometrically:
 *         V_in = 1100 mV * raw_in / raw_ref
 *   - ADC1 (VOUT) and the DACs feeding AC0 (over-voltage) and AC2 (power loss) use the 1.5 V reference
 *     (INT15V, specified for VDD 1.9-5.5 V).
 * Hardware constants come from engineering/design/connectivity.yaml (R10/R11, R12/R13, R14/R15, RT1,
 * U2 INA186A2 x RS1) and parameters.yaml (shunt, CSA gain).
 */
#ifndef CONV_H
#define CONV_H

#include <stdbool.h>
#include <stdint.h>

#define CONV_ADC_MAX            1023u
#define CONV_REF_CAL_MV         1100u   /* INT11V measured on the ADC0 INTREF input */
#define CONV_REF_ADC1_MV        1500u   /* INT15V reference of ADC1 */
#define CONV_REF_DAC_MV         1500u   /* INT15V reference of DAC0 (AC0) and DAC2 (AC2) */
#define CONV_VBAT_DIV           2u      /* R10 100k / R11 100k */
#define CONV_VOUT_DIV           6u      /* R12 100k / R13 20k */
#define CONV_CS_MA_PER_MV       2u      /* INA186A2 gain 50 x RS1 10 mOhm = 0.5 V/A */

/* Plausible INT11V readings against VDD: VDD 5.5 V -> 205 counts, VDD 1.8 V -> 625 counts. Outside this
 * window the reference measurement is broken and no ratiometric value is trustworthy. */
#define CONV_REF_RAW_MIN        190u
#define CONV_REF_RAW_MAX        640u

/* NTC divider: 10k bias (R14/R15) from NTC_PWR to the pin, 10k NTC (B 3380 K) to GND. An open NTC reads
 * the bias rail (about 1023), a shorted NTC or a missing bias reads about 0. */
#define CONV_NTC_OPEN_RAW       1015u   /* >= this: open (R > ~1.3 MOhm, below about -70 C) */
#define CONV_NTC_SHORT_RAW      8u      /* <= this: short (R < ~80 Ohm, above about +200 C) */
#define CONV_T_NONE             (-32768)

typedef enum {
    SENSOR_OK = 0,
    SENSOR_OPEN = 1,
    SENSOR_SHORT = 2,
} sensor_status_t;

/* DAC code for a comparator threshold at the divided pin voltage `pin_mv` (8-bit DAC, INT15V). */
#define CONV_DAC_CODE(pin_mv)   ((uint8_t)((((uint32_t)(pin_mv)) * 256UL + CONV_REF_DAC_MV / 2u) / CONV_REF_DAC_MV))

bool conv_ref_valid(uint16_t raw_ref);
uint16_t conv_vdd_mv(uint16_t raw_ref);                         /* 0 when the reference reading is invalid */
uint16_t conv_ratio_mv(uint16_t raw, uint16_t raw_ref);         /* pin voltage in mV, 0 when invalid */
uint16_t conv_vbat_mv(uint16_t raw, uint16_t raw_ref);
uint16_t conv_laser_ma(uint16_t raw, uint16_t raw_ref);
uint16_t conv_vout_mv(uint16_t raw_adc1);
sensor_status_t conv_ntc(uint16_t raw, int16_t *c10);          /* *c10 = tenths of a degree, or CONV_T_NONE */

#endif
