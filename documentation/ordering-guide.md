# Ordering guide: evaluation board at PCBWay or JLCPCB

For the owner placing the prototype order by hand. No tool in this repository uploads files or places orders.

> **Status on 2026-10-27:** the evaluation board is **DRAFT_REVIEW** (`reports/release-readiness.md`). Its CAD is
> complete (DRC 0 errors, 0 warnings, 0 unconnected, 0 parity). Uploading for a **quote and DFM review** is fine now.
> Before **paying**, record the five human reviews in `engineering/release/design-reviews.yaml` (FP-U1, FP-L1,
> FP-POWERPAK, FP-RS1, ORIENT); the data to compare is in `reports/footprint-review.md`, and the review brief is
> `documentation/pre-order-review.md`. FP-U1 (the TPS552882 land pattern generated from the datasheet's vector
> geometry) matters most: a wrong land pattern means every board is scrap.
>
> Never order the compact 22 mm board: its package is classed DRAFT_REVIEW_INCOMPLETE_BOARD and its ZIP carries
> `DO_NOT_FABRICATE.txt`.

## 1. Which fab

| | PCBWay | JLCPCB |
|---|---|---|
| Bare boards | Yes | Yes |
| Assembled boards | **Preferred.** BOM and centroid are already in PCBWay's template format; turnkey sourcing from global distributors | Possible: JLC-format BOM/CPL provided; parts come from LCSC or JLC global sourcing/consignment |
| Parts not confirmed at LCSC (2026-10-24) | Sourced by PCBWay | U1 TPS552882RPMR, Q2/Q3 SiSS80DN (JLC stock 0), RS1 MCS1632R010FER: global sourcing or consign |
| Upload folder | `manufacturing/pcbway/evaluation-board/` | `manufacturing/jlcpcb/evaluation-board/` |

Stock and prices in this repository are from 2026-10-24 or UNKNOWN. Confirm every line at quote time. Accept no
substitute part without a review: the listed PowerPAK alternates have different land patterns, and the alternate shunt
has not been reviewed.

## 2. Files

| Purpose | PCBWay | JLCPCB |
|---|---|---|
| Fabrication (Gerber + drill) | `evaluation-board-gerbers.zip` | `evaluation-board-jlcpcb-gerbers.zip` (same Gerber/drill bytes, flat, no PDFs) |
| Assembly BOM | `assembly/BOM_PCBWay_template.csv` | `BOM_JLCPCB.csv` (29 lines; JLCPCB part numbers filled for 9, match the rest by MPN) |
| Assembly placement | `assembly/CPL_PCBWay.csv` | `CPL_JLCPCB.csv` |
| Orientation reference | `drawings/assembly_top.pdf`, `assembly/ibom.html` | the same files from the PCBWay folder |

Both folders are regenerated and hash-checked by the tools (`export_pcbway.py`, `export_jlcpcb.py`, `validate.py`).
Re-run the export if any CAD source changes; never edit the files by hand.

## 3. Layer order (both fabs)

| Layer | File | Contents |
|---|---|---|
| L1 (top) | `nubm44_driver-F_Cu.gtl` | Top copper: all components, power pours, signals |
| L2 | `nubm44_driver-In1_Cu.g1` | Inner 1: solid ground plane |
| L3 | `nubm44_driver-In2_Cu.g2` | Inner 2: power copper, ground fill, some signals |
| L4 (bottom) | `nubm44_driver-B_Cu.gbl` | Bottom copper |

Other files: top/bottom solder mask `.gts`/`.gbs`, top/bottom silkscreen `.gto`/`.gbo`, top/bottom paste
`.gtp`/`.gbp` (bottom paste is empty), outline `.gm1`, plated holes `nubm44_driver-PTH.drl`, non-plated holes
`nubm44_driver-NPTH.drl`. The order matches the Gerber job file KiCad wrote (`gerbers/nubm44_driver-job.gbrjob`).

## 4. Board options

The requirement column comes from the design (DD-14, `documentation/stack-up.md`, KiCad design rules). The setting
names follow the fabs' order forms as of 2026; if a form differs, the requirement is what must be met.

