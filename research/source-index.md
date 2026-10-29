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
| Separate 2S budget-driver qualification | BUD-01 … BUD-22 | [sources/budget-driver-sources.md](sources/budget-driver-sources.md) | [budget-driver plan](../engineering/budget-driver-plan.md), [implementation handover](../engineering/budget-2s-design.md) |

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


## GBP / UK sourcing follow-up, retrieved 2026-10-28

All prices are primary-seller page/search observations, not guaranteed current offers. Cached dates/direct-fetch
failures, MOQ, exact suffixes, VAT and dispatch limits are explicit below and per line in the review CSV.
Current stock and final UK/China delivered prices are UNKNOWN. The owner's preference for GBP does not resolve
QUOTE-01's ISO currency. No unverified placeholder zero price is recorded as a real offer.

| ID | Source / publisher | URL | Dated evidence / use |
|---|---|---|---|
| FX-01 | Euro foreign exchange reference rates / ECB | https://www.ecb.europa.eu/stats/shared/pdf/eurofxref.pdf | Sheet dated 2026-10-28: EUR 1 = USD 1.1133 = GBP 0.83785; derived GBP/USD 0.752582412647... . Reference conversion only, payment FX/fees UNKNOWN. |
| UK-01 | Coilcraft direct / UK sales route: XGL5030-102MEC | https://www.coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xgl/xgl5030/xgl5030-102/ | Retrieved 2026-10-28. 1+: 2.62 USD/each; min 1, multiple 1; VAT/handling/freight additional where applicable; GBP below is FX conversion, not a native GBP quote. Primary product page fetched; cached snapshot; current price/stock UNKNOWN. Product widget says both in stock and selected configuration unavailable; exact UK inventory UNKNOWN. C suffix retained for sub-reel tape; ask for a firm GBP UK-warehouse quote and accepted tape format. |
| UK-02 | DigiKey UK storefront: TPS552882RPMR | https://www.digikey.co.uk/en/products/detail/texas-instruments/TPS552882RPMR/13577752 | Retrieved 2026-10-28. 1+: 5.11 GBP/each; 10+: 3.934 GBP/each; min 1, multiple 1; ex VAT. Primary page fetched; cached last year; current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Cut tape; optional Digi-Reel GBP 4.50 excluded. Ten costs less than eight at the observed break. |
| UK-03 | Mouser UK storefront: SISS23DN-T1-GE3 | https://www.mouser.co.uk/en/ProductDetail/Vishay-Semiconductors/SISS23DN-T1-GE3?qs=vgn07B5hXasEazztkB9Jlw%3D%3D | Retrieved 2026-10-28. 1+: 1.20 GBP/each; 10+: 0.568 GBP/each; min 1, multiple 1; VAT basis UNKNOWN in retrieved pricing block; do not treat as a tax-inclusive total. Indexed primary-seller text; cached 2-5 months; current direct offer not verified. Current stock/dispatch location UNKNOWN. Cut tape; optional MouseReel GBP 3.50 excluded. Compare consolidated DigiKey UK-32 before splitting orders. |
| UK-04 | DigiKey UK storefront: SISS80DN-T1-GE3 | https://www.digikey.co.uk/en/products/detail/vishay-siliconix/SISS80DN-T1-GE3/12547429 | Retrieved 2026-10-28. 1+: 2.04 GBP/each; 10+: 1.311 GBP/each; min 1, multiple 1; ex VAT. Indexed primary-seller text; cached 2-5 months; current direct offer not verified. Current stock/dispatch location UNKNOWN. Cut tape. Observed ten-part purchase costs less than nine; present stock UNKNOWN. |
| UK-05 | Farnell UK: ATTINY1616-MNR | https://uk.farnell.com/microchip/attiny1616-mnr/mcu-8bit-avr-20mhz-qfn-20/dp/2769962 | Retrieved 2026-10-28. 1+: 0.690 GBP/each; 25+: 0.676 GBP/each; min 1, multiple 1; ex VAT. Primary product page fetched; cached snapshot; current price/stock UNKNOWN. Current stock/dispatch location UNKNOWN. Exact QFN bare MCU; not SOIC -SNR or a breakout board. |
| UK-06 | DigiKey UK storefront: INA186A2IDCKR | https://www.digikey.co.uk/en/products/detail/texas-instruments/INA186A2IDCKR/10434641 | Retrieved 2026-10-28. 1+: 0.750 GBP/each; 10+: 0.537 GBP/each; min 1, multiple 1; ex VAT. Indexed primary-seller text; cached 2-5 months; current direct offer not verified. Current stock/dispatch location UNKNOWN. A2 gain and DCK package retained; packing-only T candidate is ALT-02, not adopted. |
| UK-07 | DigiKey UK storefront: MCS1632R010FER | https://www.digikey.co.uk/en/products/detail/ohmite/MCS1632R010FER/2003858 | Retrieved 2026-10-28. 1+: 0.490 GBP/each; 10+: 0.312 GBP/each; min 1, multiple 1; ex VAT. Primary product page fetched; cached snapshot; current price/stock UNKNOWN. Current stock/dispatch location UNKNOWN. Freshly fetched snapshot used, not the conflicting indexed GBP 0.480/0.307; footprint remains OPEN. |
| UK-08 | Mouser UK storefront: DMG1012T-7 | https://www.mouser.co.uk/en/ProductDetail/Diodes-Incorporated/DMG1012T-7?qs=sGAEpiMZZMutXGli8Ay4kG1%252BkykufLNv4d6B9Zukwz0%3D | Retrieved 2026-10-28. 1+: 0.292 GBP/each; 10+: 0.174 GBP/each; min 1, multiple 1; VAT basis UNKNOWN in retrieved pricing block. Indexed primary-seller text; cached 2-5 months; current direct offer not verified. Current stock/dispatch location UNKNOWN. CPC UK-31 is cheaper but retrieved stock of eight is below either fitted requirement; availability must be confirmed. |
| UK-09 | Farnell UK: NCP15XH103F03RC | https://uk.farnell.com/murata/ncp15xh103f03rc/thermistor-ntc-10kohm-1-0402/dp/2456121 | Retrieved 2026-10-28. 10+: 0.0743 GBP/each; min 10, multiple 10; ex VAT. Primary seller search snapshot crawled today; no checkout stock confirmation. Current stock/dispatch location UNKNOWN. Retain exact thermal-protection curve/tolerance; do not replace with generic 10k NTC. |
| UK-10 | Farnell UK: PMEG4010CEJ,115 | https://uk.farnell.com/nexperia/pmeg4010cej-115/schottky-rect-40v-1a-sod323f/dp/1757777 | Retrieved 2026-10-28. 5+: 0.469 GBP/each; 10+: 0.321 GBP/each; min 5, multiple 5; ex VAT. Primary seller search snapshot crawled yesterday; final offer UNKNOWN. Current stock/dispatch location UNKNOWN. |
| UK-11 | Farnell UK: RB521S30T1G | https://uk.farnell.com/onsemi/rb521s30t1g/diode-schottky-200ma-30v-sod-523/dp/2317433 | Retrieved 2026-10-28. 5+: 0.147 GBP/each; 50+: 0.0781 GBP/each; min 5, multiple 5; ex VAT. Primary seller search snapshot crawled last week; final offer UNKNOWN. Current stock/dispatch location UNKNOWN. Exact onsemi suffix; do not replace with Nexperia RB521S30,115 automatically. |
| UK-12 | DigiKey UK storefront: BZX585-C6V2,135 | https://www.digikey.co.uk/en/products/detail/nexperia-usa-inc/BZX585-C6V2-135/7724513 | Retrieved 2026-10-28. 1+: 0.220 GBP/each; 10+: 0.135 GBP/each; min 1, multiple 1; ex VAT. Primary seller indexed snapshot crawled last month; final offer UNKNOWN. Current stock/dispatch location UNKNOWN. Base BOM omits packing suffix. Candidate price is not an exact-MPN approval; hardware overvoltage role retained for review. |
| UK-13 | Farnell UK: CL05B104KO5NNNC | https://uk.farnell.com/samsung-electro-mechanics/cl05b104ko5nnnc/cap-0-1uf-16v-mlcc-0402/dp/3013349 | Retrieved 2026-10-28. 10+: 0.0105 GBP/each; 100+: 0.0090 GBP/each; min 10, multiple 10; ex VAT. Primary product search snapshot crawled two weeks ago; category page shows a different price. Snapshot cut tape backordered to 2026-11-22 despite full-reel stock; current cut-tape availability UNKNOWN. Do not use the headline full-reel stock count as low-quantity availability. |
| UK-14 | Farnell UK: CL10A106KP8NNNC | https://uk.farnell.com/samsung-electro-mechanics/cl10a106kp8nnnc/cap-10uf-10v-mlcc-0603/dp/3013386 | Retrieved 2026-10-28. 10+: 0.105 GBP/each; 100+: 0.0638 GBP/each; min 10, multiple 10; ex VAT. Primary seller indexed snapshot crawled two weeks ago; final offer UNKNOWN. Retrieved listing out of stock; current availability/lead time UNKNOWN. |
| UK-15 | DigiKey UK storefront: CL21A226MOQNNNE | https://www.digikey.co.uk/en/products/detail/samsung-electro-mechanics/CL21A226MOQNNNE/3888567 | Retrieved 2026-10-28. 1+: 0.240 GBP/each; 10+: 0.143 GBP/each; 50+: 0.1042 GBP/each; min 1, multiple 1; ex VAT. Primary exact-product indexed snapshot crawled two weeks ago; other snapshots/aliases have different prices. Current stock/dispatch location UNKNOWN. Keep exact O/Q/N suffix string; cheaper MQQNNNE/MQQNNNG listings are different MPNs, not approved substitutes. |
| UK-16 | DigiKey UK storefront: RT0402BRD0710KL | https://www.digikey.co.uk/en/products/detail/yageo/RT0402BRD0710KL/1068998 | Retrieved 2026-10-28. 1+: 0.070 GBP/each; 10+: 0.058 GBP/each; min 1, multiple 1; ex VAT. Primary indexed snapshot crawled three months ago; final offer UNKNOWN. Current stock/dispatch location UNKNOWN. Retain 0.1% precision current-setting part; UK eBay lead UK-29 not qualified on pack/postage. |
| UK-17 | RS UK: GRM1555C1H681JA01D | https://uk.rs-online.com/web/p/mlccs-multilayer-ceramic-capacitors/2477970 | Retrieved 2026-10-28. 100+: 0.018 GBP/each; min 100, multiple 100; ex VAT. Primary indexed snapshot crawled four months ago; final offer UNKNOWN. Retrieved listing temporarily out of stock; current availability UNKNOWN. 100-piece pack is excessive for this build; request a small cut-tape quantity elsewhere. |
| UK-18 | DigiKey UK storefront: RC0402FR-07100KL | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-07100KL/729473 | Retrieved 2026-10-28. 1+: 0.070 GBP/each; 10+: 0.015 GBP/each; 25+: 0.0112 GBP/each; 50+: 0.0088 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-19 | DigiKey UK storefront: RC0402FR-0710KL | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-0710KL/729470 | Retrieved 2026-10-28. 1+: 0.070 GBP/each; 10+: 0.015 GBP/each; 25+: 0.0112 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-20 | DigiKey UK storefront: RC0402FR-071K2L | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-071K2L/726517 | Retrieved 2026-10-28. 1+: 0.080 GBP/each; 10+: 0.016 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-21 | DigiKey UK storefront: RC0402FR-0720KL | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-0720KL/726557 | Retrieved 2026-10-28. 1+: 0.070 GBP/each; 10+: 0.015 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-22 | DigiKey UK storefront: RC0402FR-07220RL | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-07220RL/726565 | Retrieved 2026-10-28. 1+: 0.070 GBP/each; 10+: 0.015 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-23 | DigiKey UK storefront: RC0402FR-0727K4L | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-0727K4L/2827905 | Retrieved 2026-10-28. Price UNKNOWN; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Conflicting CT and Digi-Reel price blocks: low-quantity price UNKNOWN. |
| UK-24 | DigiKey UK storefront: RC0402FR-0747KL | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-0747KL/726616 | Retrieved 2026-10-28. 1+: 0.070 GBP/each; 10+: 0.016 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-25 | DigiKey UK storefront: RC0402FR-0749K9L | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-0749K9L/726620 | Retrieved 2026-10-28. 1+: 0.080 GBP/each; 10+: 0.016 GBP/each; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Observed cut-tape breaks; a small kit is not proof of exact manufacturer/tolerance. |
| UK-26 | DigiKey UK storefront: RC0402FR-074K7L | https://www.digikey.co.uk/en/products/detail/yageo/RC0402FR-074K7L/2827563 | Retrieved 2026-10-28. Price UNKNOWN; min 1, multiple 1; ex VAT. Primary indexed exact-product snapshot; final current offer UNKNOWN. Current stock/dispatch location UNKNOWN. Exact primary product lead found; price block not retrieved: price UNKNOWN. |
| UK-27 | Coilcraft UK sales/warehouse and UK terms | https://www.coilcraft.com/de-de/contact/saleslocations/europe-and-africa/ ; https://www.coilcraft.com/de-de/home/terms-uk/ | Retrieved 2026-10-28. Manufacturer lists a UK warehouse and UK sales route. Exact XGL5030 stock/GBP delivered quote UNKNOWN. UK terms: USD base pricing, FX variation, VAT/handling and FCA costs may apply. |
| UK-28 | DigiKey UK published delivery information | https://www.digikey.co.uk/en/products/detail/texas-instruments/TPS552882RPMR/13577752 | Retrieved 2026-10-28. UK site footer: free UK delivery at GBP 33+, GBP 12 below. Marketplace/destination/checkout exceptions and VAT/import terms must be confirmed. UK storefront does not establish UK dispatch. |
| UK-29 | eBay UK / RapidWarehouse-Office, exact R9 title | https://www.ebay.co.uk/itm/146427921924 | Retrieved 2026-10-28. Fetched primary cached page: GBP 3.22 per listing unit; Hampshire UK location. Quantity of resistors in each listing unit UNKNOWN. GBP 12.09 postage shown for non-UK destination 1073VR is not a UK shipping quote: UK shipping UNKNOWN. VAT basis and traceability UNKNOWN. |
| UK-30 | eBay UK / richde_uk0, title five ATTINY1616-MNR | https://www.ebay.co.uk/itm/405733729377 | Retrieved 2026-10-28. Fetched primary cached page: GBP 17.27 per lot of five, location Shenzhen China, brand Unbranded. Displayed postage GBP 3.36; UK destination not established, so UK shipping UNKNOWN. Seller name does not establish UK stock. Not qualified for critical MCU procurement. |
| UK-31 | CPC UK / DMG1012T-7 | https://cpc.farnell.com/diodes-inc/dmg1012t-7/mosfet-n-ch-20v-sot-523/dp/SC16742 | Retrieved 2026-10-28. Fetched cached page: GBP 0.11 at 1+, 0.07 at 10+, ex VAT, min/multiple 1, cut tape. Snapshot only eight parts, below fitted 15/9. Free standard UK delivery above GBP 24.99 ex VAT; actual stock/postage UNKNOWN. |
| UK-32 | DigiKey UK / Q1 alternative exact source | https://www.digikey.co.uk/en/products/detail/vishay-siliconix/SISS23DN-T1-GE3/4142144 | Retrieved 2026-10-28. Fetched cached page: GBP 1.18 at 1+, 0.746 at 10+, ex VAT, cut tape; GBP 7.46 for ten. Optional GBP 4.50 Digi-Reel excluded. May be cheaper delivered than splitting a Mouser order. Current stock/price UNKNOWN. |
| ALT-01 | XAL5030-102MEC / Coilcraft | https://www.coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xal/xal50xx/xal5030-102/ ; https://www.coilcraft.com/getmedia/49bc46c8-4b2c-45b9-9b6c-2eaa235ea698/xal50xx.pdf | Retrieved 2026-10-28. Manufacturer 1+ USD 2.74; XAL table 1 uH, DCR 8.5/9.4 mOhm typ/max, Isat 14 A at 30% drop, Irms 8.7/11.1 A at 20/40 C rise. Compared with PREORDER-01 XGL. Proposed only, no completed substitute footprint/thermal review; not cheaper than exact XGL direct reference. |
| ALT-02 | INA186A2IDCKT / TI | https://www.ti.com/product/INA186/part-details/INA186A2IDCKT | Retrieved 2026-10-28. A2 gain 50 V/V, DCK six-pin SC70, 250 small T&R; linked A2IDCKR 3000 large T&R. Packing-only candidate; GBP price/stock UNKNOWN, not adopted. |
| ALT-03 | TPS552882RPMR ordering alias / TI | https://www.ti.com/product/TPS552882/part-details/TPS552882RPMR | Retrieved 2026-10-28. TI identifies TPS552882RPMR.A as identical to TPS552882RPMR. 26-pin RPM package retained. GBP price/stock UNKNOWN; proposed sourcing alias only. |

