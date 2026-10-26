/* Host model of <avr/interrupt.h> for the register-model test (firmware/tests/test_hal.c). */
#ifndef MOCK_AVR_INTERRUPT_H
#define MOCK_AVR_INTERRUPT_H

#include <stdbool.h>

extern bool mock_irq_enabled;
#define sei()           (mock_irq_enabled = true)
#define cli()           (mock_irq_enabled = false)
#define ISR(vector)     void vector(void)

#endif
