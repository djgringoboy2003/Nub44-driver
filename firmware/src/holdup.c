#include "holdup.h"

void holdup_begin(holdup_t *h, uint32_t now)
{
    h->t_loss = now;
    h->t_return = now;
    h->returning = false;
}

holdup_action_t holdup_step(holdup_t *h, uint32_t now, bool supply_present)
{
    if (!supply_present) {
        h->returning = false;           /* bounce: the gap continues from the first loss */
        return HOLDUP_SLEEP;
    }
    if (!h->returning) {
        h->returning = true;
        h->t_return = now;
    }
    return (now - h->t_return) >= HOLDUP_RETURN_TICKS ? HOLDUP_RESTART : HOLDUP_WAIT;
}

uint32_t holdup_gap_ticks(const holdup_t *h)
{
    return h->t_return - h->t_loss;
}

holdup_gap_t holdup_classify(const holdup_t *h)
{
    uint32_t gap = holdup_gap_ticks(h);
    if (gap < HOLDUP_MIN_CLICK_TICKS) {
        return GAP_GLITCH;
    }
    return gap < HOLDUP_SHORT_GAP_TICKS ? GAP_CLICK : GAP_LONG;
}
