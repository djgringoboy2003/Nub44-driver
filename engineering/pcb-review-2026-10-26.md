# Independent PCB review, 2026-10-26

Part of the comprehensive audit (`reports/comprehensive-project-audit.md`, AUD-PCB-01…05). Numbers come from the
generated layout reviews (`reports/layout-review-<variant>.md`, regenerated on 2026-10-26 from the committed copper)
and from `engineering/compact-feasibility.md`. No CAD file was changed in this review: every option below needs a
new router session (and the full regeneration chain in AGENTS.md), and several change hardware, which needs the
owner's approval.

## 1. Evaluation board (45 × 40 mm, DRC 0/0/0/0)

The earlier dispositions in `engineering/layout-review.md` were re-checked against the copper data. They are
consistent with it. The assessment below adds an independent view of risk and of whether to act before the first
prototype order.

| Item | Measured (layout review) | Assessment | Options and trade-offs | Act before the first order? |
|---|---|---|---|---|
| **DR1H via beside the SW1 junction** | SW1 neck 1.30 mm equivalent (x2.43 of the IPC-2221 long-trace screen) at Q2 pad 3; DR1H loop 12.3 mm² against SW1, 11.0 mm route, 2 vias | SW1 carries the full inductor current (7.4 A worst point). The neck is short and spreads heat into the pour; the loss is in the 96 mW copper allowance. DR1H drives Q2, which only switches in the buck/transition region (full cell with a low-Vf diode); in boost mode Q2 is held on. | Move the via 0.6–1 mm off the junction and widen the SW1 pour: needs a new router session for DR1H and the nearby GND fanout; risk of new DRC findings near Q2/Q3. Gain: about 0.1–0.2 mΩ and a smaller gate loop. | No. Measure SW1 temperature (T2.7/T2.12) and DR1H/SW1 ringing (T2.9) first. |
| **U1 ISP/ISN routing** | ISP on In2 under ISN on F.Cu: 7.5/6.0 mm more than 1 mm apart, about 14 mm² enclosed | DC accuracy is unaffected (no current flows). The loop is a magnetic pickup: with SW2 edges of order 10^9 A/s and roughly 1 nH of mutual coupling (order-of-magnitude estimate), nanosecond spikes of hundreds of mV are possible across a 50 mV sense threshold. The ISP/ISN loop is slow (TI: "average" limit), so false limiting is unlikely, but a noisy **CC flag** would latch FAULT_OVERCURRENT (fault 6) in the firmware. The INA186 branch that regulates the current is a tight same-layer pair. | Route ISP_K/ISN_K as a same-layer pair from the shunt's sense pads to U1: new router session for FB and the sense nets. | No, but watch for nuisance fault 6 on the bench (T1.10, T2.4, T2.11). If it appears, re-route before the second spin. |
| **C5 (BOOT1) placement** | BOOT1 route 15.2 mm, 2 vias, loop 18.3 mm² against SW1 (largest drive loop) | Same switching region as DR1H. Large bootstrap loops cause high-side gate ringing and slower edges (more switching loss) in buck/transition only. | Move C5 next to U1 pins 22/23: blocked by L1/U1 courtyard spacing (0.12 mm); would need U1 or L1 to move, i.e. a re-placement of the power stage. | No. Covered by T2.9 (DR1H, SW1 waveforms at 4.2 V with a low-Vf load). |
| **VCC (C7) routing** | 7.8 mm through In2 and 2 vias; loop area 1.5 mm² against the ground plane | Acceptable: the In2-over-ground geometry keeps the loop area small even though the route is long. VCC supplies all gate drivers; its ripple is the item to measure. | Put C7 at pin 19: trades against BOOT2 (C6) loop area in the same corner. | No. T2.10 measures VCC ripple. |
| **SW2 entry** | 0.75 mm equivalent width at U1 pin 21 (x4.2 of the screen) | Package-limited (DD-16): the inductor current enters through one 0.25 mm pin plus the bridged centre pad. Local heating at the pin is the risk; U1's own power dissipation adds to it. | HDI via-in-pad on the RPM0026A centre pads (DD-16); not available on the standard 4-layer process. | No (cannot be fixed without HDI). T2.7/T2.12 thermal image of U1's top edge. |
| **AGND/PGND coupling** | +11 mA (+0.28 %) DC setpoint shift at the worst point | Inside the ±5 % budget (stack 3.58 % + 0.28 %). AC coupling of PGND noise into AGND is UNKNOWN. | Separate AGND net with a net tie at C7, combined with HDI (DD-23). | No. T2.11 compares measured current with CS. |
| **Package-limited heat dissipation** | U1 junction estimate 97 °C at 50 °C board (60 K/W assumed; CALC-12) | The 60 K/W figure is an assumption for a board without thermal vias under the IC; it is the most uncertain thermal number in the design. | HDI via-in-pad; or reduce losses (lower setpoint is an owner decision, DD-13). | No. T2.7 is the deciding measurement; the firmware board limit (85 °C) and the IC's 175 °C shutdown are backstops. |

