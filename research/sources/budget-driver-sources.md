# Budget two-cell driver: source record

Retrieved 2026-10-28 for [the budget-driver plan](../../engineering/budget-driver-plan.md).
Manufacturer documents establish component specifications, not feasibility of our complete circuit.
Retailer observations are dated search snapshots; stock and payable offers are `UNKNOWN`.
All local downloaded files are untrusted input, parsed with project Python in isolated (`-I`) mode.
No downloaded code was executed. Local datasheets are git-ignored; hashes below identify the reviewed bytes.

## Primary technical sources

| ID | Publisher / document | URL | Reviewed scope / local copy |
|---|---|---|---|
| BUD-01 | TI TPS54821, SLVSB14B, revised February 2016 | https://www.ti.com/lit/ds/symlink/tps54821.pdf ; https://www.ti.com/product/TPS54821 | PDF 42 pages; pp.1,3,5–6,12–15,22, package drawings: input/output class, compensation access, soft start, 0.6 V reference, 10.5/14.5/17 A high-side current limit, magnetics and exposed pad. Local `datasheets/budget_TI_TPS54821_SLVSB14B.pdf`. Added 2026-10-29 (DD-31): p.5 table conditions TJ −40…125 °C, "measured at pins"; non-switching VIN current 600/800 µA; EN thresholds 1.21/1.26 V rising, 1.10/1.17 V falling, pull-up 1.15 µA and hysteresis 3.3 µA **typical only**. p.6 minimum off time 0 ns (BOOT-PH ≥ 3 V), BOOT-PH UVLO 2.1/3 V, PWRGD low below 92% / above 106% of Vref. p.15 100% duty operation until BOOT-PH UVLO forces a refresh. p.1 typical efficiency curve, approximate read 95.5% at 8 V → 3.3 V / 4 A, used only as a plausibility check. |
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

## Implementation qualification sources (2026-10-29)

Retrieved directly from the manufacturers. These additions support DD-30 and the separate numeric candidate
in `engineering/design/budget-2s/parameters.yaml`. None supplies a complete delivered price or proves the
complete driver. Local PDFs were parsed with `python -I`; the encrypted Microchip document additionally
needed `cryptography` in ignored `tools/review-pdf/`, outside the project venv and requirements. That helper
installation does not alter the electrical toolchain. Downloads were not executed.