## Project 450 inspiration review (2026-10-28)

| ID | Source / publisher | URL | Retrieval, local copy and scope |
|---|---|---|---|
| P450-01 | Project 450 / Gao Guangyan, Loneoceans Laboratories | https://www.loneoceans.com/labs/project450/ | Retrieved 2026-10-28 using direct HTTPS after web reader returned 406. Author's 2018–2019 build narrative, not independent verification. Local `datasheets/project450.html`, SHA-256 `40342538f0eed9d68457e692b875cf1a3bf7a7f7cc92e3b40ec366f645463cef`. Two-cell buck, mechanical heat path, arming and charging concepts; historical prices not current offers. |
| P450-02 | TPS56C215 datasheet / Texas Instruments | https://www.ti.com/lit/ds/symlink/tps56c215.pdf | Retrieved 2026-10-28; SLVSD05H, revised June 2025, 39 pages. Local `datasheets/pwr_tps56c215_slvsd05h.pdf`, SHA-256 `d0645b0baa5e2115ac8b8075fb40743454ed371a83ffed7d2f3abf289ffd4b06`. Pages 1–3: step-down topology, 4.5 V startup without external bias, 18-pin RNN package and adjustable SS; not compatible with the existing single-cell design or RPM pinout. |
| P450-03 | TPS552882 product information / Texas Instruments | https://www.ti.com/product/TPS552882 | Retrieved 2026-10-28. Manufacturer confirms four-switch buck-boost, RPM 26-pin package and fixed 4 ms soft start; existing local datasheet LEAD-01 remains the detailed design source. No current price/stock assertion. |