Other items worth noting:
- **Test-point and programming access:** 13 labelled test points including VBAT, VOUT, EN, CS, FB, UPDI, VMCU and GND
  (REQ-TEST-01). SW1/SW2 and VCC have no test pads; T2.9/T2.10 need a ground-spring probe directly on the parts.
  A future spin could add small SW2/VCC probe pads.
- **Assembly and inspection:** U1 (VQFN-HR, 0.5 mm pitch, bridged centre pads) and U3 (VQFN-20) need X-ray or careful
  microscope inspection (T0.1). The custom U1 land pattern and the L1 land-pattern assumption are now explicit
  PROTOTYPE_CANDIDATE review blockers (FP-U1, FP-L1 in `engineering/release/design-reviews.yaml`).
- **High-current vias:** the VOUT column via carries 1.68 A (screen 1 A); barrel loss about 3 mW. Acceptable.

**Recommendation:** order the evaluation prototype with the current copper once the five human reviews are recorded,
and treat the measurements above (T2.7, T2.9–T2.12, and nuisance-fault observation for ISP/ISN) as the input for any
second spin. Re-routing before the first order would spend a router session on effects the bench has not shown.

## 2. Compact board (Ø 22 mm): strategy

**Current state:** 20 unconnected items (mostly MCU signals), 0 DRC errors, every power path connected. The limit is
via capacity: a through via needs free copper on F.Cu, In2 and B.Cu at once, the centre spring pad forbids vias within
2.95 mm of the centre, and the router found only about 15 mm² of legal via area, none beside the MCU. Pin swaps and
finer inner lines were simulated and did not finish the board (`compact-feasibility.md`). Re-running the same router
without changing the problem will not help.

**Findings from this audit that change the inputs:**
- **PG is unused by the firmware** (it was never read; DD-28 now leaves the pin without a pull-up). Removing the
  PG-to-MCU net from the compact variant removes one of the 20 open items with no functional loss.
- The **optional switch input (SW_IN)** duplicates the click mode change; dropping it on the compact variant removes
  another open item (owner choice).
- These two reductions alone do not finish the board (about 18 would remain); they lower the demand for any of the
  directions below.

| Direction | What changes | Routing effect | Fabrication complexity and cost | Reliability | Thermal | Main risk |
|---|---|---|---|---|---|---|
| **A. HDI: blind/laser microvias, via-in-pad** | Stack-up with laser vias F↔In1 and B↔In2; U1 centre pads get via-in-pad (DD-16) | Removes the "free on all layers" condition; via sites beside the MCU become available; U1 escapes shrink | Highest: HDI process, filled/capped vias; cost UNKNOWN until quoted (PCBWay offers HDI, MFG sources) | Good if filled and capped; microvia reliability depends on the fabricator | Best: thermal vias under U1 (fixes NECK-SW2 and the package-limited items) | Cost and lead time |
| **B. 6-layer through-via** | Two more inner signal layers; same via technology | More routing tracks per via site, but the via-site scarcity near the MCU remains; may finish if the bottleneck is track capacity rather than via sites (simulation suggests via sites dominate) | Moderate: standard 6-layer, PCBWay standard process | As now | Better heat spreading (more copper) | May still not finish; needs a grid-router study on a 6-layer copy |
| **C. Placement re-architecture (4-layer)** | MCU and harness pads on the top side; plated harness pads that double as layer changes; fewer bottom test pads | Creates via sites where the MCU needs them | Standard process, lowest cost | As now | As now | Large CAD effort; power column (L1 over the spring, U1 below) must be preserved |
| **D. Fewer parts on the compact variant** | Drop PG (unused) and SW_IN; consider moving the NTC and indicator circuits to the harness | Each removed net frees a corridor; at most a few items | None | Slightly better (fewer joints) | None | Function loss is an owner decision |
| **E. Two-board stack** | Power board (converter, shunt, spring/ring) and control board (MCU, enable chain) joined by pins | Each board has room to route | Two boards, board-to-board pins, assembly step | Interconnect is a new failure point | Splits heat sources | Height in the host |
| **F. Larger diameter** | Brief requires 22 mm | Solves it | None | As now | Better | Owner/brief change |

**Recommendation (for the owner's decision after the evaluation bench data):**
1. Apply the low-risk reductions (D: PG, and SW_IN if the click mode change suffices) in any direction.
2. Obtain PCBWay quotes for A (HDI, including via-in-pad for U1) and B (6-layer) for the 22 mm outline.
3. Before committing CAD effort to B or C, run the grid router's legality map on a 6-layer copy and on a top-side
   MCU placement copy (a different problem, so a meaningful new run), and compare the remaining open items.
4. Choose A if the thermal bench data (T2.7/T2.12) show U1 running hot on the evaluation board: HDI fixes both the
   routing and the package-limited thermal path.

All of this stays a routing draft until then (DD-27); Gates D/E/F remain open for the compact board and its export
carries the DO_NOT_FABRICATE marker.
