# Independent pre-order review, 2026-10-27

Reviewer: **Codex (AI review), requested by repository owner**. Reviewed commit
`fab63177bd7086457878a5da7a13dc7cc917e8c3`, following `documentation/pre-order-review.md`.
Scope: evaluation board, 45 × 40 mm, four layers, five assembled prototypes. The compact board remains
DO_NOT_FABRICATE. The owner decides whether this AI review is sufficient and whether to order.

**Recommendation: hold payment pending the footprint dispositions below.** No reversed IC, transistor or
diode was identified in the reviewed mappings. Three evaluation-board reviews are complete; two remain open.
There are also two confirmed release-check defects. Nothing in this review establishes measured electrical
performance or closes Gate G. No circuit, copper, firmware or manufacturing file was changed.

## 1. FP-U1: TPS552882

**Reference:** LEAD-01, TI SLVSFC5, November 2020, pin functions p.3; RPM0026A package p.38,
example board layout p.39 and stencil p.40, drawing 4224618/A (10/2018).

Compared the committed custom footprint, its embedded PCB pads, the footprint report, connectivity and actual
front-copper bridge segments. There are 26 numbered pads. The nominal side pitch is 0.5 mm; the nonuniform
top/bottom locations also match the drawing. Pads 24/25/26 are each 0.375 × 1.425 mm, centred at
x = −0.625/0/+0.625 mm. The side-pad widths, top/bottom lengths, L-shaped corner extents and pin-1 location
match the dimensioned example. The custom corner polygons use square corners rather than TI's typical
R0.05 rounding; no pad-number or nominal-envelope error was found.

The evaluation PCB contains the intended bridges: 9→24 GND, 21→25 SW2, 11→26 VOUT. The SW2 diagonal is
0.25 mm wide, from (100.25, 94.60) to (100.00, 95.35) mm, with 0.30 mm adjoining segments. GND/VOUT use
0.30 mm segments at x = 99.375/100.625 mm between y = 96.00 and 97.40 mm. These are real copper segments,
not an assumption from common net names.

**Result: DONE for the evaluation board's nominal land pattern and connections.** The existing narrow-path
and grounding limitations remain AUD-PCB-01/DD-16. Ask the assembler to review the actual stencil apertures,
0.10 mm stencil example and centre-pad soldering process; inspect U1 joints by X-ray. This is not a thermal,
switching-waveform or assembly-yield sign-off.

## 2. FP-L1: XGL5030 on the XAL5030 footprint

**Reference:** PREORDER-01, Coilcraft document 1576-1, revised 2026-02-19, p.1, recommended land pattern.

The embedded footprint has two 1.18 × 4.70 mm pads, centres at ±1.655 mm, giving 3.31 mm centre separation.
These dimensions match the XGL5030 drawing despite the library name saying XAL5030. The footprint's body
outline is conservative relative to the XGL5030 nominal body. L1 is at (100.75, 90.60) mm, −90°.

**Result: DONE for the evaluation board.** No land-pattern change is needed. Inductor heating and saturation
under the real waveform remain bench checks, not consequences of this geometric match.

## 3. FP-POWERPAK: Q1, Q2, Q3

**References:** PREORDER-02, SiSS23DN document 62852, Rev. A, 2013-05-13, p.1;
PREORDER-03, SiSS80DN document 77684, Rev. C, 2026-10-19, p.1;
PREORDER-04, PowerPAK 1212-8S outline document 63919, 2020-07-20, p.1;
PREORDER-05, recommended minimum pads document 72597, 2008-01-21, p.7.

Pin mapping is correct: 1–3 source, 4 gate, drain terminals combined into footprint pad 5.

| Device | Source | Gate | Drain | Result |
|---|---|---|---|---|
| Q1, P-channel | VBAT | Q1_G | BAT_SPRING | Correct reverse-polarity arrangement |
| Q2 | SW1 | DR1H | VBAT | Correct high-side buck FET |
| Q3 | GND | DR1L | SW1 | Correct low-side buck FET |

The board uses the generic `Vishay_PowerPAK_1212-8_Single` pattern: 0.66 mm pad pitch, source/gate pads
0.99 × 0.405 mm and custom drain extent 2.235 × 2.390 mm. Its provenance is the older generic single-device
pattern. Both selected parts specify **1212-8S**, whose outline has 0.65 mm terminal pitch. The 0.01 mm pitch
difference is small and does not itself prove an unusable footprint. Pin mapping alone does not establish
solder-land compatibility across these package variants.

