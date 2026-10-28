# Project 450: ideas for this driver

Reviewed 2026-10-28 by Codex (AI review), requested by owner. Proposals only; no design, firmware,
component, footprint or release-status change. Sources P450-01/02/03 are registered in
[source-index.md](source-index.md).

[Loneoceans Project 450](https://www.loneoceans.com/labs/project450/) is a useful reference for thermal
integration and controls. Its 2018–2019 build uses two cells in series and a TPS56C215 synchronous buck
converter; the author reports operation with a NUBM44-V2 at 4.5 A. These are the author's observations,
not measurements of our board. Our approved setpoint remains 4.0 A (DD-13).

| Idea | What the page describes (P450-01) | Assessment for this repository |
|---|---|---|
| Conduct heat into the enclosure | One-sided components, underside ground contact areas, insulation and an aluminium baseplate; the diode block also attaches to it. | The most useful mechanical idea. REQ-PCB-01 already covers thermal copper, but a real copper-to-host interface needs a mechanical design, electrical isolation review and measured temperatures. Keep live pads and switching nodes clear of metal; account for both the driver's losses and the diode mount. Do not expose copper or assume a safe continuous duty from the article alone. |
| Deliberate arming | A switch-code unlock. | A possible usability improvement if the intended controls support it. Preserve default-off, the existing independent interlock and fault latch. A code is an additional control; it cannot establish hardware safety. Specify reset, brownout and power-gap behaviour before proposing firmware changes. |
| Gentler startup | A roughly 200–250 ms soft-start target. | First measure our current ramp and overshoot at T1.3 and every mode restart at T1.8. TPS552882 has a fixed 4 ms soft start (P450-03); editing `soft_start_s` would change the model only. The MCU currently enables the converter; R8/R9 set current. A programmable current ramp needs a separately designed control path and loop/fault validation. |
| Useful diagnostics | Battery cut-off, programmable current modes and LED error indications. | Battery monitoring, emission delay and fault indications already exist in our firmware. Distinct current levels would be a new feature: current firmware modes alter timing, while changing the static maximum needs the documented R8 option. Keep indications understandable before adding more modes. |
| Charging inhibition | An MCU interlock prevents emission while charging. | Sensible if charging is ever added. The present brief has no integrated charger. Define hardware inhibit, cell protection and thermal behaviour first; do not add the article's two-cell charging circuit to the present board. |
| Layout and magnetics | Close input capacitors, quiet feedback and a larger, lower-loss inductor option. | These reinforce the existing layout review. Size L1 for our topology, peak/RMS current, inductance, bias, DCR and available volume. The article's XAL7030/7070 parts are not qualified replacements for XGL5030-102MEC. Larger parts would require placement/routing changes; no saving is established. |

The topology is the main limit on reuse. TI's current
[TPS56C215 Rev. H datasheet](https://www.ti.com/lit/ds/symlink/tps56c215.pdf) identifies an 18-pin
step-down converter and 4.5 V startup without external bias (P450-02). Our input reaches 4.2 V fully
charged and falls to about 2.83 V; specified output compliance reaches 5.2 V. A buck cannot supply that
range from one cell. Its package/pinout also differs from the present 26-pin TPS552882. This is not a
straight swap. Two-cell operation could justify a future buck architecture study, but changes the battery,
host, protection and charging requirements. Complete GBP cost and any saving are UNKNOWN.

Use the article as engineering inspiration, with manufacturer documents setting component limits. The
retrieved page still has a schematic placeholder, and its inspected links do not provide downloadable
project schematic, PCB or firmware files. Exact feedback implementation and full fault behaviour are
therefore UNKNOWN from this source. Historical prices, simulated efficiency and the author's reported
optical output do not validate our cost, efficiency, output rating or lifetime. Retain dummy-load bring-up,
the existing bench plan, and X-ray inspection of U1/U3.

Recommended sequence: resolve the existing PowerPAK/RS1/U3 manufacturing questions; assemble and measure
the evaluation board; then assess a defined host/heatsink interface. Consider arming and adjustable-current
features only against a concrete use case. Any adopted electrical, component or footprint proposal needs
an owner decision, a design-decision entry and the full AGENTS.md regeneration/review chain. Gate G remains
OPEN until our own measured evidence satisfies the bench criteria.