Assessment: [Project 450 design notes](project450-design-notes.md). All changes are proposals only.

## Budget two-cell sources (retrieved 2026-10-28/29)

[BUD-01…22 source table](sources/budget-driver-sources.md) records manufacturer specifications, local PDF
paths/SHA-256 and native GBP distributor snapshots for the separate budget track (DD-29/30). Initial PDFs:
TPS54821, TPS56628, SRP1265A, INA300 and INA180. Implementation adds DMP2022LSS, DMP2005UFG, AO3400A,
TLV6700, SN74HCS74, TLV803E, MCP1703A and WSK2512 manufacturer documents, with pin/limit/package notes.
Documents were parsed with Python `-I`; no downloaded code ran. The encrypted Microchip PDF needed an
isolated helper under ignored `tools/review-pdf`, without changing the project venv or requirements.
Retailer search snapshots are explicitly dated with crawl age and VAT basis. Live price/stock/shipping and
complete delivered cost remain UNKNOWN. No marketplace listing or substitution is qualified by this study.
The owner's 2S permission / £60 ceiling are requirements; the architecture, parts and remaining targets in
[the plan](../engineering/budget-driver-plan.md) remain subject to circuit qualification. The
[implementation handover](../engineering/budget-2s-design.md) records generated electrical screens,
preliminary model evidence and the issues blocking layout. No CAD or bench verification is claimed.
