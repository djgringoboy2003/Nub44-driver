# NUBM44 driver: supporting-component research

Author: component-selection agent. Data retrieved 2026-10-24. The lead engineer makes the final choices. Every number below comes from a datasheet in `research/datasheets/cmp_*` or from a distributor page listed in `research/sources/component-sources.md` (IDs CMP-xx). Anything that could not be verified is marked **UNKNOWN**. Stock and prices are LCSC product-page values from 2026-10-24 (CMP-37). Basic/Extended status and JLC assembly stock come from the JLCPCB parts API (CMP-36).

Machine-readable table: `research/component-candidates.csv` (65 rows).

## 0. Loss budget used for the selections

| Operating point | P_out | Efficiency target | P_in | I_in | Total loss allowed |
|---|---|---|---|---|---|
| V_in = 3.0 V, 4 A × 5.0 V | 20 W | 86 % | 23.3 W | 7.75 A | 3.26 W |
| V_in = 4.0 V, 4 A × 5.0 V | 20 W | 95 % | 21.05 W | 5.26 A | 1.05 W |

The 4 V point is the hard one. Every milliohm in the input path costs 5.26² = 27.7 mW, which is 2.6 % of the whole loss budget. Every milliohm in the 4 A laser path costs 16 mW.

## 1. Audit of the earlier proposed parts

| Part | Role | Problem found (datasheet numbers) | Verdict |
|---|---|---|---|
| 0.15 Ω, 0.5 W sense resistor | Laser current shunt | P = 0.15 Ω × (4 A)² = **2.4 W**, 4.8× its 0.5 W rating. The 0.6 V drop wastes 12 % of the 20 W output, so this part alone breaks both efficiency targets. | **Reject.** Use 3–5 mΩ plus an amplifier (§2.1): 48–80 mW. |
| TI LM358 (CMP-01, SLOS068AB) | Error / sense amplifier | V_OS max 7 mV (LM358) or 3 mV (LM358A/B) at 25 °C, against a 20–40 mV shunt signal: **17–35 % error** (7.5–15 % for the B version). Input common-mode range only reaches (V+) − 1.5 V at 25 °C and (V+) − 2 V over temperature. On a 2.8–4.2 V supply that tops out at 0.8–2.7 V, so it **cannot sense the high side at 4.3–5 V**. Recommended minimum supply is 3 V, above the 2.8 V cell cutoff. GBW is 0.7 MHz. Packages are SOIC-8, VSSOP-8 and SOT-23-8. | **Reject** for current sensing. A zero-drift CSA or op-amp gives about 100× lower offset. |
| Microchip ATtiny13A (CMP-04, DS40002307A) | MCU | Supply 1.8–5.5 V is fine (≤4 MHz at 1.8 V, ≤10 MHz at 2.7 V). No DAC. The 10-bit ADC on its 1.1 V reference gives 1.07 mV/LSB, so a 20–40 mV shunt reads only 19–37 counts. Programming is SPI ISP (RESET, SCK, MISO, MOSI, VCC, GND), which needs 6 pads. Clearing RSTDISBL needs 12 V HV serial programming. Packages: SOIC-8 (4.9 × 6 mm), SOIJ-8, VDFN-10 3 × 3 mm (ATtiny13A-MMU, LCSC C1522083, **7 pcs** in stock) and WQFN-20 4 × 4 mm. | **Replace.** Usable, but the ATtiny1616 (§2.5) adds a DAC, comparators and 1-wire UPDI in 3 × 3 mm. |
| AOS AO3400A (CMP-02, Rev 3.1) | Boost switch / laser FET | R_DS(on) max 32 mΩ at 4.5 V and 48 mΩ at 2.5 V. I_D is 5.7 A at 25 °C (t ≤ 10 s rating), below the 7.75 A inductor current. R_θJA is 100 typ / 125 max °C/W steady state. As a boost switch at 3 V in: I_rms ≈ 7.75 A × √0.45 ≈ 5.2 A, so conduction loss is ≈ 0.87 W at 25 °C before temperature rise and switching loss. That is a ≈ 110 °C junction rise, which fails. As the 4 A laser FET: 0.51 W at 4.5 V gate (64 °C rise) and 0.77 W at 2.5 V gate (96 °C rise). | **Reject** for power paths. Fine as a small-signal gate driver (V_th 0.65–1.45 V; JLC Basic C20917). |
| AOS AO4407A (CMP-03, Rev 11.1) | Reverse-polarity P-FET | V_GS(th) is −1.7 / −2.3 / **−3.0 V** (min/typ/max). R_DS(on) is specified only at −20, −10 and −6 V (11, 13 and 17 mΩ max). The output curves start at −3.5 to −4 V. With V_GS = −V_bat = −2.8 to −3.0 V the FET is at or below its maximum threshold and **cannot carry 8 A**. SOIC-8 is 5 × 6 mm. | **Reject.** Use the 2.5 V-rated FETs in §2.2. |
| 10 µH boost inductor | Boost inductor | At 0.5–2.2 MHz, 10 µH gives needlessly small ripple, and no 10 µH part fits with I_sat ≥ 11 A. Example in a 4 × 4 mm body: Coilcraft XGL4030-103ME (CMP-32) has DCR 69.5 mΩ max (4.2 W loss at 7.75 A) and I_sat 2.3 A at 20 % drop. Energy scales as L·I_sat². 10 µH × (11 A)² = 1210 µJ against 53 µJ for XGL4030-401ME, about 23× more core. That estimate puts it far beyond a 22 mm board. | **Reject.** Use 0.27–0.47 µH, 11.5–15.5 A (§2.3). |