**Result: OPEN.** Obtain written acceptance of these exact lands for both selected MPNs, or derive a footprint
from the exact 8S package's recommended land pattern and regenerate the board. Include the drain/paste geometry,
not only the four small pads, in the assembler's check. This is part of AUD-PCB-06.

The Q1 datasheet URL in `engineering/design/connectivity.yaml` uses document **62999**; the manufacturer's
SiSS23DN document is **62852**. AUD-DOC-04 records this traceability error. Correct the authoritative field during
the next source/CAD regeneration; do not patch generated schematic/export metadata by hand.

## 4. FP-RS1: Ohmite shunt and Kelvin taps

**Reference:** PREORDER-06, Ohmite MCS series, NEC#11705, PDF p.2 (printed p.16), land-pattern table and diagram;
p.3 identifies MCS1632R010FER. No revision date is printed in the retrieved document.

The MCS1632 is a **two-terminal** component. The board implements four-net Kelvin routing with copper-only
sense pads, not a four-terminal resistor. Pads 1/4 carry VOUT/LD_P; pads 2/3 carry ISP_K/ISN_K. The footprint's
two separate front-copper rectangles join 1–2 and 3–4 locally. Sense pads have no mask or paste openings.
This is consistent with local Kelvin taps and does not create four separate solder joints.

| Dimension, mm | Committed footprint | Ohmite pattern |
|---|---:|---:|
| Each current land length | 1.125 | 1.20 (L2) |
| Each current land width | 1.750 | 1.84 (O) |
| Inner gap | 1.800 | 1.80 (N) |
| Overall span | 4.050 | 4.20, derived from N + 2L2 |

The rectangular land envelopes have about 10.8% less area than the manufacturer's rectangles; the board's
rounded corners reduce actual copper area further. This is a confirmed dimensional deviation, not proof of
failed soldering or insufficient power rating.

**Result: OPEN, AUD-PCB-06.** Preferred remedy: use 1.20 × 1.84 mm current lands centred at ±1.50 mm, preserving
the 1.80 mm gap and the separate sense taps. Review mask, paste, courtyard, neighbouring clearances and current
entry before regeneration. Alternatively, obtain explicit assembler acceptance of the existing geometry.
Verify current accuracy after assembly; Kelvin traces do not eliminate the resistor's own terminal/solder effects.

## 5. ORIENT: drawing, iBOM and centroid

**References:** LEAD-01 and PREORDER-02/03 above; PREORDER-07 INA186 SBOS318B, July 2021, p.3;
PREORDER-08 Microchip DS40002204A, 2020, pp.16/18 (pinout), pp.576–578 (VQFN);
LEAD-04 DMG1012T DS31783 Rev.8-2, February 2022, p.1;
PREORDER-09 PMEG4010CEJ, 2022-10-01, p.1;
PREORDER-10 RB521S30T1/D Rev.12, October 2024, p.1;
PREORDER-11 BZX585 series Rev.9, 2026-09-11, p.1.

Rendered and inspected `assembly_top.pdf`, decoded the iBOM data, and compared the PCBWay centroid. All 52
placed parts have matching centres, rotations modulo 360° and top-side designation between iBOM and CPL.
The coordinate conversion is x_CPL = x_PCB − 100, y_CPL = 100 − y_PCB. The JLCPCB CPL agrees too.

Directions below refer to the top view of the assembly drawing, with its title upright.

| Ref | CPL rotation | Pin 1 / cathode location | Mapping checked |
|---|---:|---|---|
| U1 | 0° | Upper left | DR1L; centre-pad map as section 1 |
| U2 | 0° | Upper left | REF; IN+ = ISP_K, IN− = ISN_K |
| U3 | 0° | Upper left | PA2; VDD pin 4, GND pin 3 and exposed pad |
| Q1, Q2 | 180° | Lower right | Source pins 1–3; gate 4 |
| Q3 | 0° | Upper left | Source pins 1–3; gate 4 |
| Q4, Q5, Q6 | 0° | Upper left | Gate 1, source 2, drain 3 |
| D1 | 90° | Cathode at bottom | Cathode LD_P; anode GND |
| D2 | 0° | Cathode at left | Cathode VMCU; anode VBAT |
| D3 | 0° | Cathode at left | Cathode VOUT; anode OV_G |

