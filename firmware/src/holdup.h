/*
 * Power-gap (hold-up) logic, hardware independent and unit-tested on the host.
 *
 * When the battery disappears (clicky tail switch), AC2 stops emission and the MCU sleeps on the C16 charge,
 * timing the gap with the RTC (1024 Hz). Audit AUD-FW-08/09:
 *   - the supply must stay present for HOLDUP_RETURN_TICKS before the restart, so a bouncing contact
 *     produces one restart, and the gap is measured from the first loss to the final return;
 *   - gaps shorter than HOLDUP_MIN_CLICK_TICKS are glitches (sag or contact bounce, not a deliberate
 *     click): restart without a mode change;
 *   - gaps up to HOLDUP_SHORT_GAP_TICKS advance the mode; longer gaps return to continuous.
 */
#ifndef HOLDUP_H
#define HOLDUP_H

#include <stdbool.h>
#include <stdint.h>

#define HOLDUP_TICK_HZ          1024u
#define HOLDUP_RETURN_TICKS     20u     /* ~20 ms of continuous supply before restarting */
#define HOLDUP_MIN_CLICK_TICKS  31u     /* ~30 ms: shorter gaps are glitches, not clicks */
#define HOLDUP_SHORT_GAP_TICKS  512u    /* 0.5 s: shorter gaps advance the mode (DD-08) */

typedef enum {
    GAP_GLITCH = 0,     /* restart, keep the mode */
    GAP_CLICK = 1,      /* restart, next mode */
    GAP_LONG = 2,       /* restart, continuous mode */
} holdup_gap_t;

typedef enum {
    HOLDUP_SLEEP = 0,   /* supply absent: sleep until a comparator or RTC event */
    HOLDUP_WAIT = 1,    /* supply back but not yet stable: keep polling */
    HOLDUP_RESTART = 2, /* supply stable: classify the gap and restart */
} holdup_action_t;

typedef struct {
    uint32_t t_loss;    /* RTC ticks at the first loss */
    uint32_t t_return;  /* RTC ticks when the supply last came back */
    bool returning;
} holdup_t;

void holdup_begin(holdup_t *h, uint32_t now);
holdup_action_t holdup_step(holdup_t *h, uint32_t now, bool supply_present);
uint32_t holdup_gap_ticks(const holdup_t *h);
holdup_gap_t holdup_classify(const holdup_t *h);

#endif
