/*
 * Firmware runtime: start-up, the supervision cycle and the power-gap (hold-up) sequence.
 * Uses only hal.h, so it runs unchanged against the host mock (firmware/tests/hal_mock.c).
 */
#ifndef FW_H
#define FW_H

#include <stdint.h>

#include "app.h"
#include "hal.h"

#define FW_NOINIT_MAGIC     0x4C44u     /* "LD" */
#define FW_MAX_TICK_BACKLOG 4u          /* more pending ticks than this = supervision overrun */

void fw_init(void);                     /* after any reset */
void fw_poll(void);                     /* one main-loop pass */
const app_t *fw_app(void);              /* state machine, for tests and debugging */
app_inputs_t fw_inputs_from(const hal_sample_t *s, bool ov_latched);

#endif