| ID | Manufacturer / document | Primary URL | Reviewed scope / local basename |
|---|---|---|---|
| BUD-15 | Diodes DMP2022LSS, DS31373 Rev.6-2, December 2017 | https://www.diodes.com/datasheet/download/DMP2022LSS.pdf | pp.1–2, SO-8 diagram, ratings and drive conditions. `DMP2022LSS-13`; 20 V P-channel, ±12 V gate; RDS typ/max 11/16 mΩ at −4.5 V, 17/22 mΩ at −2.5 V (TA = 25 °C). Reverse-input candidate; compare output-pair loss rather than assume low gate threshold means low resistance. `budget_Diodes_DMP2022LSS.pdf`. |
| BUD-16 | Diodes DMP2005UFG, DS38932 Rev.2-2, November 2016 | https://www.diodes.com/datasheet/download/DMP2005UFG.pdf | pp.1–3, ratings, ordering and typical curves. `DMP2005UFG-7`; PowerDI3333-8, 20 V P-channel, ±10 V gate; RDS typ/max 5.4/6.5 mΩ at −2.5 V, 3.5/4.0 mΩ at −4.5 V (TA = 25 °C only); VGS(th) −0.3…−0.9 V. Typical Qg 55 nC at −4.5 V. Selected single output disconnect for development (DD-31); exact land/paste, transient margin and hot resistance still OPEN. `budget_Diodes_DMP2005UFG.pdf`. |
| BUD-17 | Alpha & Omega AO3400A Rev.3.1, July 2023 | https://www.aosmd.com/res/data_sheets/AO3400A.pdf | pp.1–2, SOT-23 N-channel ratings: 30 V VDS, ±12 V VGS, max RDS 48 mΩ at +2.5 V, 32 mΩ at +4.5 V. Candidate low-current gate driver only; a logic output must actually guarantee sufficient voltage. `budget_AOS_AO3400A.pdf`. |
| BUD-18 | TI TLV6700, SNVSAV2B, November 2019 | https://www.ti.com/lit/ds/symlink/tlv6700.pdf | pp.1,3,5–6. DDC pins 1 OUTA, 2 GND, 3 INA+, 4 INB−, 5 VDD, 6 OUTB. Rising threshold 396–404 mV, falling 387–400 mV over temperature; bias and resistor errors included in candidate calculations. Propagation numbers are not assumed guaranteed system response limits. `budget_TI_TLV6700.pdf`. |
| BUD-19 | TI SN74HCS74, SCLS782D, December 2021 | https://www.ti.com/lit/ds/symlink/sn74hcs74.pdf | pp.1,3–6. Schmitt inputs on all inputs; 2–6 V supply; asynchronous clear and edge-triggered data. `SN74HCS74DR` SOIC-14 proposed as fault/arm latch. Do not replace with ordinary LVC74A on slowly released fault nodes. Output drive at 3.3 V still needs a documented load/buffer solution: p.5 guarantees VOH ≥ VCC − 0.1 V and VOL ≤ 0.1 V for VCC 2–6 V only at \|IO\| = 20 µA (6 mA limits are given at 4.5 V and 6 V only). `budget_TI_SN74HCS74.pdf`. |
| BUD-20 | TI TLV803E family, SLVSES2J, May 2021 | https://www.ti.com/lit/ds/symlink/tlv803e.pdf | pp.1,3–5 and device nomenclature. `TLV803EA29DBZR`: open-drain active-low supervisor, 2.93 V nominal threshold, 200 ms reset delay; chosen DBZ pinout is 1 GND, 2 RESET, 3 VDD. R/V pinout suffixes are different. Complete tolerance/sequencing review OPEN. `budget_TI_TLV803E.pdf`. |
| BUD-21 | Microchip MCP1703A, DS20005122C, 2023 | https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP1703-Data-Sheet-DS20005122.pdf | pp.1–4,12,35. `MCP1703AT-3302E/MB` fixed 3.3 V SOT-89: 1 GND, 2/tab VIN, 3 VOUT. Input 2.7–16 V; output capacitors 1–22 µF. Full-temperature regulation uses ±3%, plus applicable load/line terms; do not call the `02` nominal tolerance a complete ±2% rail guarantee. `budget_Microchip_MCP1703A.pdf`. |
| BUD-22 | Vishay WSK2512, document 30108, 11 December 2023 | https://www.vishay.com/docs/30108/wsk2512.pdf | pp.1–3, four-terminal construction, exact ordering encoding, resistance-dependent package/land drawing. `WSK2512R0100FEA`: 10 mΩ, 1%, 1 W at 70 °C, ±35 ppm/°C for this value. Use T1.19 mm / 0.005–0.2 Ω land group; a generic two-pad 2512 is not equivalent. Procurement and pin-to-land review OPEN. `budget_Vishay_WSK2512.pdf`. |

### Default-off interface additions (DD-32, 2026-10-29)

