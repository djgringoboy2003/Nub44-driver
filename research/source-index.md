# Research source index

All sources were retrieved on 2026-10-24 unless a row says otherwise. Local copies are in `research/datasheets/`
with a topic prefix (`nubm44_`, `pwr_`, `cmp_`, `bat_`, `mfg_`). Each topic keeps its own table with URL,
document revision, local path, relevant pages and primary/secondary classification:

| Topic | IDs | Source table | Report |
|---|---|---|---|
| Nichia NUBM44 laser diode | LD-01 … LD-30 | [sources/nubm44-sources.md](sources/nubm44-sources.md) | [nubm44-research.md](nubm44-research.md) |
| Converter ICs and architecture | PWR-01 … PWR-25 | [sources/converter-sources.md](sources/converter-sources.md) | [converter-ic-research.md](converter-ic-research.md), [architecture-comparison.md](architecture-comparison.md) |
| Supporting components and sourcing | CMP-01 … CMP-42 | [sources/component-sources.md](sources/component-sources.md) | [component-research.md](component-research.md), [component-candidates.csv](component-candidates.csv) |
| Batteries, polarity, host mechanics | BAT-01 … BAT-44 | [sources/battery-sources.md](sources/battery-sources.md) | [battery-and-mechanics.md](battery-and-mechanics.md) |
| PCBWay fabrication/assembly, CAD tooling | MFG-01 … MFG-33 | [sources/manufacturing-sources.md](sources/manufacturing-sources.md) | [pcbway-requirements.md](pcbway-requirements.md), [cad-tooling.md](cad-tooling.md) |

## Sources added by the lead engineer

| ID | Title | Publisher | URL | Revision | Local copy | Used for |
|---|---|---|---|---|---|---|
| LEAD-01 | TPS552882 datasheet: pin table, RPM0026A land pattern (vector geometry extracted from p.39), equations 1–6, compensation p.24–25 | Texas Instruments | https://www.ti.com/lit/ds/symlink/tps552882.pdf | SLVSFC5, Nov 2020 | `datasheets/pwr_tps552882_slvsfc5.pdf` | Symbol, footprint, all converter settings |
| LEAD-02 | INA186 Table 5-1 Pin Functions (DCK) | Texas Instruments | https://www.ti.com/lit/ds/symlink/ina186.pdf | SBOS318B, Jul 2021, p.3 | `datasheets/cmp_TI_INA186.pdf` | U2 symbol pins |
| LEAD-03 | ATtiny1616 Table 5-1 PORT Function Multiplexing | Microchip | (local copy from LCSC mirror) | p.17 | `datasheets/cmp_Microchip_ATtiny1616.pdf` | MCU pin allocation |
| LEAD-04 | DMG1012T pin diagram (SOT-523: 1 G, 2 S, 3 D) | Diodes Inc. | https://www.diodes.com/assets/Datasheets/ds31783.pdf | DS31783 Rev. 8-2, Feb 2022 | `datasheets/cmp_Diodes_DMG1012T.pdf` | Q4–Q6 |
| LEAD-05 | XGL5030 product page: XGL5030-102 L, DCR, Isat, Irms | Coilcraft | https://www.coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xgl/xgl5030/ | datasheet revised 02/19/26 (per search result; PDF download blocked by a JavaScript challenge) | none | L1 values |
| LEAD-06 | LCSC listing C6937849 (XGL5030-102MEC: 1 µH, 5.8 mΩ, 14 A Isat, 17.8 A rated, 5.5 × 5.3 mm; stock UNKNOWN) | LCSC | https://www.lcsc.com/product-detail/C6937849.html | page as fetched | none | L1 cross-check |
| LEAD-07 | Ohmite MCS1632R010FER listing (10 mΩ ±1 % 1 W 1206; ~775k stock, 26-week lead time) | DigiKey | https://www.digikey.my/en/products/detail/ohmite/MCS1632R010FER/2003872 | search result snippet | none | Shunt choice (stock figure from a search snippet, not a fetched page) |
| LEAD-08 | RALEC LR1206-21R010F4 datasheet (10 mΩ 1 W 1206; LCSC ~830 pcs) | RALEC / LCSC | https://datasheet.lcsc.com/lcsc/2304140030_RALEC-LR1206-21R010F4_C154635.pdf | search result snippet | none | Alternate shunt |