| Requirement | PCBWay setting | JLCPCB setting |
|---|---|---|
| 4 copper layers | Layers: 4 | Layers: 4 |
| 45 × 40 mm, single board | Board type: single pieces; size 45 × 40 mm | Dimensions 45 × 40 mm; delivery format: single PCB; different designs: 1 |
| Quantity | 5 (minimum) | 5 (minimum) |
| FR-4 | FR-4; TG 150-160 recommended (TG 130-140 acceptable) | FR4; TG 155 recommended (standard TG acceptable) |
| 1.6 mm finished thickness | Thickness 1.6 mm | PCB thickness 1.6 mm |
| 1 oz on every layer (the copper-loss analysis assumes it) | Finished copper 1 oz; **inner copper 1 oz** | Outer copper weight 1 oz; **inner copper weight 1 oz** (not 0.5 oz) |
| ENIG (flat pads for the 0.4/0.5 mm pitch QFNs) | Surface finish: immersion gold (ENIG) | Surface finish: ENIG |
| 0.15 / 0.15 mm track/space (6/6 mil) | Min track/spacing 6/6 mil | Standard capability (no option to set) |
| 0.3 mm min drill, 0.6 mm vias, none in pads | Min hole size 0.3 mm; via process: tenting vias | Min via hole size/diameter: default (0.3 mm); via covering: tented |
| No controlled impedance | Impedance control: no | Impedance control: no |
| Standard 4-layer stack | Default 1.6 mm 4-layer stack (7628 prepreg, as DD-14 assumed) | Specify stack-up: the 7628-prepreg option (closest to DD-14); dielectric thickness then differs slightly, which is acceptable without impedance control |
| Legible B+ / B- polarity labels | Solder mask green, silkscreen white | Colour green, silkscreen white; **remove order number: specify a location** (or remove) so the marking does not cover the labels |
| Electrical test | 100 % E-test (flying probe) | Electrical test: flying probe, fully tested |
| No special features | No gold fingers, castellations, edge plating, blind/buried vias | Gold fingers no; castellated holes no; edge plating no |
| Fabricator check | Request engineering confirmation of the files before production | Confirm production file: yes |

Bare boards only: order a **top-side stencil** (all parts are on the top; the bottom paste layer is empty).

## 5. Assembly options

| Item | PCBWay | JLCPCB |
|---|---|---|
| Service | Turnkey assembly | Standard PCBA (economic PCBA restricts parts and options) |
| Sides | Top only | Assembly side: top |
| Parts | 29 unique parts, 52 SMD placements, 0 through-hole | Same |
| Boards to assemble | All 5, or at least 3 (one may be lost in fault tests) | PCBA quantity: at least 3 |
| Not placed | J1 (battery wire pad; listed as DNS in the template) | J1 is omitted from `BOM_JLCPCB.csv` |
| Inspection | Request **X-ray of U1 and U3** (VQFN; U1 has bridged centre pads, DD-16) | Request X-ray of U1 and U3 if offered; photo confirmation yes |
| Orientation | Ask PCBWay to confirm pin 1 of U1, U2, U3 and the orientation of D1-D3 and Q1-Q6 against `assembly_top.pdf` | **Confirm parts placement: yes**, and check every part in JLC's placement preview: rotations are KiCad's, and JLC's library orientation differs for some packages |
| Substitutions | "Do not substitute without approval" | Reject automatic substitutions; global-source or consign U1, Q2, Q3, RS1 |
| Programming | None (firmware and fuses are programmed on the bench, `firmware/README.md`) | None |
| Tooling holes, rails | Fab's choice | Added by JLCPCB |

## 6. Before you pay

Follow `documentation/release-checklist.md` section A. In short:
- [ ] The five human reviews recorded; `validate.py` shows the evaluation board at **PROTOTYPE_CANDIDATE**.
- [ ] Quote reviewed: options as above, especially **inner copper 1 oz** and **ENIG**.
- [ ] Stock confirmed for U1, Q1-Q3, L1, RS1, U3; no unreviewed substitutes.
- [ ] Fab's DFM or placement preview checked for pin 1 and polarity.
- [ ] The open owner decisions in PROGRESS.md taken or knowingly deferred. R4 (a possible 1.2 → 1.0 kΩ loop change)
      is an 0402 that can be swapped by hand later, so it need not delay the order.

## 7. After ordering

- Record the order (date, fab, order number, SHA-256 of the uploaded ZIP) in PROGRESS.md.
- Bring-up: `documentation/assembly.md`, then the bench plan with a rated dummy load; record every test with
  `automation/bench/bench.py`. Never connect the laser diode before the dummy-load stages pass.