| ID | Manufacturer / document | Primary URL | Reviewed scope / local basename |
|---|---|---|---|
| BUD-23 | Diodes DMG1013T, DS31784 Rev.7-2, June 2024 | https://www.diodes.com/assets/Datasheets/ds31784.pdf | p.3 (TA = 25 °C): `DMG1013T-7` P-channel −20 V, VGSS ±6 V, VGS(th) −0.5…−1.0 V, RDS max 0.7/0.9/1.3 Ω at −4.5/−2.5/−1.8 V, IDSS ≤ 100 nA at −20 V, IGSS ≤ ±2 µA at ±4.5 V. P1 EN source. Existing local copy `cmp_Diodes_DMG1013T.pdf` (earlier CMP-27 comparison). |
| BUD-24 | Vishay WSL series, document 30100, revision 23-Nov-2023 | https://www.vishay.com/docs/30100/wsl.pdf | pp.1–2: WSL2512 1.0 W at 70 °C; ±1% from 0.0005 Ω; component TCR (including terminals, −55…+155 °C) ±75 ppm/°C for 7–500 mΩ; element TCR < 20 ppm/°C; part number `WSL2512R0100FEA` = 10 mΩ, ±1%. Budget shunt (DD-34). Local `budget_Vishay_WSL.pdf`, downloaded 2026-10-29, parsed with `python -I`. |
| BUD-25 | Web search snapshots, 2026-10-29 (DD-34) | LCSC C57461 / C529558 / C2862638 / C844901; DigiKey UK TLV803EA29DBZR/11308855; DigiKey DMP2005UFG-7/7352955 | Search-result snippets, not fetched offers: TPS54821RHLR, INA300AIDGSR, SN74HCS74DR and WSL2512R0100FEA listed by LCSC/JLCPCB; DigiKey shows 12-week lead times for TPS54821/INA300; TI showed SN74HCS74 out of stock; DigiKey UK about 3,200 TLV803EA29DBZR at about £0.37 (ex VAT); DigiKey DMP2005UFG-7 not normally stocked, 40-week lead; WSK2512R0100FEA out of stock on aggregators. No AliExpress listing found for any searched TI part. Price/stock remain UNKNOWN for costing. |
| BUD-26 | AMASS XT30PW-M drawing (scanned, TME copy), accessed 2026-10-29 | https://www.tme.eu/Document/6eb2005a51a52592b3f19e8a450c54c8/XT30PW-M.pdf | p.1: PCB male, right-angle, 15 A rated current, contact resistance 0.80 mΩ (the `power_model` contact allocation until DD-40; the current Amass specification, BUD-30, gives 1.20 mΩ and is now used), 2-pin land on 5.0 mm pitch. The scan does not show which pad carries the moulded +/− marks; KiCad's `Connector_AMASS:AMASS_XT30PW-M_1x02_P2.50mm_Horizontal` places its "+" silk beside pad 2, so J1 pin 2 = VBAT_IN (DD-38). Physical check of the moulding against the B+/B− silkscreen OPEN. `budget_AMASS_XT30PW-M.pdf`. |
| OWNER-VI-01 | Project owner, conversation instruction, 2026-10-29 | — | NUBM44 operating points supplied by the owner: 3.0 A at 4.40 V, 3.5 A at 4.52 V, 4.0 A at 4.62 V, 4.5 A at 4.72 V; main target 4.5 A, about 7.3 W optical expected (DD-33). Owner data, not a measurement by this project and not a manufacturer limit. Consistent with community data in `research/nubm44-research.md` (about 4.7 V at 4.5 A, LD-13/LD-14). Used for the setpoint options and efficiency condition only; the 3.8–5.2 V compliance range still applies. |

Further limits used from existing records (no new download):
- LEAD-04 DMG1012T (DS31783 Rev.8-2), p.2 at 25 °C: VGS(th) 0.5–1.0 V, RDS max 0.4/0.5/0.7 Ω at 4.5/2.5/1.8 V,
  IDSS ≤ 100 nA, IGSS ≤ ±1 µA, VGSS ±6 V. These are for N1–N5.
- BUD-18 TLV6700, p.5: VOL ≤ 250 mV at 3 mA (VDD 1.8 V) and at 5 mA (VDD 5 V); open-drain leakage ≤ 300 nA.
- BUD-20 TLV803E, p.8–9: VIT− accuracy ±2% (−40…125 °C), hysteresis 0.9–1.5%; VOL ≤ 300 mV at 500 µA
  (VDD 1.7 V) and at 2 mA (VDD 3.3 V); leakage ≤ 350 nA; VPOR 0.7 V; reset delay A 130/200/270 ms.
- BUD-06 INA300, p.5: ALERT VOL ≤ 400 mV at 3 mA, leakage ≤ 1 µA at 3.3 V.
- BUD-19 SN74HCS74, p.4–5: VCC 2–6 V; VT+/VT− rows at 2/4.5/6 V only; input leakage ≤ ±1 µA at 6 V.
- PREORDER-08 ATtiny1614/16/17 DS40002204A: p.2 speed grade 0–10 MHz at 2.7–5.5 V. p.513: VIH 0.7 VDD,
  VIL 0.3 VDD, VOL ≤ 0.6 V and VOH ≥ 2.4 V at VDD 3.0 V and 7.5 mA. Pin leakage is given only as typical
  (< 0.05 µA).
- BUD-01 TPS54821, p.3: EN absolute maximum 6 V.

All eight new part prices, live stock, UK dispatch and delivered offers are `UNKNOWN`. Candidate status is
explicit: neither output MOSFET pair nor an exact precision-divider resistor is frozen for manufacturing.
The original A/B libraries and lands are not changed by these reviews.

### BOM sourcing (DD-39, 2026-10-29)

Order codes and part identities for the 40 lines that were "select at order". Collected per MPN in
`engineering/design/budget-2s/sourcing.yaml`. Stock and prices seen while checking are **not** used for costing
(UNKNOWN until quoted).

