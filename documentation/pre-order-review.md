# Pre-order review brief (evaluation board)

For the independent reviewer (Codex or a person) asked to check the evaluation board before the owner orders
prototypes. Read [AGENTS.md](../AGENTS.md) first; its rules apply (never invent data, never hand-edit generated
evidence, never place orders).

## 1. What is being ordered

- The **evaluation board** (Variant B, 45 × 40 mm, 4 layers), 5 boards, assembled top side only (29 parts, 52
  placements), at PCBWay (preferred) or JLCPCB. Files and fab options: [ordering-guide.md](ordering-guide.md).
- Not the compact 22 mm board: it is an incomplete routing draft and its package says DO_NOT_FABRICATE.

## 2. Reproduce the current evidence (Windows, after `scripts\setup.ps1`)

```powershell
.venv\Scripts\python.exe -m pytest tests -q                        # expect all pass
.venv\Scripts\python.exe firmware\build.py --mutation               # expect PASS, 15/15 mutants killed
.venv\Scripts\python.exe automation\validation\validate.py          # expect exit 0, 3 known items, both boards DRAFT_REVIEW
```

Without KiCad, ngspice or avr-gcc (for example on Linux): `validate.py --mode fast`. CI runs the same in
`.github/workflows/ci.yml`. Generated status: `reports/dashboard/index.html`, `reports/validation-register.md`,
`reports/release-readiness.md`.

## 3. Review tasks that block the order (record each in `engineering/release/design-reviews.yaml`)

The geometry for every item is tabulated in [reports/footprint-review.md](../reports/footprint-review.md)
(regenerate with `automation/review/footprint_report.py`).

| ID | Check | Reference |
|---|---|---|
| FP-U1 | TPS552882 RPM0026A land pattern: 26 pads, sizes, 0.5 mm pitch, the three centre pads 24/25/26, pin 1, and that pins 9/21/11 bridge to centre pads 24/25/26 as intended (DD-16) | TI SLVSFC5, package and example layout pages (local copy `research/datasheets/pwr_tps552882_slvsfc5.pdf`, git-ignored; public URL in `research/source-index.md` LEAD-01) |
| FP-L1 | XGL5030-102MEC terminals fit KiCad's XAL5030 land pattern | Coilcraft XGL5030 datasheet (LEAD-05) |
| FP-POWERPAK | PowerPAK 1212-8 pads 1-3 source, 4 gate, 5 drain; Q1 (P-channel) drain on BAT_SPRING, source on VBAT; Q2/Q3 nets | Vishay SiSS23DN / SiSS80DN datasheets |
| FP-RS1 | Kelvin 1206 shunt: current pads 1/4, sense pads 2/3 joined only at the resistor | Ohmite MCS1632 datasheet (LEAD-07) |
| ORIENT | Pin 1 / polarity of U1, U2, U3, D1-D3, Q1-Q6 in `manufacturing/pcbway/evaluation-board/drawings/assembly_top.pdf`, the iBOM and the centroid rotations | the parts' datasheets |

To record a review, set `status: DONE` with `reviewer`, `date` and `evidence` (document, revision, page, what was
compared and the result). A reviewer that is an AI agent must say so in `reviewer` (for example
`Codex (AI review), requested by <owner>`); the owner decides whether that is sufficient. If a footprint is wrong,
do not mark it DONE: record the discrepancy and stop; the fix needs a CAD change and the full regeneration chain.

After recording, `validate.py` should report the evaluation board at PROTOTYPE_CANDIDATE.

## 4. Further review welcome (does not block the order)

- **Ordering files:** `manufacturing/pcbway/evaluation-board/` and `manufacturing/jlcpcb/evaluation-board/` against
  the options in the ordering guide (layer order L1 `.gtl`, L2 `.g1`, L3 `.g2`, L4 `.gbl`; inner copper 1 oz; ENIG).
- **Circuit:** the hardware enable chain (Q4 MCU, Q5 interlock, Q6 over-voltage Zener) on EN/UVLO, the UVLO divider
  (3.08/2.83 V), the reverse-polarity P-FET, the FB divider for 4.0 A; `engineering/design/connectivity.yaml`,
  `engineering/calculations/power-stage-results.md`, DD-02 to DD-06.
- **Firmware (DD-28):** `firmware/src/`; the hardware assumptions still unverified on the bench are listed in
  `firmware/README.md` ("Not yet verified").
- **Open owner decisions** (opinions welcome; none changes this order's files): AUD-SIM-04 / VAL-SIM-12 loop gain
  margin (R4 1.2 → 1.0 kΩ option), AUD-SRC-04 R16 rating, AUD-PCB-04 Q6 gate clamp. Details:
  `reports/comprehensive-project-audit.md`, `engineering/pcb-review-2026-10-26.md`.
- **Known limitations** (accepted): `engineering/known-limitations.yaml`, PROGRESS.md "Open limitations".

## 5. How to report

Write findings to `reports/pre-order-review.md` (one section per item: what was checked, against which document and
page, result, and any defect with its evidence). New defects go into `reports/comprehensive-project-audit.md` with a
new ID. Commit on a branch and leave the order decision to the owner.