**Result: DONE for evaluation-board pin numbering, polarity and exported orientation.** The supplier must
still show a placement preview with its feeder/library rotation convention before assembly approval.

**Additional land-pattern deviation, AUD-PCB-06:** U3's nominal pad pitch and package are correct, but the board
uses a 1.70 × 1.70 mm exposed land and 2.90 mm opposing pad-centre spacing. Microchip's recommended pattern on
p.578, drawing C04-23380 Rev.A, specifies 1.80 × 1.80 mm and 3.00 mm respectively. The peripheral pads match
0.80 × 0.20 mm. This is not an orientation failure and does not prove the footprint cannot be assembled.
Include this difference in DFM disposition; either obtain acceptance or update the footprint and regenerate.

## 6. Confirmed release-check defects

### AUD-VAL-11: required reviews disappear when records are removed (high, OPEN)

`automation/export/release_check.py:review_blockers()` only iterates the supplied list. It never asserts the
presence of FP-U1, FP-L1, FP-POWERPAK, FP-RS1 and ORIENT for each applicable variant/level. Empty lists, wrong
scope/level and non-dictionary records are silently skipped. In an isolated temporary directory:

```text
reviews: []                                      -> [] blockers
FP-U1 removed, remaining records synthetically DONE -> [] blockers
```

This is a bypass of the review component of the gate, not proof the complete release gate passes without CAD,
firmware and other evidence. The real register was not cleared during reproduction.

**Solution:** define required IDs independently of the editable records, validate schema, require exactly one
applicable record per ID, and reject absent/malformed/duplicate records. Test empty, missing, duplicate,
wrong-variant and wrong-level cases for prototype and DFM reviews.

### AUD-VAL-12: completed reviews are not tied to the reviewed artifacts (high, OPEN)

The same function checks only `status`, truthy `reviewer`, `date` and `evidence`. It does not hash or inspect the
reviewed PCB, footprint, BOM, CPL or drawing. A synthetic DONE register still returned no review blockers after
changing a synthetic PCB file. Existing CAD/export freshness checks do not fix this: after legitimate CAD
regeneration, the old DONE review survives. Final manufacturing approval hashes do not protect the earlier
PROTOTYPE_CANDIDATE review gate.

**Solution:** store and verify per-review dependency hashes, including the embedded footprint/PCB and relevant
assembly artifacts. Invalidate only affected reviews when inputs change. Require date format and structured
source evidence. Add a test proving a real dependency change reopens the review. This report records the exact
baseline and artifact hashes below as interim traceability; the current checker does not enforce them.

## 7. Ordering files and electrical decisions

- PCBWay BOM: 29 SMT part lines / 52 placements plus one explicitly DNS hand-fitted spring line. JLCPCB: 29
  BOM lines / 52 placements. All 13 common Gerber/drill members are byte-identical. PCBWay additionally includes
  two drill-map PDFs and the Gerber job file; those omissions from the JLC ZIP are intentional.
- Order the evaluation package only. Keep four layers, 1.6 mm, 1 oz copper on **all four layers**, ENIG and
  top-only assembly. Confirm the actual stack-up and DFM review, X-ray of U1/U3, and no unreviewed substitutions.
  Live stock, prices, assembly acceptance and lead times remain UNKNOWN; only 9/29 JLC BOM rows have LCSC IDs.
- **R16, existing AUD-SRC-04:** 220 Ω at a 4.2 V short dissipates 80.2 mW versus the evaluation BOM's 62.5 mW
  rating. I recommend resolving this before ordering. A 470 Ω candidate gives 37.5 mW at 4.2 V; verify LED
  brightness, temperature derating and tolerance. A suitably rated larger package is another option but needs
  layout regeneration. This is a wiring-fault risk, not normal LED dissipation.
- **R4, existing AUD-SIM-04:** the saved tolerance sweep has 9.5 dB gain margin against 10 dB. The existing
  exploratory 1.0 kΩ result is 11.1 dB. Either formally accept the prototype risk with loop/transient testing or
  validate the 1.0 kΩ change across the full simulation set before regeneration. These are averaged-model
  results, not measured stability margins. Do not silently swap a BOM value without rebuilding evidence.