| ID | Source | Locator | Reviewed scope |
|---|---|---|---|
| BUD-27 | Distributor part pages read directly, 2026-10-29 | `jlcpcb.com/partdetail/<code>`, `lcsc.com/product-detail/<code>.html`, DigiKey (RT0603BRD07133KL), element14 (3885982) | MPN, manufacturer and the stated value/tolerance/rating read from each page: C25804 0603WAF1002T5E, C21190 0603WAF1001T5E, C22775 0603WAF1000T5E, C25803 0603WAF1003T5E, C4190 0603WAF2201T5E (all 0603, ±1 %, 100 mW, ±100 ppm/°C); C17513 0805W8F1001T5E (1 k, ±1 %, 125 mW, JLC Basic); C14663 Yageo CC0603KRX7R9BB104 (100 nF 50 V X7R, Basic); C57112 FH 0603B103K500NT (10 nF 50 V X7R, Basic); C15849 Samsung CL10A105KB8NNNC (1 µF 50 V X5R, Basic); C29936 Samsung CL10B105KA8NNNC (1 µF 25 V X7R); C19666 Samsung CL10A475KO8NNNC (4.7 µF 16 V X5R); C12891 Samsung CL31A226KAHNNNE (22 µF 25 V X5R 1206, Basic); C2928896 Nippon Chemi-Con EMVL160ARA101MF80G (100 µF 16 V ±20 %, D6.3 × L7.7 mm, 81 mA at 120 Hz, −40…+105 °C); C315986 Littelfuse SMAJ10CA (bidirectional, SMA, VRWM 10 V, VBR 11.1 V, VC 17 V, IPP 23.5 A, 400 W 10/1000 µs; the page does not tie VC to IPP); C2296 KENTO KT-0805Y (yellow 0805, VF 1.8–2.4 V, Basic); C2918453 E-Switch TL3342F160QG/TR (SMD-4P 5.2 × 5.2 mm, Extended); C49257 BOOMELE 2.54-1*3P (1 × 3 male, 2.54 mm, through-hole); DigiKey RT0603BRD07133KL (133 kΩ ±0.1 %, ±25 ppm/°C, 0.1 W, Active, 44,048 shown); element14 3885982 Vishay TNPW06032K67BEEA (2.67 kΩ, 0.1 %, 125 mW, 75 V, TNPW e3; TCR not shown on the page). Rejected on reading: C2297 KT-0805G (emerald green, VF up to 3.1 V: too little current through the 1 kΩ from 3.3 V) and C77131 (NCP15XH103F03RC, an 0402 part). |
| BUD-28 | Web-search result snapshots, 2026-10-29 (not fetched pages) | LCSC/JLCPCB, RS UK, Farnell, DigiKey, Future Electronics, Mouser listings returned by search | C22809 0603WAF1502T5E (15 k), C22828 0603WAF1800T5E (180 Ω), C22935 0603WAF1004T5E (1 M, Basic), C22965 0603WAF2703T5E (270 k), C23179 0603WAF4700T5E (470 Ω, Basic), C25819 0603WAF4702T5E (47 k, Basic): all UNI-ROYAL 0603 ±1 % 100 mW ±100 ppm/°C. C114639 / RS 199-5645 Yageo RC0603FR-079K1L (9.1 k ±1 %). C21122 Samsung CL10B223KB8NNNC (22 nF 50 V X7R). C1636 FH 0603CG102J500NT (1 nF 50 V C0G ±5 %, Extended). C576818 Yageo CC0603JRNPO9BN472 (4.7 nF 50 V NP0 ±5 %). C13564 Murata NCP18XH103F03RB (10 kΩ ±1 %, B25/50 3380 K ±1 %, 0603; DigiKey marks it "Not For New Designs"). Panasonic ERA-3AEB family (0603, ±0.1 %, ±25 ppm/°C, 0.1 W, 75 V, AEC-Q200; three-digit value code for E24, four for E96): ERA-3AEB103V 10 k (RS 566-890 / 741-9789), ERA-3AEB134V 130 k (RS 179-9606 / 169-1170; LCSC C473257 datasheet link), ERA-3AEB2742V 27.4 k (RS 708-8855), ERA-3AEB2671V 2.67 k (DigiKey/Future, ±25 ppm stated; 12-week lead shown). Vishay TNPW e3 code: B = ±0.1 %, E = ±25 ppm/K; sibling BEEA listings state 25 ppm (Mouser TNPW060322K6BEEA, Future TNPW0603200KBEEA). Yageo RT code: B/C/D/E = ±10/15/25/50 ppm/°C (datasheet extracts; RT0603BRE0710KL listed at ±50 ppm), so RT…BRE parts do not meet 25 ppm. E-Switch TL3342F160QG (non-TR) shown obsolete/zero stock; the /TR variant shown in stock at DigiKey. |