## 2. Category comparisons and recommendations

### 2.1 Current sensing

**Shunt resistors** (4 A full scale):

| MPN (mfr) | Value / type | Rating | TCR | Size (mm) | P at 4 A | LCSC (stock, price) | Notes |
|---|---|---|---|---|---|---|---|
| **WSKW06125L000FEA** (Vishay, CMP-34) | 5 mΩ, **4-terminal Kelvin**, Mn-Cu | 1.0 W at 70 °C | ±75 ppm/°C (3–5 mΩ, including terminals); element < 20 ppm/°C | 1.50 × 3.05 × 0.46 (0612) | 80 mW | C4236646 (244, $1.11@1) | **1st choice.** True Kelvin sense pins E1/E2. Low stock. |
| **WSKW06123L000FEA** (Vishay, CMP-34) | 3 mΩ, 4-terminal | 1.0 W | ±75 ppm/°C | same | 48 mW | C1517434 (5176, $0.56@1) | **Alternate**, better stock. 12 mV at 4 A, so pair it with gain 100 (1.2 V out). |
| WSLP12065L000FEA (Vishay) | 5 mΩ, 2-terminal | 1 W (LCSC listing) | ±110 ppm/°C (listing) | 3.2 × 1.6 (1206) | 80 mW | C844909 (10323, $0.46) | Needs a Kelvin-split land pattern. Datasheet not retrieved. |
| WSLP20105L000FEA (Vishay) | 5 mΩ | 2 W (listing) | ±110 ppm/°C | 5.0 × 2.5 (2010) | 80 mW | C2094890 (1270, $1.01) | Larger than needed. |
| PA1206FRF070R005L (Yageo) | 5 mΩ | 0.25 W (listing) | ±100 ppm/°C | 1206 | 80 mW | LCSC page not fetched (JLC C875583, 48) | Only 3× margin. Niche. |
| Bourns CSS2H-2512 | 1–2 mΩ only on JLC (no 5 mΩ found) | 3–5 W | ±50–75 ppm/°C | 2512 | — | JLC C2093761 (2 mΩ) | Too big. |

Choose a value from the converter's FB reference. V_FB = I × R × G: 5 mΩ × 4 A × 50 = 1.0 V, and 3 mΩ × 4 A × 100 = 1.2 V.

**Current-sense amplifiers.** All are TI except TSC213:

| MPN | Supply | Common mode | V_OS max (RTI) | Gain options (V/V) | BW (gain 50/100) | Package | LCSC (stock, price) |
|---|---|---|---|---|---|---|---|
| **INA186A2/A3IDCKR** (CMP-05) | **1.7–5.5 V** | **GND − 0.2 to 40 V** | **±50 µV**; drift 0.5 µV/°C | 25/50/100/200/500 | 37 / 35 kHz | SC70-6 | A2 C2058238 (9836, $0.87); A3 C2058245 (4792, $1.02) |
| INA190A3IDCKR (CMP-08) | 1.7–5.5 V | −0.2 to 40 V | **±15 µV**; 80 nV/°C | 25…500 | 37 / 35 kHz | SC70-6 | C2058578 (4810, $1.53) |
| **INA185A2IDRLR** (CMP-07) | 2.7–5.5 V | −0.2 to 26 V | ±55 µV (V_CM = 0) / ±130 µV (V_CM = 12 V) | 20/50/100/200 | **210 / 150 kHz** | **SOT-563, 1.6 × 1.6** | C2059320 (3979, $1.13) |
| INA181A2IDBVR (CMP-06) | 2.7–5.5 V | −0.2 to 26 V | ±150 µV (V_CM = 0) / ±500 µV (12 V) | 20/50/100/200 | 210 / 150 kHz | SOT-23-6 | C2058784 (55315, $0.37@5) |
| INA199A1DCKR (CMP-09) | 2.7–26 V | −0.3 to 26 V | ±150 µV | 50/100/200 | 80 / 30 kHz | SC70-6 | C59135 (85020, $0.41) |
| TSC213ICT (ST, CMP-10) | 2.7–26 V | −0.3 to 26 V | 35 µV max quoted for TSC210; **TSC213 value not extracted** | 50 | UNKNOWN | SC70-6 | JLC stock 0. LCSC UNKNOWN. |
| MAX9938FEUK+T (ADI) | UNKNOWN (datasheet download failed) | high-side | UNKNOWN | 25 | UNKNOWN | SOT-23-5 | LCSC UNKNOWN (JLC 100) |
| MAX4080 | Its own JLC family listing gives CM 4.5–76 V. Not usable at 4.3 V or on the low side. | — | — | — | — | SOIC/µMAX | Rejected |

