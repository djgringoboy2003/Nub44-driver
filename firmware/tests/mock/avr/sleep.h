/* Host model of <avr/sleep.h> for the register-model test (firmware/tests/test_hal.c). */
#ifndef MOCK_AVR_SLEEP_H
#define MOCK_AVR_SLEEP_H

void mock_sleep_cpu(void);
#define sleep_cpu()     mock_sleep_cpu()

#endif