Limits checked for D2 (no new download): BUD-01 TPS54821 p.4, VIN and PVIN absolute maximum 20 V; BUD-21 MCP1703A
p.3, VDD absolute maximum +18 V. The SMAJ10CA 17 V clamp (BUD-27) sits below both, with about 1 V margin to the
LDO at full rated pulse current.

### LCSC codes and connector datasheets (DD-40, 2026-10-29)

LCSC codes for the 21 lines that had none after DD-39, collected in `engineering/design/budget-2s/sourcing.yaml`.
Stock and prices seen while checking are **not** used (UNKNOWN until quoted). LCSC's own search page is rendered
by script and returned no results to a page fetch, so codes come from product pages found by web search or by
reading neighbouring codes.

| ID | Source | Locator | Reviewed scope |
|---|---|---|---|
| BUD-29 | LCSC product pages read directly, 2026-10-29 | `https://www.lcsc.com/product-detail/<code>.html` | MPN, manufacturer, package and the stated key attributes read from each page: C1852114 TI TLV803EA29DBZR (SOT-23-3, 2.93 V, 200 ms, open-drain active-low, 1.7–6 V); C2058238 TI INA186A2IDCKR (SC-70-6, 50 V/V); C2868382 TI TLV6700DDCR (TSOT-23-6, two open-drain channels, 1.8–18 V); C148015 Microchip MCP1703AT-3302E/MB (SOT-89-3, 3.3 V, 250 mA, 16 V); C614136 Microchip ATTINY1616-SN (SOIC-20-300mil); C154919 Diodes DMP2022LSS-13 (SO-8, P 20 V 10 A, ±12 V); C222439 Vishay SISS23DN-T1-GE3 (PowerPAK1212-8S, P 20 V, ±8 V); C20512 Diodes DMG1012T-7 (SOT-523, N 20 V 630 mA); C96676 Diodes DMG1013T-7 (SOT-523, P 20 V 460 mA); C550626 Nexperia BZX585-C10,115 (SOD-523, 9.5–10.5 V, 300 mW); C550667 Nexperia BZX585-C6V2,115 (SOD-523, 5.89–6.51 V, 300 mW); C780205 Bourns SRP1265A-4R7M (4.7 µH ±20 %, 8.4 mΩ, Isat 28 A); C431092 Changzhou Amass XT30PW-M30.G.Y (right-angle male, through-hole, 2-pin, 15 A); C5249699 Keystone 3568 (mini automotive blade fuse clip/holder, through-hole); C5188434 MAX MX126-5.0-02P-GN01-Cu-S-A (2-pole, 5 mm, through-hole, 10 A/300 V listed); C131337 JST B2B-PH-K-S(LF)(SN) (2-pin, 2.0 mm, through-hole, 2 A); C190610 Panasonic ERA3AEB103V; C861111 Yageo RT0603BRD07133KL; C855755 Yageo AT0603BRD0727K4L (27.4 kΩ); C855783 Yageo AT0603BRD072K67L (2.67 kΩ). The last four are 0603 thin film, ±0.1 %, ±25 ppm/°C, 100 mW. C1852114 and C861111 were found by reading neighbouring codes (C1852111–C1852117, C1852119; C861109–C861113: other TLV803E/TLV809E/TPS3840 parts and RT0603BRD07130/132/135KL). Not used: C1852118 TLV803EA29RDBZR (R pinout); TLV803EC29DBZR C2867948 and TLV803EB29DBZR C2869935 (10 ms and 40 µs delays; codes from LCSC page titles); C2862618 INA186A2QDCKRQ1 (the exact part was found). ERA-3AEB2742V and TNPW06032K67BEEA were not found on LCSC. |
| BUD-30 | Changzhou Amass Electronics, "Amass Product Specification", XT30PW20-M.G.* / XT30PW30-M.G.* (the LCSC datasheet of C431092), read 2026-10-29 | https://datasheet.lcsc.com/datasheet/pdf/f40c503d729038bd14858056d73ccb74.pdf?productCode=C431092 | Scanned, with no text layer; read as page images. p.1 model key: M = male, G = gold plated, Y = yellow. p.2: right-angle through-hole 2-pin. Welding height 2.0 mm (PW20) or 3.0 mm (PW30). DC 500 V, 15 A (UL1977). **Contact resistance 1.20 mΩ** (GB/T5095.2). Temperature rise < 60 °C at 15 A for 4 h; −20…120 °C. p.3 installation holes: 2 × Ø1.90 on 5.00 mm, plus 2 × Ø1.00 11.00 mm apart, 10.00 mm from the pin row. KiCad `AMASS_XT30PW-M` has 1.9 and 1.0 mm drills at those positions. No +/− polarity marks are shown. `budget_AMASS_XT30PW-M_LCSC-C431092.pdf`. |
| BUD-31 | Cixi MaiXu Electronics drawing MX126-5.0-XXP, 2022-09-14 (the LCSC datasheet of C5188434), read 2026-10-29 | https://datasheet.lcsc.com/datasheet/pdf/f81da43c133b386f14d372a038c5dc3a.pdf?productCode=C5188434 | Scanned; read as a page image. UL 300 V / 10 A. IEC 250 V / 15 A (pollution degree 2, overvoltage category III). 26–14 AWG, 0.5–2.5 mm², M2.5 screw. Pitch 5.0 mm, PCB holes Ø1.30; body 10.30 mm high, 7.80 mm deep; −40…+105 °C. Order-code key: GN01 = standard green, Cu = copper block, S = cross-head screw. LCSC lists the maker as "MAX". KiCad's `TerminalBlock_MaiXu_MX126-5.0-02P` (1.3 mm drill) cites the LCSC MAX MX126 3-pin datasheet (C5188435). `budget_MAIXU_MX126-5.0_LCSC-C5188434.pdf`. |

