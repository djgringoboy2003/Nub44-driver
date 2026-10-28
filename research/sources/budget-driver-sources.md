# Budget two-cell driver: source record

Retrieved 2026-10-28 for [the budget-driver plan](../../engineering/budget-driver-plan.md).
Manufacturer documents establish component specifications, not feasibility of our complete circuit.
Retailer observations are dated search snapshots; stock and payable offers are `UNKNOWN`.
All local downloaded files are untrusted input, parsed with project Python in isolated (`-I`) mode.
No downloaded code was executed. Local datasheets are git-ignored; hashes below identify the reviewed bytes.

## Primary technical sources

| ID | Publisher / document | URL | Reviewed scope / local copy |
|---|---|---|---|
| BUD-01 | TI TPS54821, SLVSB14B, revised February 2016 | https://www.ti.com/lit/ds/symlink/tps54821.pdf ; https://www.ti.com/product/TPS54821 | PDF 42 pages; pp.1,3,5–6,12–15,22, package drawings: input/output class, compensation access, soft start, 0.6 V reference, 10.5/14.5/17 A high-side current limit, magnetics and exposed pad. Local `datasheets/budget_TI_TPS54821_SLVSB14B.pdf`. |
| BUD-02 | TI TPS54620 product information | https://www.ti.com/product/TPS54620 | 4.5–17 V, 6 A, current-mode alternative, 14-pin QFN options, adjustable soft start. No substitution qualification. |
| BUD-03 | TI TPS56628, SLVSC94A, revised December 2013; product selector | https://www.ti.com/lit/ds/symlink/tps56628.pdf ; https://www.ti.com/product/TPS56628 | PDF 27 pages; pp.1,4–5 and package section: D-CAP2, DDA HSOIC-8 PowerPAD, fixed 1 ms startup. Product selector lists 85% maximum duty. Adaptive timing/high-duty CC operation not qualified. Local `datasheets/budget_TI_TPS56628_SLVSC94A.pdf`. |
| BUD-04 | TI TPS56637 product information | https://www.ti.com/product/TPS56637 | 6 A D-CAP3 converter; RPA VQFN-HR-10 3 × 3 mm package. Not a SOIC hand-assembly alternative. |
| BUD-05 | Bourns SRP1265A series | https://www.bourns.com/docs/product-datasheets/srp1265a.pdf | PDF 5 pages; p.1 specifications/land pattern, remaining current/temperature curves and processing information. 4R7M: 4.7 µH ±20%, DCR 7/8.4 mΩ typ/max, Irms 13.5 A (40 °C rise), Isat 28 A (20% L drop), data at 25 °C. No revision date identified on reviewed first page. Local `datasheets/budget_Bourns_SRP1265A.pdf`. |
| BUD-06 | TI INA300, SBOS613C, revised June 2021 | https://www.ti.com/lit/ds/symlink/ina300.pdf | PDF 42 pages; pp.1,3–5,10–18: independent current comparator, DGS VSSOP-10 option, 2.7–5.5 V supply, 0–36 V common mode, resistor threshold, delay/noise adjustment, latching. Local `datasheets/budget_TI_INA300_SBOS613C.pdf`. |
| BUD-07 | TI INAx180, SBOS741H, revised July 2022 | https://www.ti.com/lit/ds/symlink/ina180.pdf | PDF 53 pages; features, package/pin and electrical tables: INA180 A2 gain 50, DBV SOT-23-5, offset specification depends on common mode (150 µV at 0 V versus 500 µV at 12 V). No new error budget completed. Local `datasheets/budget_TI_INA180_SBOS741H.pdf`. |
| BUD-08 | Alpha & Omega AO4407A, Rev.11.1 March 2024 | https://www.aosmd.com/sites/default/files/res/datasheets/AO4407A.pdf | Manufacturer PDF pp.1–2: SOIC-8 P-MOS, −30 V VDS, ±25 V VGS, resistance specified at −6/−10/−20 V gate drive. No −4.5 V resistance guarantee; minimum-drive and thermal qualification open. Existing local `datasheets/cmp_AOS_AO4407A.pdf` is a historical copy; use the linked Rev.11.1 for this proposal. |

Existing references also used: PREORDER-07 / LEAD-02 (INA186), PREORDER-08 (Microchip DS40002204A, 2020;
SOIC pinout p.15 and port multiplexing p.18), PREORDER-02 (SiSS23DN gate rating), LEAD-04 (DMG1012T),
P450-01/02 (Project 450/TPS56C215). The existing exact INA186A2IDCKR remains the starting proposal;
no imaginary INA186 DBV commercial suffix is introduced.

## GBP retailer observations

