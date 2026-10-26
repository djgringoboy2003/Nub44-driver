/* Host unit tests for firmware/src/holdup.c (power-gap logic). Build and run: firmware/build.py */
#include "../src/holdup.h"
#include "check.h"

/* Drive the logic with a supply waveform: present(t) for t >= t0, one step per RTC tick.
 * Returns the tick at which RESTART is requested and counts how many times it was requested. */
typedef bool (*supply_fn)(uint32_t t);

static uint32_t simulate(holdup_t *h, uint32_t t0, supply_fn present, unsigned *restarts)
{
    uint32_t t = t0, t_restart = 0;
    *restarts = 0;
    holdup_begin(h, t0);
    for (unsigned i = 0; i < 20000u; i++, t++) {
        if (holdup_step(h, t, present(t)) == HOLDUP_RESTART) {
            if (*restarts == 0u) t_restart = t;
            (*restarts)++;
            break;
        }
    }
    return t_restart;
}

static uint32_t g_return;
static bool after_return(uint32_t t) { return t >= g_return; }
static bool bouncing(uint32_t t) { return (t >= 200u && t < 205u) || (t >= 207u && t < 209u) || t >= 212u; }
static bool always(uint32_t t) { (void)t; return true; }

static holdup_gap_t gap_after(uint32_t ticks)
{
    holdup_t h;
    unsigned n;
    g_return = 1000u + ticks;
    simulate(&h, 1000u, after_return, &n);
    return holdup_classify(&h);
}

static void test_classification_boundaries(void)
{
    CHECK(gap_after(5) == GAP_GLITCH, "5 ms: glitch");
    CHECK(gap_after(HOLDUP_MIN_CLICK_TICKS - 1u) == GAP_GLITCH, "just below the click minimum");
    CHECK(gap_after(HOLDUP_MIN_CLICK_TICKS) == GAP_CLICK, "click minimum");
    CHECK(gap_after(200) == GAP_CLICK, "200 ms click");
    CHECK(gap_after(HOLDUP_SHORT_GAP_TICKS - 1u) == GAP_CLICK, "just below 0.5 s");
    CHECK(gap_after(HOLDUP_SHORT_GAP_TICKS) == GAP_LONG, "0.5 s and longer: long");
    CHECK(gap_after(5000) == GAP_LONG, "5 s");
}

static void test_restart_needs_stable_supply(void)
{
    holdup_t h;
    unsigned n;
    uint32_t t;
    g_return = 300u;
    t = simulate(&h, 100u, after_return, &n);
    CHECK(n == 1u && t == 300u + HOLDUP_RETURN_TICKS, "restart after the return debounce");
    CHECK(holdup_gap_ticks(&h) == 200u, "gap measured to the return");
}

static void test_bounce_on_return_is_one_gap(void)
{
    holdup_t h;
    unsigned n;
    uint32_t t = simulate(&h, 0u, bouncing, &n);
    CHECK(n == 1u, "a bouncing return gives one restart");
    CHECK(t == 212u + HOLDUP_RETURN_TICKS, "restart only after the last bounce has settled");
    CHECK(holdup_gap_ticks(&h) == 212u && holdup_classify(&h) == GAP_CLICK, "gap measured from the first loss");
}

static void test_supply_already_back(void)
{
    holdup_t h;
    unsigned n;
    uint32_t t = simulate(&h, 50u, always, &n);
    CHECK(n == 1u && t == 50u + HOLDUP_RETURN_TICKS, "a sag that already recovered restarts (never sleeps forever)");
    CHECK(holdup_classify(&h) == GAP_GLITCH, "and is not a click");
    CHECK(holdup_step(&h, 60u, false) == HOLDUP_SLEEP, "absent supply -> sleep");
}

static void test_rtc_wraparound(void)
{
    holdup_t h;
    holdup_begin(&h, 0xFFFFFF00u);
    holdup_step(&h, 0x00000080u, true);           /* 384 ticks later, across the 32-bit wrap */
    CHECK(holdup_gap_ticks(&h) == 0x180u && holdup_classify(&h) == GAP_CLICK, "gap across the counter wrap");
}

int main(void)
{
    test_classification_boundaries();
    test_restart_needs_stable_supply();
    test_bounce_on_return_is_one_gap();
    test_supply_already_back();
    test_rtc_wraparound();
    return CHECK_SUMMARY();
}