## Independent pre-order review sources (retrieved 2026-10-27)

Primary manufacturer documents. These supplement the historical LEAD rows; live stock is UNKNOWN.

| ID | Document / manufacturer | Revision and reviewed pages | URL | Local copy |
|---|---|---|---|---|
| PREORDER-01 | XGL5030 / Coilcraft | 1576-1, 2026-02-19, p.1 | https://www.coilcraft.com/getmedia/e64ac115-95f2-45c7-b798-1b3769b91583/xgl5030.pdf | `datasheets/cmp_Coilcraft_XGL5030_1576-1.pdf` |
| PREORDER-02 | SiSS23DN / Vishay | 62852 Rev.A, 2013-05-13, p.1 | https://www.vishay.com/docs/62852/siss23dn.pdf | `datasheets/cmp_Vishay_SiSS23DN.pdf` |
| PREORDER-03 | SiSS80DN / Vishay | 77684 Rev.C, 2026-10-19, p.1 | https://www.vishay.com/docs/77684/siss80dn.pdf | `datasheets/cmp_Vishay_SiSS80DN.pdf` |
| PREORDER-04 | PowerPAK 1212-8S / Vishay | 63919, 2020-07-20, p.1 | https://www.vishay.com/docs/63919/ppak1212-8s.pdf | `datasheets/cmp_Vishay_PowerPAK1212-8S_outline_63919.pdf` |
| PREORDER-05 | Recommended minimum pads / Vishay | 72597, 2008-01-21, PDF p.1 / printed p.7 | https://www.vishay.com/docs/72597/72597.pdf | `datasheets/cmp_Vishay_recommended-min-pads_72597.pdf` (the URL serves the PowerPAK 1212-8 single page alone) |
| PREORDER-06 | MCS series / Ohmite | NEC#11705, no printed revision date, PDF pp.2-3 (printed pp.16-17) | https://www.ohmite.com/assets/files/Datasheets/mcs-series.pdf?r=false | `datasheets/cmp_Ohmite_MCS-series.pdf` |
| PREORDER-07 | INA186 / TI | SBOS318B, July 2021, p.3 | https://www.ti.com/lit/ds/symlink/ina186.pdf | `datasheets/cmp_TI_INA186.pdf` |
| PREORDER-08 | ATtiny1614/1616/1617 / Microchip | DS40002204A, 2020, pp.16/18/576-578 | https://ww1.microchip.com/downloads/en/DeviceDoc/ATtiny1614-16-17-DataSheet-DS40002204A.pdf | `datasheets/cmp_Microchip_ATtiny1614-16-17_DS40002204A.pdf` |
| PREORDER-09 | PMEG4010CEJ / Nexperia | 2022-10-01, pp.1-3; retrieved 2026-10-28 | https://assets.nexperia.com/documents/data-sheet/PMEG4010CEJ.pdf?download=1 | `datasheets/cmp_Nexperia_PMEG4010CEJ.pdf` |
| PREORDER-10 | RB521S30T1 / onsemi | RB521S30T1/D Rev.12, October 2024, p.1; retrieved 2026-10-28 | https://www.onsemi.com/download/data-sheet/pdf/rb521s30t1-d.pdf | `datasheets/cmp_onsemi_RB521S30T1.pdf` |
| PREORDER-11 | BZX585 series / Nexperia | Rev.9, 2026-09-11, pp.1,2,4; retrieved 2026-10-28 | https://assets.nexperia.com/documents/data-sheet/BZX585_SER.pdf?download=1 | `datasheets/cmp_Nexperia_BZX585_SER.pdf` |

Local copies were downloaded on 2026-10-28 and checked against the document number and revision above; the
existing SiSS23DN, SiSS80DN and INA186 copies already were these revisions.

