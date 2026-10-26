/* Host unit tests for firmware/src/conv.c (measurement conversions). Build and run: firmware/build.py */
#include <math.h>
#include <stdlib.h>

#include "../src/conv.h"
#include "check.h"

static uint16_t adc(double v_pin, double v_ref)
{
    double raw = v_pin / v_ref * 1023.0 + 0.5;
    return raw > 1023.0 ? 1023u : (uint16_t)raw;
}

static void test_reference_window(void)
{
    CHECK(!conv_ref_valid(0) && !conv_ref_valid(1023), "rail readings are invalid");
    CHECK(conv_ref_valid(adc(1.1, 5.5)) && conv_ref_valid(adc(1.1, 1.8)), "VDD 1.8-5.5 V is valid");
    CHECK(!conv_ref_valid(CONV_REF_RAW_MIN - 1u) && !conv_ref_valid(CONV_REF_RAW_MAX + 1u), "window edges");
    CHECK(abs((int)conv_vdd_mv(adc(1.1, 3.3)) - 3300) <= 10, "VDD from the 1.1 V reading");
    CHECK(conv_vdd_mv(0) == 0 && conv_vbat_mv(500, 0) == 0 && conv_laser_ma(500, 1023) == 0,
          "invalid reference -> zero, never a plausible value");
}

/* The battery thresholds must be measurable when VDD (= VBAT - D2) is below 2.9 V (AUD-FW-04). */
static void test_vbat_ratiometric_over_supply(void)
{
    int worst = 0;
    for (int vbat = 2700; vbat <= 4200; vbat += 50) {
        for (int drop = 150; drop <= 450; drop += 100) {
            double vdd = (vbat - drop) / 1000.0;
            uint16_t raw_ref = adc(1.1, vdd), raw = adc(vbat / 2000.0, vdd);
            int err = abs((int)conv_vbat_mv(raw, raw_ref) - vbat);
            if (err > worst) worst = err;
        }
    }
    CHECK(worst <= 12, "VBAT within 12 mV (quantisation only) for VDD 2.25-4.05 V");
    CHECK(abs((int)conv_vbat_mv(adc(1.45, 2.6), adc(1.1, 2.6)) - 2900) <= 12, "2.9 V cut-off readable at VDD 2.6 V");
}

static void test_laser_current(void)
{
    double vdd = 3.5;
    CHECK(abs((int)conv_laser_ma(adc(2.0, vdd), adc(1.1, vdd)) - 4000) <= 15, "4.0 A -> 2.0 V -> 4000 mA");
    CHECK(conv_laser_ma(0, adc(1.1, vdd)) == 0, "zero current");
    vdd = 2.6;                                     /* CS above VDD saturates: reads the rail, never wraps */
    CHECK(conv_laser_ma(1023, adc(1.1, vdd)) >= 5000, "saturated reading stays above the regulation window");
}

static void test_vout(void)
{
    CHECK(conv_vout_mv(0) == 0, "0 V");
    CHECK(abs((int)conv_vout_mv(adc(5.625 / 6.0, 1.5)) - 5625) <= 10, "5.625 V trip level");
    CHECK(conv_vout_mv(1023) == 9000 && conv_vout_mv(2000) == 9000, "full scale 9 V, clamps");
}

static void test_dac_codes(void)
{
    CHECK(CONV_DAC_CODE(5625u / 6u) == 160u, "AC0 code for the 5.625 V over-voltage trip");
    CHECK(CONV_DAC_CODE(2600u / 2u) == 222u, "AC2 code for the 2.6 V power-loss trip");
    CHECK(fabs(160 * 1.5 / 256 * 6 - 5.625) < 0.01, "AC0 code reproduces 5.625 V");
    CHECK(fabs(222 * 1.5 / 256 * 2 - 2.600) < 0.01, "AC2 code reproduces 2.60 V");
}

static double ntc_raw(double t_c)
{
    double r = 10e3 * exp(3380.0 * (1.0 / (t_c + 273.15) - 1.0 / 298.15));
    return 1023.0 * r / (r + 10e3);
}

static void test_ntc_against_beta_model(void)
{
    double worst = 0;
    int16_t c10;
    for (int t10 = -200; t10 <= 1150; t10 += 5) {
        uint16_t raw = (uint16_t)(ntc_raw(t10 / 10.0) + 0.5);
        CHECK(conv_ntc(raw, &c10) == SENSOR_OK, "valid over -20..115 C");
        if (fabs((c10 - t10) / 10.0) > worst) worst = fabs((c10 - t10) / 10.0);
    }
    CHECK(worst <= 1.2, "table within 1.2 C of the B3380 model");
    conv_ntc((uint16_t)(ntc_raw(60.0) + 0.5), &c10);
    CHECK(c10 >= 600, "the 60 C laser limit is not read low");
    conv_ntc((uint16_t)(ntc_raw(85.5) + 0.5), &c10);
    CHECK(c10 > 850, "85.5 C reads above the 85 C board limit");
}

static void test_ntc_faults(void)
{
    int16_t c10 = 0;
    CHECK(conv_ntc(1023, &c10) == SENSOR_OPEN && c10 == CONV_T_NONE, "open: bias rail");
    CHECK(conv_ntc(CONV_NTC_OPEN_RAW, &c10) == SENSOR_OPEN, "open threshold");
    CHECK(conv_ntc(0, &c10) == SENSOR_SHORT && c10 == CONV_T_NONE, "short / bias missing");
    CHECK(conv_ntc(CONV_NTC_SHORT_RAW, &c10) == SENSOR_SHORT, "short threshold");
    CHECK(conv_ntc(CONV_NTC_SHORT_RAW + 1u, &c10) == SENSOR_OK && c10 == 1150, "very hot clamps above every limit");
    CHECK(conv_ntc(CONV_NTC_OPEN_RAW - 1u, &c10) == SENSOR_OK && c10 == -200, "very cold clamps (no trip)");
}

int main(void)
{
    test_reference_window();
    test_vbat_ratiometric_over_supply();
    test_laser_current();
    test_vout();
    test_dac_codes();
    test_ntc_against_beta_model();
    test_ntc_faults();
    return CHECK_SUMMARY();
}
