/*
 * NUBM44 driver firmware: ATtiny1616 (tinyAVR 1-series), 5 MHz (20 MHz oscillator / 4).
 * Build: firmware/build.py (avr-gcc 15.2.0, -mmcu=attiny1616); see firmware/README.md.
 *
 * Layers: hal_avr.c (registers, interrupts) -> fw.c (supervision cycle, hold-up) -> app.c (state
 * machine) with conv.c (measurement conversions) and holdup.c (power-gap logic).
 */
#include "fw.h"

int main(void)
{
    fw_init();
    for (;;) {
        fw_poll();
    }
}
