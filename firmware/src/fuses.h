/*
 * Required ATtiny1616 fuse values (single source; audit AUD-FW-16).
 *
 * Fuses are programmed by hand on the bench (firmware/README.md, test plan T0.4); the firmware reads them
 * at start-up and latches FAULT_CONFIG (blink code 15) if they differ, because every timer assumes the
 * 20 MHz oscillator and the hold-up mode memory needs brown-out detection.
 *
 * BODCFG (fuse offset 1): LVL[7:5] = BODLEVEL0 (1.8 V, DS40001997C Table 37-12), SAMPFREQ[4] = 1 kHz,
 *                         ACTIVE[3:2] = enabled, SLEEP[1:0] = sampled (lower hold-up current).
 * OSCCFG (fuse offset 2): FREQSEL[1:0] = 20 MHz, OSCLOCK = 0 (the main clock divides it by 4: 5 MHz).
 */
#ifndef FUSES_H
#define FUSES_H

#define FW_FUSE_BODCFG          0x06u
#define FW_FUSE_OSCCFG          0x02u
#define FW_FUSE_OSCCFG_MASK     0x03u   /* FREQSEL; OSCLOCK is not required */

#endif