Offset at a 20 mV full scale (5 mΩ, 4 A): INA186 ±0.25 %, INA190 ±0.075 %, INA185 ±0.65 % (high side), INA181 ±2.5 % (high side), LM358 up to ±35 %. At 10 % current (0.4 A, 2 mV) multiply each figure by 10.

* **First choice: INA186A2IDCKR** (or A3 with a 3 mΩ shunt). It is the only well-stocked part that runs directly from the cell down to 1.7 V. Its common-mode range does not depend on the supply, so it senses at the 4.3–5 V high side while powered from 2.8–4.2 V. It also offers a REF pin for offsetting.
* **Alternate: INA185A2IDRLR.** Use it if the converter's CC loop needs a faster sense path: 210 kHz against 37 kHz. At a 10 kHz crossover that is about 3° of phase lag instead of 15°, roughly 12° less. Its footprint is also the smallest at 1.6 × 1.6 mm. Its minimum supply of 2.7 V leaves only 0.1 V below the 2.8 V cutoff.
* Use INA190 if low-current-mode accuracy matters (±15 µV).

**Zero-drift op-amps** (error amplifier, or a discrete low-side amplifier with the shunt at ground):

| MPN | Supply | V_OS max | GBW | I_Q | Package | LCSC (stock, price) |
|---|---|---|---|---|---|---|
| **OPA387DBVR** (CMP-14) | 1.7–5.5 V | ±2 µV | 5.7 MHz | 570 µA | SOT-23-5 | C4366709 (7660, $1.56) |
| **OPA333AIDCKR** (CMP-11) | 1.8–5.5 V | 10 µV (5 V) | 350 kHz | 17 µA typ | SC70-5 (also SOT-23-5, C30878: 8256) | C44193 (2827, $1.29) |
| TLV333IDCKR (CMP-13) | 1.8–5.5 V | 15 µV | 350 kHz | 17 µA | SC70-5 | C181502 (14550, $0.31@5) |
| OPA388IDBVR (CMP-12) | 2.5–5.5 V | ±5 µV | 10 MHz | (see datasheet) | SOT-23-5 | C1850240 (2180, $2.55) |
| TSZ121ICT (ST, CMP-17) | 1.8–5.5 V | 5 µV at 25 °C, 8 µV over temperature | 400 kHz | 40 µA max | SC70-5 | C2058276 (2143, $1.77) |
| TLV9061 / TLV9001 (CMP-15/16) | 1.8–5.5 V | **±1.6 mV** | 10 / 1 MHz | 538 / 60 µA | SOT-23-5, SC70-5 | LCSC pages not fetched (JLC: TLV9061IDBVR C398358 273k; TLV9001IDBVR C398363 42k) |

TLV9061 and TLV9001 are not zero-drift. Their 1.6 mV offset is 4–8 % of a 20–40 mV signal, so use them only after gain. **Recommendation:** OPA387 for speed, TLV333 for cost, OPA333 for lowest current.

### 2.2 MOSFETs