LEAD-01 was rechecked against the manufacturer PDF, pp.3/38-40, SLVSFC5 November 2020. LEAD-04 was rechecked
against DS31783 Rev.8-2 February 2022, p.1, at https://www.diodes.com/datasheet/download/DMG1012T.pdf.
The exact reviewed board/package hashes and comparison results are in [pre-order-review.md](../reports/pre-order-review.md).


## Quote and sourcing review, 2026-10-28

Prices below are dated observations, not reserved inventory or UK delivered quotes. Review, retrieval limits
and calculations: [bom-quote-sourcing-review.md](../reports/bom-quote-sourcing-review.md). No AliExpress price
was qualified; every such value is UNKNOWN. Historical LEAD stock snippets above are not current stock evidence.

| ID | Source / publisher | URL or private input | Retrieved / revision | Local evidence and use |
|---|---|---|---|---|
| QUOTE-01 | PCBWay BOM quotation, product T-1K2W1137524A, five units | Owner-provided private file; external URL UNKNOWN | Filename dated 2026-10-28; reviewed 2026-10-28, quote validity UNKNOWN | `documentation/T-1K2W1137524A-5units-BOM_PCBWay_template(2026-10-28).xls`; SHA-256 `8879e8906eefa4084cdd92df5f52ffa5eb7880dc75fb3d2069cef9b1157d7d4b`; parsed with system Python -I / external xlrd 2.0.2. Currency ISO code UNKNOWN (dollar cell formats); arithmetic/comparison in `reports/bom-quote-check.json`. Original committed in this private repository. |
| SOURCE-01 | XGL5030-102MEC exact product / Coilcraft | https://www.coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xgl/xgl5030/xgl5030-102/ | Retrieved 2026-10-28 | USD 2.62 at 1+; sub-reel tape or optional USD 25 leader/trailer; 400/full C reel. Orderability widget ambiguous; live stock and UK shipping/tax UNKNOWN. Sample eligibility/quantity UNKNOWN. |
| SOURCE-02 | TPS552882RPMR exact product / DigiKey | https://www.digikey.com/en/products/detail/texas-instruments/TPS552882RPMR/13577752 | Retrieved 2026-10-28 | USD 7.04 at 1+, 5.425 at 10+, cut tape. Optional Digi-Reel fee USD 7. Stock at payment and UK delivered total UNKNOWN; review does not reserve inventory. |
| SOURCE-03 | TPS552882RPMR C3188898 / LCSC | https://www.lcsc.com/product-detail/C3188898.html | Retrieved 2026-10-28 | Page dollar prices 6.539 at 1+, 5.984 at 10+, minimum/multiple 1. ISO currency, destination costs and final supply paperwork to confirm. |
| SOURCE-04 | AliExpress public exact-MPN searches and unqualified listing leads | https://www.aliexpress.com/item/1005009465550468.html and https://www.aliexpress.com/item/1005011654039524.html | Search/retrieval attempted 2026-10-28 | Secondary archive leads only; direct offer details unavailable. Seller, Choice status, exact option, price, pack quantity and UK shipping UNKNOWN. No prices copied from archive. Per-line exact-MPN search terms in `reports/bom-sourcing-options.csv`. |

Diode downloads are untrusted data, parsed with Python `-I`; no downloaded code was executed. The PDFs remain
local and git-ignored, consistent with the existing datasheet policy. Their SHA-256 values are:

| ID | Bytes | SHA-256 |
|---|---:|---|
| PREORDER-09 | 248222 | `378861b96f1aa490dca0818999999db0b460da2441fb7170b3c75699c156524f` |
| PREORDER-10 | 198508 | `089b507b5ac2c1a892bb84d6866cbe0956cba5bc0bd3c5675b415c7ea0a05660` |
| PREORDER-11 | 313874 | `10f91b1932e6952a7f5565b5af5e8253133bae1882d88a235baf34048c7db1f7` |

MFG-02/03/06/09/11 were read locally first and their primary pages rechecked on 2026-10-28 for the sourcing
review. MFG-03 and MFG-06 publish different attrition schedules; obtain a written order-specific schedule.
