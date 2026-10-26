#include "conv.h"

bool conv_ref_valid(uint16_t raw_ref)
{
    return raw_ref >= CONV_REF_RAW_MIN && raw_ref <= CONV_REF_RAW_MAX;
}

uint16_t conv_vdd_mv(uint16_t raw_ref)
{
    if (!conv_ref_valid(raw_ref)) {
        return 0;
    }
    return (uint16_t)(((uint32_t)CONV_REF_CAL_MV * CONV_ADC_MAX + raw_ref / 2u) / raw_ref);
}

uint16_t conv_ratio_mv(uint16_t raw, uint16_t raw_ref)
{
    if (!conv_ref_valid(raw_ref) || raw > CONV_ADC_MAX) {
        return 0;
    }
    return (uint16_t)(((uint32_t)CONV_REF_CAL_MV * raw + raw_ref / 2u) / raw_ref);
}

uint16_t conv_vbat_mv(uint16_t raw, uint16_t raw_ref)
{
    return (uint16_t)(conv_ratio_mv(raw, raw_ref) * CONV_VBAT_DIV);
}

uint16_t conv_laser_ma(uint16_t raw, uint16_t raw_ref)
{
    return (uint16_t)(conv_ratio_mv(raw, raw_ref) * CONV_CS_MA_PER_MV);
}

uint16_t conv_vout_mv(uint16_t raw_adc1)
{
    if (raw_adc1 > CONV_ADC_MAX) {
        raw_adc1 = CONV_ADC_MAX;
    }
    return (uint16_t)(((uint32_t)raw_adc1 * CONV_REF_ADC1_MV * CONV_VOUT_DIV + CONV_ADC_MAX / 2u) / CONV_ADC_MAX);
}

/* 10k NTC (B 3380) against 10k to NTC_PWR, ratiometric -> tenths of a degree (piecewise linear).
 * Table from R(T) = 10k * exp(3380 * (1/T - 1/298.15)), raw = 1023 * R / (R + 10k). */
sensor_status_t conv_ntc(uint16_t raw, int16_t *c10)
{
    static const uint16_t tab_raw[] = {903, 838, 755, 661, 512, 376, 268, 189, 133, 95, 69};
    static const int16_t tab_t[] = {-200, -100, 0, 100, 250, 400, 550, 700, 850, 1000, 1150};
    const uint8_t n = (uint8_t)(sizeof(tab_raw) / sizeof(tab_raw[0]));
    *c10 = CONV_T_NONE;
    if (raw >= CONV_NTC_OPEN_RAW) {
        return SENSOR_OPEN;
    }
    if (raw <= CONV_NTC_SHORT_RAW) {
        return SENSOR_SHORT;
    }
    if (raw >= tab_raw[0]) {
        *c10 = tab_t[0];                          /* colder than -20 C: clamp (never trips a limit) */
        return SENSOR_OK;
    }
    if (raw <= tab_raw[n - 1u]) {
        *c10 = tab_t[n - 1u];                     /* hotter than 115 C: clamp (above every limit) */
        return SENSOR_OK;
    }
    for (uint8_t i = 0; (uint8_t)(i + 1u) < n; i++) {
        if (raw <= tab_raw[i] && raw >= tab_raw[i + 1u]) {
            int32_t span = (int32_t)tab_raw[i] - tab_raw[i + 1u];
            *c10 = (int16_t)(tab_t[i] + (int32_t)(tab_t[i + 1u] - tab_t[i]) * (tab_raw[i] - raw) / span);
            break;
        }
    }
    return SENSOR_OK;
}