**(a) Reverse-polarity protection, about 8 A** (losses use the 25 °C maximum R_DS(on); multiply by the datasheet's normalized-R_DS(on)-versus-temperature factor for hot operation):

| MPN | Type | R_DS(on) max at 10 / 4.5 / 2.5 / 1.8 V (mΩ) | V_GS(th) | Q_g | Package | P at 7.75 A / 5.26 A | LCSC (stock, price) |
|---|---|---|---|---|---|---|---|
| **IRLHM620TRPBF** (Infineon, CMP-18) | N 20 V | 2.2 / 2.5 / **3.5** / — | 0.5–1.1 V | 52 typ / 78 max nC | PQFN 3.3 × 3.3 | 0.21 W / 0.07–0.10 W | **C538149 (4332, $0.28)** |
| DMN2002UFG-7 (Diodes, CMP-19) | N 20 V | 1.4 / 1.7 / **2.4** / — | 0.5–1.3 V | 53 nC at 4.5 V | PowerDI3333-8 | 0.14 W / 0.05–0.07 W | **Not listed at LCSC/JLC.** DigiKey/Mouser UNKNOWN. |
| DMN22M5UFG-7 (Diodes, CMP-20) | N 20 V | — / 2.0 / 2.6 / — | 0.5–1.3 V | 53 nC | PowerDI3333-8 | 0.16 W | C3289380 (**0**) |
| SiSS80DN (Vishay, CMP-21) | N 20 V | 0.92 / 1.15 / 3.0 / — | 0.6–1.5 V | 36 nC | PowerPAK 1212-8S | 0.18 W | JLC stock 0. LCSC page not fetched. |
| AON7404G (AOS, CMP-40) | N 20 V | — / 4.3 / 6.8 / — | — | — | DFN 3 × 3 | 0.41 W | Rejected |
| **SiSS23DN-T1-GE3** (Vishay, CMP-22) | **P** −20 V (V_GS ±8 V) | — / 4.5 / **6.3** / 11.5 | −0.4 to −0.9 V | 93 nC | PowerPAK 1212-8S, 3.3 × 3.3 × 0.75 | 0.38 W / 0.12–0.17 W | C222439 (**220**, $1.86) |
| DMP2005UFG-13 (Diodes, CMP-24) | P −20 V (±8 V) | — / 4.0 / **6.5** / 14 | −0.3 to −0.9 V | 55 nC at −4.5 V | PowerDI3333-8 | 0.39 W / 0.11–0.18 W | C2922355 (**119**, $1.31) |
| SiSH615ADN (Vishay, CMP-23) | P −20 V | — / 6.0 / 9.8 / — | −0.4 to −1.5 V | 59 nC | PowerPAK 1212-8SH | 0.59 W | JLC 50 |
| AON7407 (AOS, CMP-39) | P −20 V | — / 9.5 / 12.5 / 18 | −0.3 to −0.9 V | 44 nC | DFN 3 × 3 | 0.75 W | Rejected |

* **First choice: IRLHM620TRPBF as a low-side N-FET.** Source goes to battery negative (the perimeter ring) and drain to circuit ground, with the gate pulled to B+ through a resistor so V_GS = V_bat ≥ 2.8 V. It loses 0.21 W worst case at 3 V in, against 0.38 W for the best P-FET. It is the only ≤ 4 mΩ (at 2.5 V) part with real LCSC stock, and it costs $0.28.
  * Caveat: the circuit ground then differs from the body/ring by the FET drop. Account for this in the sense and MCU references.
* **High-side P option (if a split ground is unacceptable): SiSS23DN** (6.3 mΩ at −2.5 V), with DMP2005UFG as the alternate. Both have low LCSC stock, so plan a DigiKey/Mouser buy (stock UNKNOWN).
* No 2 × 2 mm part reaches ≤ 4 mΩ at 2.5 V in this search. The best 2 × 2 option found is IRLHS6242 at 15.5 mΩ.

**(b) Laser-path series disconnect / current-limit FET (4 A continuous):**

| MPN | R_DS(on) max at 2.5 V | P at 4 A | Thermal | SOA figure | LCSC |
|---|---|---|---|---|---|
| **IRLHM620TRPBF** | 3.5 mΩ (2.5 mΩ at 4.5 V) | **56 mW** | R_θJA 46 °C/W (31 °C/W, t < 10 s); R_θJC 3.4 | Fig 8, single pulse, **T_C = 25 °C**, with a DC line | C538149 (4332) |
| IRLHS6242TRPBF (CMP-25) | 15.5 mΩ (11.7 mΩ at 4.5 V) | 0.25 W | R_θJA 63 °C/W (46 °C/W, < 10 s) | Fig 8 | C150933 (17700, $0.26@5) |
| SiSS23DN (if a P-FET suits a high-side disconnect) | 6.3 mΩ at −2.5 V | 0.10 W | R_thJA 26 °C/W max (t ≤ 10 s) | **Junction-to-ambient** SOA with 10 s and DC lines | C222439 (220) |

* **Recommendation:** use IRLHM620 here too, so the design shares one part.
* **Linear-mode warning:** the Infineon and Diodes SOA curves are referenced to T_C = 25 °C on an infinite heatsink. They do not hold for a 22 mm FR-4 board.
  * Derate them with R_θJA and the transient-impedance curve, or prefer a part with a junction-to-ambient SOA (Vishay SiSS23DN, SiSS80DN).
  * Thermal instability of trench FETs at low V_DS × high I_D in linear mode cannot be judged from these datasheets: **UNKNOWN, verify on the bench**.

**(c) Small-signal gate-control FETs:**

| MPN | Type | R_DS(on) max at 4.5 / 2.5 / 1.8 V | V_GS(th) | Package | LCSC (stock, price) |
|---|---|---|---|---|---|
| **DMG1012T-7** (CMP-26) | N 20 V | 0.4 / 0.5 / 0.7 Ω | 0.5–1.0 V | SOT-523 (1.6 × 1.6) | C20512 (124900, $0.10@5) |
| **DMG1013T-7** (CMP-27) | P −20 V | 0.7 / 0.9 / 1.3 Ω | −0.5 to −1.0 V | SOT-523 | C96676 (100640, $0.05@10) |
| AO3401A (CMP-31) | P −30 V | 60 / 85 mΩ at −4.5 / −2.5 V | −0.5 to −1.3 V | SOT-23 | C15127 (149400; **JLC Basic**) |
| AO3400A (CMP-02) | N 30 V | 32 / 48 mΩ | 0.65–1.45 V | SOT-23 | C20917 (654750; **JLC Basic**) |
| SSM3K35AMFV / SSM3J35AMFV (Toshiba, CMP-28/29) | N / P 20 V | **UNKNOWN** (table not machine-readable) | UNKNOWN | VESM/SOT-723 (1.2 × 1.2) | C150155 (19580, $0.036@10) / JLC C5274156 |
| NX3008NBKW (Nexperia, CMP-30) | N 30 V | 1.4 Ω at 4.5 V; no 2.5 V figure extracted | — | SOT-323 | JLC C282548 |

**Recommendation:** DMG1012T / DMG1013T. Both are fully specified at 1.8 V and well stocked. Use AO3400A / AO3401A where a JLC Basic part with tens of mΩ is useful, for example an LED or load switch.

### 2.3 Power inductor (boost, 0.5–2.2 MHz)

Ripple example: L = 0.40 µH, 1 MHz, V_in = 3.0 V, D ≈ 0.46. ΔI = 3.0 × 0.46 / (0.40 µH × 1 MHz) = 3.45 A p-p, so I_pk ≈ 7.75 + 1.73 = 9.5 A. At 2 MHz, I_pk ≈ 8.6 A.

| MPN (Coilcraft unless noted) | L | DCR typ/max | I_sat at 10 / 20 / 30 % drop | I_rms (20 / 40 °C rise) | Size (mm) | DCR loss at 7.75 / 5.26 A | LCSC (stock, price) |
|---|---|---|---|---|---|---|---|
| **XGL4030-401MEC** (CMP-32) | 0.40 µH | 2.8 / **3.2 mΩ** | 7.2 / **11.5** / 15.5 A | 15.5 / 22.5 A | 4.0 × 4.0 (height: drawing on p.1) | 0.19 / 0.09 W | C7397005 (**48**, $5.44) |
| XGL4030-271MEC (CMP-32) | 0.27 µH | 2.2 / 2.4 mΩ | 9.2 / 14.4 / 19.3 A | 17.5 / 24.2 A | 4 × 4 | 0.14 / 0.07 W | C7417190 (34, $5.79) |
| XGL4030-301ME / -471ME | 0.30 / 0.47 µH | 2.9 / 3.9 mΩ max | 12.5 A / 10.6 A at 20 % | 17.0 / 15.3 A | 4 × 4 | — | -471: C5837791 (JLC 0) |
| **XEL4030-471MEC** (CMP-33) | 0.47 µH | 4.10 / 4.60 mΩ | **15.5 A (30 % drop; only figure given)** | 12.3 / 15.6 A | 4 × 4 | 0.28 / 0.13 W | **C19191694 (984, $4.28)** |
| XEL4030-641ME (CMP-33) | 0.64 µH | 5.30 / 5.90 mΩ | 13.5 A (30 %) | 10.9 / 13.7 A | 4 × 4 | 0.35 W | — |
| XGL4030-102ME (CMP-32) | 1.0 µH | 6.5 / 7.2 mΩ | 4.8 / 7.6 / 10.3 A | 10.8 / 13.0 A | 4 × 4 | 0.43 W | Fails 11 A |
| XAL5030-102MEC | 1.0 µH | UNKNOWN | UNKNOWN | UNKNOWN | 5.3 × 5.5 (listing) | — | C5379798 (630, $8.50) |
| Vishay IHLP2525CZER1R0M01 | 1.0 µH | UNKNOWN | UNKNOWN | UNKNOWN | 6.9 × 6.5 (listing) | — | C845018 (9068, $0.55) |
| Sunlord MWSA0503S-R47MT | 0.47 µH | UNKNOWN | UNKNOWN | UNKNOWN | 5.4 × 5.2 (listing) | — | LCSC UNKNOWN (JLC C408353, 3501) |
| TDK SPM6530T-1R0M120 | 1.0 µH | UNKNOWN | UNKNOWN | UNKNOWN | 7.1 × 6.5 (listing) | — | JLC C87572 (4789) |

* **First choice: XGL4030-401MEC** at 1–2.2 MHz. It has the lowest DCR that meets ≥ 11 A at a 20 % drop in a 4 × 4 mm body. LCSC stock is thin, so buy it from Coilcraft or DigiKey (stock UNKNOWN).
* **Alternate: XEL4030-471MEC.** It has the best LCSC stock, but note that its 15.5 A I_sat is a **30 %-drop** figure.
* Core/AC loss is **UNKNOWN**: run the Coilcraft loss calculator once the converter frequency is fixed.
* If the converter needs 1 µH at about 0.5 MHz, a 4 × 4 part cannot reach 11 A. Move to 5 × 5 or 6.5 × 6.5 (XAL5030 or IHLP-2525; specs to verify).

### 2.4 MLCC capacitors

| MPN | Value | Size | LCSC (stock, price) | JLC | DC-bias at 4–5 V |
|---|---|---|---|---|---|
| Samsung CL21A226MOQNNNE | 22 µF 16 V X5R | 0805 | C98190 (19970, $0.092@10) | Extended | **UNKNOWN** |
| Murata GRM21BR61C226ME44L | 22 µF 16 V X5R | 0805 | C86817 (**0**) | Extended | UNKNOWN (Murata SimSurfing not retrieved) |
| Samsung CL31A476MPHNNNE | 47 µF 10 V X5R | 1206 | C96123 (13700, $0.157@5) | **Basic** | **UNKNOWN**. The 10 V rating is only 2× the 5 V output. |
| Samsung CL05B104KO5NNNC | 100 nF 16 V X7R | 0402 | C1525 (6.13 M, $0.0036@100) | **Basic** | n/a |
| Samsung CL05A105KO5NNNC | 1 µF 16 V X5R | 0402 | C29266 (2.39 M, $0.0055@100) | Extended (per API) | n/a |

**Recommendation:** use 16 V 22 µF 0805 parts in parallel on the input and output. Size the bank from manufacturer DC-bias curves (Murata SimSurfing, Samsung, TDK), which were **not retrieved** in this pass. Do not assume nominal capacitance at 5 V.

### 2.5 Microcontroller

| MPN | Package | Supply | Programming | Analog | LCSC (stock, price) | Verdict |
|---|---|---|---|---|---|---|
| **ATTINY1616-MNR** (CMP-35) | VQFN-20 **3 × 3** | **1.8–5.5 V** (≤5 MHz at 1.8 V; ≤10 MHz at 2.7 V) | **UPDI 1-wire** on PA0 (pin 19). Tools: Microchip PICkit 4/5, MPLAB SNAP, Atmel-ICE, or SerialUPDI (USB-UART + resistor, avrdude/pymcuprog). | 8-bit DAC0 (out on PA6), 3 analog comparators, 2 × 10-bit ADC, 16 KB flash / 2 KB SRAM | C507118 (3507, $1.10) | **1st choice** |
| ATtiny3216-MNR | same | same | same | 32 KB | **Not found on JLC/LCSC** | DigiKey/Mouser UNKNOWN |
| PY32F003F16U6TR (Puya) | QFN-20 3 × 3 | **UNKNOWN** for this MPN | SWD 2-wire + Puya device pack | 12-bit ADC (family); no DAC | C3018714 (6620, $0.33@5) | **Alternate** (cost) |
| PY32F002AF15P6TU (Puya) | TSSOP-20 (large) | 1.7–5.5 V (LCSC listing) | SWD | 12-bit ADC | C5292059 (52715, $0.215@5) | Too large in TSSOP. QFN variant not checked. |
| CH32V003F4U6 (WCH) | QFN-20 3 × 3 | **UNKNOWN** (datasheet not retrieved; confirm minimum V_DD against the 2.8 V cutoff) | 1-wire SWIO, WCH-LinkE | 10-bit ADC, op-amp/comparator | C5299908 (1030, $0.315@5) | Possible; verify |
| ATTINY10-TSHR | SOT-23-6 | 1.8–5.5 V (listing) | TPI: TPIDATA, TPICLK, RESET. **Programming at 5 V only** (CMP-42, secondary). 12 V on RESET only to recover RSTDISBL. | 8-bit ADC, AC, 1 KB / 32 B | C128438 (2030, $1.00) | Not recommended: the whole cell rail must be lifted to 5 V for programming, and memory is tiny. |
| ATTINY412-SSNR | **SOIC-8** (LCSC listing) | 1.8–5.5 V | UPDI | DAC, AC | C1337190 (3096, $0.74) | Too large |
| ATtiny13A (audit) | SOIC-8 / VDFN-10 | 1.8–5.5 V | SPI ISP, 6 pads | ADC, AC | C40382 (9595, $1.26) / C1522083 (7) | Replace |

ATtiny1616 rationale:
* The DAC sets the current reference directly; no PWM-RC ripple.
* A DAC-referenced comparator gives a hardware over-current trip independent of firmware.
* One programming pad plus GND and V_DD.
* The 3 × 3 mm body fits the 22 mm board.

### 2.6 Protection and miscellaneous

| Item | MPN | Key data | LCSC (stock, price) | Notes |
|---|---|---|---|---|
| Anti-parallel Schottky across the LD | **PMEG4010CEJ,115** (Nexperia) | 40 V, 1 A, V_F 570 mV at 1 A (LCSC listing). **V_F at mA level and C_j UNKNOWN.** | C50704 (16100, $0.37@5) | Smallest reputable part found (SOD-323F) |
| | B5819W (MDD) | 40 V, V_F 600 mV at 1 A (listing) | C64885 (747450, $0.02@50) | JLC preferred. Its Jiangsu Changjing B5819W (C8598) is Basic. |
| | SS34 (MDD) | 40 V 3 A, V_F 550 mV at 3 A (listing) | C8678 (2.80 M) | JLC Basic, but SMA is oversized |
| ESD/TVS on the LD | — | **Not researched (budget)** | — | UNKNOWN |
| NTC 0402 | **Murata NCP15XH103F03RC** | 10 kΩ ±1 %, B25/50 = 3380 K (listing) | C77131 (297300, $0.02@50) | |
| | Murata NCP15WF104F03RC | 100 kΩ ±1 %, B25/50 = 4250 K (listing) | C77130 (299660, $0.02@20) | |
| Battery spring | — | **UNKNOWN (not researched).** The candidate must carry about 8 A or be bypassed. | — | Check Keystone, MPD and Harwin SMT/THT springs (current rating, free height, pad size). |
| Gold perimeter ring | PCB copper ring with ENIG (or hard gold) finish | PCBWay finish options not verified in this pass | — | Stitch the ring to the ground plane with many vias. It carries the full 8 A return. |
| Test pads | ENIG round pads, 1.0–1.5 mm | UPDI + V_DD + GND (3 pads) for the ATtiny1616 | — | |

## 3. Pinouts of the recommended parts (verbatim from datasheets)

**INA186, DCK (SC70-6)**, CMP-05 Table 5-1, p.3:

| Name | DCK pin | Type | Description (verbatim) |
|---|---|---|---|
| REF | 1 | — | (reference input; full text truncated in extraction, see p.3) |
| GND | 2 | Analog | Ground |
| VS | 3 | — | Supply. This row was lost in extraction. Pin 3 follows by elimination and matches the INA190 DCK drawing (CMP-08 p.3: "1 REF, 2 GND, 3 VS, 4 IN+, 5 IN−, 6 OUT"). |
| IN+ | 4 | Analog input | "Current-sense amplifier positive input. For high-side applications, connect to bus voltage side of sense resistor. For low-side applications, connect to load side of sense resistor." |
| IN– | 5 | Analog input | "Current-sense amplifier negative input. For high-side applications, connect to load side of sense resistor. For low-side applications, connect to ground side of sense resistor." |
| OUT | 6 | Analog output | "OUT pin. This pin provides an analog voltage output that is the gained up voltage difference from the IN+ to the IN– pins, and is offset by the voltage applied to the REF pin." |
| ENABLE | — | Digital input | DDF and YFD packages only |

Land pattern: CMP-05 Figure 10-1 "Recommended Layout for SC70 (DCK) Package" (p.25–26) and the DCK0006A package addendum.

**IRLHM620 (PQFN 3.3 × 3.3)**, CMP-18: the pin drawing on p.1 is a graphic and could not be extracted. The usual IR PQFN 3.3 × 3.3 assignment is S on pins 1–3, G on pin 4, and D on pins 5–8 plus the pad. **Verify against p.1.** Footprint and stencil: "refer to application note AN-1136" (stated in the datasheet's package/mounting notes: http://www.irf.com/technical-info/appnotes/an-1136.pdf).

**SiSS23DN (PowerPAK 1212-8S)**, CMP-22 p.1, verbatim text order "Bottom View … G 1 2 3 4 / 8 7 6 5 … S S S D D D D": pins 1–3 = S, pin 4 = G, pins 5–8 = D (drain pad). Land pattern: Vishay PowerPAK 1212-8S application note, **document number UNKNOWN**.

**DMP2005UFG (PowerDI3333-8)**, CMP-24 p.1: "Bottom View … S S S G / D D D D … Pin 1". Pins 1–3 = S, 4 = G, 5–8 = D. Diodes publishes the suggested pad layout at the end of the datasheet.

**DMG1012T / DMG1013T (SOT-523)**, CMP-26/27 p.1, "Top View: G, S, D". Pin 1 = G, 2 = S, 3 = D per the drawing order; verify against the drawing.

**WSKW0612**, CMP-34 p.1: "4 TERMINAL KELVIN CONNECTIONS: E1 and E2: voltage sense connection; I1 and I2: current connection". Solder pad dimensions are on p.2.

**ATtiny1616 VQFN-20**, CMP-35 Table 5-1 "PORT Function Multiplexing", p.17 (VQFN pin → pin name and key functions, verbatim tokens):

| VQFN | Pin | Functions (excerpt) |
|---|---|---|
| 1 | PA2 | EVOUT0, AIN2, RxD(3), MISO, SCL(3), LUT0-IN2 |
| 2 | PA3 | EXTCLK, AIN3, XCK(3), SCK, WO3, TCB1 WO |
| 3 | GND | |
| 4 | VDD | |
| 5 | PA4 | AIN4, AIN0, X0/Y0, XDIR(3), SS, WO4, WOA, LUT0-OUT |
| 6 | PA5 | VREFA, AIN5, AIN1, X1/Y1, OUT, AINN0, WO5, TCB0 WO, WOB |
| 7 | PA6 | AIN6, AIN2, X2/Y2, AINN0 AINP1 AINP0, **OUT (DAC0)** |
| 8 | PA7 | AIN7, AIN3, X3/Y3, AINP0 AINP0 AINN0, LUT1-OUT |
| 9 | PB5 | CLKOUT, AIN8, X12/Y12, AINP1, AINP2, WO2(3) |
| 10 | PB4 | AIN9, X13/Y13, AINN1, AINP3, WO1(3), LUT0-OUT(3) |
| 11 | PB3 | TOSC1, OUT, RxD, WO0(3) |
| 12 | PB2 | TOSC2, EVOUT1, OUT, TxD, WO2 |
| 13 | PB1 | AIN10, X4/Y4, AINP2, XCK, SDA, WO1 |
| 14 | PB0 | AIN11, X5/Y5, AINP2 AINP1, XDIR, SCL, WO0 |
| 15 | PC0 | AIN6, X6/Y6, SCK(3), TCB0 WO(3), WOC |
| 16 | PC1 | AIN7, X7/Y7, MISO(3), WOD, LUT1-OUT(3) |
| 17 | PC2 | EVOUT2, AIN8, X8/Y8, MOSI(3) |
| 18 | PC3 | AIN9, X9/Y9, SS(3), WO3(3), LUT1-IN0 |
| 19 | PA0 | **RESET/UPDI**, AIN0, LUT0-IN0 |
| 20 | PA1 | AIN1, TxD(3), MOSI, SDA(3), LUT0-IN1 |

The column alignment of the analog functions (ADC0, ADC1, AC0–AC2) is ambiguous in the extracted text. Confirm the AC and DAC assignments against p.17 before schematic capture. The VQFN-20 drawing is in the datasheet's package section (page not extracted).

## 4. Sourcing summary and UNKNOWNs

* **High-volume, safe parts** (LCSC stock > 10 k on 2026-10-24):
  * INA181A2 (55 k) and INA199A1 (85 k)
  * DMG1012T (125 k) and DMG1013T (101 k)
  * AO3400A (655 k, Basic) and AO3401A (149 k, Basic)
  * IRLHS6242 (17.7 k)
  * MLCCs: C1525 (Basic), C29266, C98190 (20 k), C96123 (Basic, 13.7 k)
  * NTCs C77130 and C77131 (around 300 k)
  * B5819W and SS34 (Basic)
  * PY32F002A (53 k)
* **Medium stock** (1 k–10 k):
  * INA186A2/A3 (9.8 k / 4.8 k), INA185A2 (4.0 k), INA190A3 (4.8 k)
  * OPA387 (7.7 k), OPA333 (2.8–8.3 k), TLV333 (14.6 k)
  * IRLHM620 (4.3 k)
  * WSKW0612 3 mΩ (5.2 k)
  * ATtiny1616 (3.5 k), PY32F003 QFN (6.6 k), CH32V003 QFN (1.0 k), ATtiny10 (2.0 k)
  * IHLP2525 1 µH (9.1 k)
* **Niche / thin** (< 1 k): plan a second source or a DigiKey/Mouser buy.
  * WSKW0612 5 mΩ (244)
  * SiSS23DN (220), DMP2005UFG (119)
  * XGL4030-401 (48), XGL4030-271 (34), XEL4030-471 (984), XAL5030-102 (630)
  * ATtiny13A-MMU (7)
  * DMN22M5UFG, SiSS80DN, GRM21BR61C226ME44L (0)
* JLC library status: almost everything above is **Extended**. Basic parts: AO3400A (C20917), AO3401A (C15127), CL31A476MPHNNNE (C96123), CL05B104KO5NNNC (C1525), SS34 (C8678), and B5819W from Jiangsu Changjing (C8598). PCBWay buys from major distributors, so Extended status matters only for JLCPCB.

**UNKNOWN or not verified in this pass:**
* Mouser/DigiKey part numbers, stock and prices for every part.
* DMN2002UFG availability.
* MLCC DC-bias derating.
* Schottky V_F at mA level and junction capacitance.
* SSM3K35AMFV/SSM3J35AMFV electrical values.
* MAX9938 specs (download failed) and the TSC213-specific offset.
* CH32V003 and PY32F003 supply ranges.
* XAL5030, IHLP-2525, Sunlord and TDK inductor specs.
* Inductor core loss at the chosen frequency.
* Linear-mode thermal stability of the MOSFETs on the real PCB.
* Battery springs, ESD/TVS parts, and PCBWay ring-finish options.
* The ATtiny10 5 V programming requirement, which is confirmed only by secondary sources (CMP-42); the Microchip PDF was not downloaded.