Used from an existing record (no new download): BUD-20 TLV803E p.3, Figure 5-1. Delay letter A = 200 ms (B 40 µs,
C 10 ms, D 50 ms, E 100 ms, F 400 ms). DBZ pinout letter R = pin 1 RESET, pin 2 GND; V = pin 1 RESET, pin 3 GND;
no letter keeps pin 1 = GND. Only TLV803EA29DBZR fits U4's land and its 200 ms delay.

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
| BUD-15 | `budget_Diodes_DMP2022LSS.pdf` | `94a2a4a80a597bc5e1de4668a484a45cbeda38bebba06eb59977d95f944cb4b8` |
| BUD-16 | `budget_Diodes_DMP2005UFG.pdf` | `e35ac98fe7f5bf3ef91413fc6132030799d319b91e8fc55e44f36f1df4d6de3d` |
| BUD-17 | `budget_AOS_AO3400A.pdf` | `9c60d0b6c1ddc7609a4b788a91181468d8ffe6c3e9ba425c3d8ffc5ba88c5033` |
| BUD-18 | `budget_TI_TLV6700.pdf` | `b97ac5c46caafd69bb762ee3da123e7906fb68394f552455a51b41385890c2fc` |
| BUD-19 | `budget_TI_SN74HCS74.pdf` | `eac261a31ca71eed79dd051ed66a03bbd5d837f88087023fd864a3599cfa95fa` |
| BUD-20 | `budget_TI_TLV803E.pdf` | `74ac4474d86c3597c4fff6ffa61a59e850130a40eda28085ece9765fb380e844` |
| BUD-21 | `budget_Microchip_MCP1703A.pdf` | `6fdfc2f20167c7292c92c9c4c8003fd4d8615e0f2f90e224e1e10dce6ed65b5f` |
| BUD-22 | `budget_Vishay_WSK2512.pdf` | `2ee8a9067539bd2cabb08845219bac55d506b1ca892a2dbaeed343dd1ed10cff` |
| BUD-24 | `budget_Vishay_WSL.pdf` | `96c2dc89ae1e3039815ed6c41f566a6e9f6b53035f8e45ea2ada1697935a44dc` |
| BUD-23 | `cmp_Diodes_DMG1013T.pdf` | `cf040fbdd079a8309c61065c347b6e9f85c3aed460fc3cd7a407fda9daf2f820` |
| BUD-26 | `budget_AMASS_XT30PW-M.pdf` | `fb61a47859734eef3482b54ba460cb6f04eeae10b1172be9032564e3c95a957d` |
| BUD-30 | `budget_AMASS_XT30PW-M_LCSC-C431092.pdf` | `db3ebbe3384b13e0b8d856a1d80261bb44a959c89a5d599e6523ba7868bc5523` |
| BUD-31 | `budget_MAIXU_MX126-5.0_LCSC-C5188434.pdf` | `8903251fb6869a2afab8018ea4fb8a10cb4749eedc79ef0efe9a9b0788af7b81` |