- **Q6, existing AUD-PCB-04:** ±6 V gate rating with an unclamped Zener-drive path is vulnerable in the documented
  multiple-fault case. Review a gate-source clamp whose tolerance remains below the rating while retaining the
  required turn-on voltage and acceptable Zener current. No clamp value is approved by this review.
- Existing evaluation-board switch-node/grounding limitations and roughly 94.11% estimated efficiency leave
  little margin over 94%. Dummy-load bring-up, current accuracy, overshoot, thermal, interlock/fault response,
  firmware timing and efficiency measurements remain required. Compact-board routing remains incomplete.

## 8. Validation actually performed

| Check | Result |
|---|---|
| Retrieved repository fidelity | All 356 baseline files matched their Git blob hashes |
| `python3 -m pytest tests -q` | 188 passed, 19 skipped (KiCad unavailable) |
| `python3 firmware/build.py --host-only --mutation` | Six suites, 531 checks; 15/15 mutants killed |
| `python3 automation/validation/validate.py --mode fast` on baseline | Exit 0; 55 entries; three known unchanged failures; zero new/changed failures |
| Fresh KiCad ERC/DRC, ngspice and AVR target build | Not run here: tools unavailable |
| Committed full-tool evidence | Evaluation ERC/DRC 0/0/0/0; compact 20 unconnected and three warnings |
| GitHub CI | Run [40500901442](https://github.com/djgringoboy2003/Nub44-driver/actions/runs/40500901442) succeeded on `4f608a996b127f1f97af13b1cab88a75bd088dcf`, parent of the reviewed docs-only commit |

After updating the review records, the full Python suite again passed 188 tests with 19 skips. One test fixture
was corrected to explicitly reset its synthetic review states, rather than assuming the real register stays OPEN.
Fast validation was rerun: exit 0, 55 entries, three unchanged known failures, no new/changed failures. Evaluation
remained DRAFT_REVIEW with three local blockers (two open reviews and the unavailable target build).

Fast validation does not establish order readiness. On the baseline it reports DRAFT_REVIEW, with five open
reviews and an unavailable local target build. After this review, FP-POWERPAK and FP-RS1 remain open for the
evaluation board, plus the U3 land-pattern DFM disposition recorded above. The compact reviews remain OPEN.
Saved full-run reports are retained; they predate these review-register updates and must be regenerated with
the complete toolchain after fixes/dispositions. No generated evidence was hand-edited to turn a failure green.

## 9. Exact package reviewed and next steps

SHA-256 values for the baseline:

| Artifact | SHA-256 |
|---|---|
| Evaluation PCB | `4ad92aefaaab987519aa7aa8424daf0849c4ea27f0b75fd592ea5f5de8e972c8` |
| Connectivity source | `014683a41ef2a722bf12220071c5bd83dea44e9c400736aac224241645fe8dab` |
| PCBWay Gerber ZIP | `e9cb87475001c9af95898825c72bc1b08eb560b960fb0c426588bb023ec192ff` |
| PCBWay BOM | `411651d84dda8953053ec9d4837da5ba1c5891a6c1323757e39a52613bcca329` |
| PCBWay CPL | `e0839e0f5e6b08297597fc8b3241f2009648a12186d397710e78e038136c11b4` |
| iBOM | `538312ca11e1cc42a6d4112688e107c42e030920b36a2d299ac81976d7f7fbe5` |
| Assembly top PDF | `c9422d4ad1336b758886779f35e79124261b039ad9db2742ec417aee6052edc6` |

1. Resolve RS1, U3 and exact PowerPAK-8S lands with corrected CAD or written DFM acceptance. Address R16 and
   decide R4/Q6 changes before producing another package.
2. Fix AUD-VAL-11/12 and the Q1 source link. Regenerate all affected schematic, board, DRC, manufacturing and
   evidence outputs through the repository's full pipeline. Re-review changed artifacts.
3. Run full validation, record the remaining reviews against the exact final hashes, and obtain the supplier's
   parts/stack-up/stencil/placement confirmation. The owner then decides whether to order five evaluation boards.
4. Bring up on a rated dummy load and record physical results in Gate G before connecting the intended load.

Manufacturer links and revisions are indexed as PREORDER-01…11 in `research/source-index.md`.