Primary seller pages were returned by web search on the retrieval date. The search service reports the crawl
age shown below. Direct attempts to reopen BUD-09…12 returned cache miss/timeout, so none is represented as
a live checkout quote. MOQ/multiple for the observed offers is one. Choose cut tape, not optional Digi-Reel:
DigiKey's observed £4.50 reeling fee is excluded. Shipping/dispatch location and live stock are `UNKNOWN`.
All prices below are GBP; this table needs no FX conversion.

| ID | Seller / exact MPN | Listing URL | Observed quantity pricing / VAT | Freshness and limits |
|---|---|---|---|---|
| BUD-09 | DigiKey UK / TPS54821RHLT | https://www.digikey.co.uk/en/products/detail/texas-instruments/TPS54821RHLT/2797955 | Cut tape, each: 1+ £3.440, 10+ £2.611, 25+ £2.40440, explicitly ex VAT. | Search crawl 5 months old. No shipping or current stock assertion. |
| BUD-10 | DigiKey UK / SRP1265A-4R7M | https://www.digikey.co.uk/en/products/detail/bourns-inc/SRP1265A-4R7M/4876629 | Cut tape, each: 1+ £1.050, 10+ £0.869, 25+ £0.80360, explicitly ex VAT. | Search crawl 3 months old. No shipping or current stock assertion. |
| BUD-11 | DigiKey UK / INA300AIDGSR | https://www.digikey.co.uk/en/products/detail/texas-instruments/INA300AIDGSR/7688269 | Cut tape, each: 1+ £1.130, 10+ £0.826, 25+ £0.74880, explicitly ex VAT. | Search crawl 2 months old. No shipping or current stock assertion. |
| BUD-12 | Farnell UK / ATTINY1616-SN, order code 3052744 | https://uk.farnell.com/microchip/attiny1616-sn/mcu-8bit-20mhz-soic-20/dp/3052744 | Each: 1+ £0.878, 25+ £0.795, explicitly ex VAT; MOQ/multiple 1. Seller identifies SOIC-20. | Search crawl 5 months old. Exact carrier accepted by assembler and shipping/current stock UNKNOWN. |
| BUD-13 | Mouser UK / INA180A2IDBVR | https://www.mouser.co.uk/en/ProductDetail/Texas-Instruments/INA180A2IDBVR?qs=5aG0NVq1C4wYcJfa99BoHg%3D%3D | Cut tape: 1+ £0.361, 10+ £0.255, 25+ £0.227. VAT basis UNKNOWN in retrieved extract. | Search crawl 5 days old. Alternative only; excluded from cost basket. Current delivered price UNKNOWN. |
| BUD-14 | Mouser UK / ATTINY1616-SNR | https://www.mouser.co.uk/en/ProductDetail/Microchip-Technology/ATTINY1616-SNR?qs=HXFqYaX1Q2w711d4DTfCdw%3D%3D | Cut tape: 1+ £0.871, 25+ £0.856. VAT basis UNKNOWN in retrieved extract. | Search crawl 1 month old. Packing-suffix alternative to SN; not adopted. Excluded from ex-VAT cost basket. |

The four-role basket uses the 1+ tier for five/seven purchases per line, with two proposed development spares
per MPN. It is not a complete BOM, a PCBWay attrition allowance or a delivered quote. Native GBP snapshots for
the existing design and eBay qualifications remain in [the earlier review](../../reports/bom-quote-sourcing-review.md).
No new AliExpress Choice/UK eBay listing is qualified for the proposed budget circuit.

## Download integrity

SHA-256 of new local PDFs, checked with isolated Python after download. These identify source documents;
they do not constitute generated CAD/simulation/bench evidence.

| Source | Local basename in `research/datasheets/` | SHA-256 |
|---|---|---|
| BUD-01 | `budget_TI_TPS54821_SLVSB14B.pdf` | `97db153c6c468e0bae85aee98864018f3070d067706e5a9884c5d0ff99f1c03d` |
| BUD-03 | `budget_TI_TPS56628_SLVSC94A.pdf` | `ae56db7dcaa005e65f8ed716b4f9dc7e47ae083c50a22fcda3bbab79ee715225` |
| BUD-05 | `budget_Bourns_SRP1265A.pdf` | `30b470999b737a6350ce5b09a917a5f12090c2e0895a78ddc15285e3d44ec649` |
| BUD-06 | `budget_TI_INA300_SBOS613C.pdf` | `348944688a1bdb7d343a4015ecd29a08bd1b78c63de1934d20f867aa61d34188` |
| BUD-07 | `budget_TI_INA180_SBOS741H.pdf` | `0466afe9de41f5dac1c3ca902972ad75aabbb91f273202557de05ed415aa16ac` |
