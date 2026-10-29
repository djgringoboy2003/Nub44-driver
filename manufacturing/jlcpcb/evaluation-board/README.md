# JLCPCB upload files: evaluation-board (DRAFT, review before ordering)

Derived on 2026-10-29 by `automation/export/export_jlcpcb.py` from `manufacturing/pcbway/evaluation-board`, whose
export check passed. The Gerber and drill bytes are identical to the PCBWay package. No tool places an order.

| Upload | File |
|---|---|
| Gerber/drill (fabrication) | `evaluation-board-jlcpcb-gerbers.zip` |
| Assembly BOM | `BOM_JLCPCB.csv` |
| Assembly placement (CPL) | `CPL_JLCPCB.csv` |

- 29 BOM lines, 52 placed parts, all on the top side; J1 (wire pad) is not placed.
- JLCPCB part numbers are filled for 9 lines (LCSC numbers recorded on 2026-10-24); match the other 20 lines in JLCPCB's BOM tool by MPN, and confirm stock for every line.
- Rotations are KiCad's. **Check every part in JLCPCB's placement preview** (pin 1 of U1, U2, U3; the PowerPAK MOSFETs Q1-Q3; diodes D1-D3; RS1's Kelvin pads) and correct it there before paying.
- Parts not confirmed at LCSC on 2026-10-24: TPS552882RPMR (U1), SISS80DN-T1-GE3 (Q2, Q3: JLC stock 0), MCS1632R010FER (RS1). Use JLCPCB global sourcing or consign them; do not accept substitutes without review.
- Board options, layer order and the pre-order checks: `documentation/ordering-guide.md`.
