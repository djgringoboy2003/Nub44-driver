# Converter IC research — NUBM44 single-cell laser driver (power stage)

- Prepared by: power-converter research specialist (agent), 2026-10-24
- Status: **evidence for lead-engineer review — not a final architecture decision**
- Source IDs `PWR-xx` refer to `research/sources/converter-sources.md`. Page numbers are PDF page numbers of the local copies in `research/datasheets/pwr_*`.
- Conventions: "min/typ/max" are datasheet values; **(inferred)** = engineering inference from topology/block diagram, not stated in the datasheet; **UNKNOWN** = not found in retrieved sources.

---

## 1. Executive summary

### 1.1 Findings that drive the architecture

1. **A boost-only stage cannot regulate laser current when the required output voltage is below the battery voltage.** The battery can be at up to 4.2 V. A hot diode, or a low-current mode, can need Vf < 4.2 V. In that case every boost IC loses control. There are three ways it happens:
   - **Standard boosts** (TPS61088, TPS61288, MP3431, TPS61089): the battery feeds the laser through the inductor and the high-side (HS) body diode, and nothing limits the current. In FPWM/FCCM the minimum on-time even pushes Vout above Vin. (inferred from topology)
   - **Boosts with a "pass-through" mode** turn the HS FET fully on, so there is not even a diode drop. TPS61022 (p.11 §7.3.5) and MP3432 (p.16–17) behave this way, and TPS61236P does so early, within 0.6 V of Vout (p.11 §8.3.4.1).
   - **Consequence:** a boost design needs a series pass/disconnect element plus an interlock (Vbat < Vf_min(I, T) − margin). The alternative is a 4-switch buck-boost.
2. **Current requirement at the worst case** (Vin = 3.0 V, Iout = 4 A, Vf = 5.0 V, η = 0.88): Iin(avg) = 7.58 A. With 40 % ripple the peak is 9.09 A and the valley 6.06 A (§5).
   - **Adequate minimum limits:** TPS552882/TPS55288 (14 A min average, +85 %), TPS61288 (12 A min peak, +32 %), MP3431 (19 A min peak, +109 %; guaranteed by correlation only, not production-tested), TPS61088 in PFM mode (10.0 A min for -Q1 at 49.9 kΩ, +10 %; 10.6 A min for the commercial Rev A at 100 kΩ, +17 %).
   - **Marginal or insufficient:** TPS61022/TPS61236P (6.5 A min valley, +7 %), TPS61089 (−1 %), TPS552892 (7.0 A min average, −8 %), TPS55289 (−12 %), TPS61178 (−30 %), TPS61378-Q1 (−56 %), XL6009 (4 A typ).
3. **Efficiency targets.**
   - **≥ 86 % at 3.0 V is realistic** for all shortlisted parts. My conduction-loss bound is ≥ 94 %, and the TPS61088-Q1 datasheet curve shows about 88–89 % at 3.0 V → 5 V/4 A.
   - **> 95 % at 4.0 V is only plausible with the lowest-Rds(on) parts** (TPS61288, MP3431, TPS552882 boost leg) and a low-DCR inductor. The TPS61288 Fig 7-5 curve (Vout 5.5 V) reads about 96 % at 4.2 V/4 A, but it uses a separate 3.3 V signal supply on an EVM.
   - Neither target is verified at our exact operating point.
   - The 4-switch buck-boost runs in its buck-boost transition region when Vin ≈ Vout (4.0 V → 4.6 V), where all four switches switch. **> 95 % is UNLIKELY/UNVERIFIED** there, because no curve at Vin 3–4 V is published (TPS55288 curves start at Vin = 5 V).

### 1.2 Shortlist (recommendation for review, ranked)

| Rank | Architecture | Leading IC | Why | Main risks |
|---|---|---|---|---|
| 1 | **4-switch synchronous buck-boost.** Boost leg integrated, 2 external buck-leg N-FETs. CC via built-in ISP/ISN loop and/or an external amplifier into FB. | **TPS552882** (standalone). Alt: **TPS55288** (I²C, current limit programmable 0–6.35 A in 50 mA steps with 10 mΩ). | Regulates Vout above **and below** Vin, so the hot-diode/low-current case is covered. Average inductor current limit 14 A min. Boost FETs 7.1/7.6 mΩ typ. 4.0 × 3.5 mm. Built-in output-current loop (50 mV ±2 mV). Hiccup short protection. Input is isolated when disabled because the buck HS FET is off (inferred). | 2 extra FETs on a 22 mm board. IQ 760 µA typ. Fixed 4 ms soft start. VIN UVLO rising up to 3.0 V. The datasheet calls the CC loop "slow", so overshoot into the diode is unverified. No SPICE model for TPS552882, and the TPS55288 model is encrypted. No efficiency data at Vin < 5 V. TPS55288 needs an I²C master to set OE before it switches. |
| 2 | **Integrated synchronous boost + external CC loop into FB + series disconnect/pass FET + Vbat-vs-Vf interlock.** | **TPS61288**. Alts: **MP3431**, TPS61088 (see note). | Best current margin per mm²: 12 A min, 6.5/8.5 mΩ typ, **2.5 × 3.0 mm**. Lowest conduction loss. VIN start ≤ 2.4 V. | No load disconnect. No short-circuit protection beyond cycle-by-cycle limit. Fixed 12–17.1 A limit forces a large-Isat inductor. Fixed 500 kHz, auto-PFM only. OVP fixed at 19 V, so an external open-load clamp is needed. Model encryption UNKNOWN. Sourcing UNKNOWN. |
| 3 | **Fully-integrated 4-switch buck-boost** (no external FETs). | **TPS552892** | All 4 FETs inside (11–22 mΩ). Standalone FB, CC (50 mV), PG and CC pins. Regulates below Vin. 3.0 × 5.0 mm. | **Average current limit 7 A min < 7.58 A needed** at 3.0 V/4 A/5.0 V. Only viable if the spec is relaxed (≤ ~3.5 A at 3.0 V, or a 3.3 V cut-off). VIN min 3.0 V. Encrypted model. |

**Rejected:**
- **XL6009** (§2).
- **LM5155x / LM5156x:** non-synchronous, so the Schottky loss alone is about 1.4–1.8 W at 4 A (≈ 7–9 % of 20 W) and > 95 % is impossible. Start-up needs ≥ 2.97 V with BIAS = VCC.
- **TPS61178:** ≤ 10 A programmable, 6.4 A min at 80.6 kΩ.
- **TPS61089:** 9.0 A min.
- **TPS61378-Q1:** 4.8 A max setting, 50/50/100 mΩ.
- **TPS61022 / TPS61236P:**
  - About +7 % valley margin.
  - Pass-through hazard.
  - TPS61236P: CC accuracy only ±10–15 %, CC "only recommended for pure resistive loads", and VIN ≤ VOUT − 0.6 V.
- **TPS55289:** 6.7 A min.

**Note on TPS61088:**
- On 2026-10-24, `ti.com/product/TPS61088` and the commercial datasheet URLs returned **HTTP 404**. The TPS61088-Q1 page is live (ACTIVE).
- TI's store inventory API reported **26,416 pcs of TPS61088RHLR** (PWR-19, PWR-20).
- Lifecycle is therefore **UNKNOWN**. Treat it as a fallback only.
- The -Q1 datasheet specifies much higher Rds(on) than the 2017 commercial datasheet: 18.0/19.5 mΩ typ vs 11/13 mΩ.

**Not evaluated** (datasheets not retrieved; automated access to analog.com and monolithicpower.com was blocked): MAX77831, MAX77857, LT3757/LT3757A, LT8330, LTC3786/LTC7804, and Silergy/Richtek/ETA/Injoinic/SGMicro alternatives. All **UNKNOWN**.

---

## 2. XL6009 audit (earlier concept: XL6009 asynchronous boost + LM358) — **REJECT**

Source PWR-17. This is a Kylinchip/XLSEMI XL6009 datasheet from a third-party mirror. It is an image/OCR PDF and no revision number appears on the pages reviewed.

| Parameter | Datasheet value | Page | Requirement | Verdict |
|---|---|---|---|---|
| Title | "400KHz 60V 4A Switching Current Boost / Buck-Boost / Inverting DC/DC Converter" | p.1 | — | — |
| Input operation voltage | **5 V min, 32 V max** (feature: "Wide 5V to 32V Input Voltage Range") | p.1, p.5 | 2.8/3.0–4.2 V | **FAIL**: not specified below 5 V at all. |
| Switch current limit | **4 A typ** (VFB = 0), no min given | p.5 | ≥ 9.1 A peak | **FAIL** |
| Switch Rds(on) | 110 mΩ typ / 120 mΩ max (Vin = 12 V, Isw = 4 A) | p.5 | — | About 3.3 W switch conduction loss at 3.0 V/4 A (7.58² A² × D 0.47 × 0.12 Ω). |
| Rectifier | Asynchronous; external Schottky (typ. app uses 1N5824) | p.3 | — | Adds about 1.6 W at 4 A (assuming 0.4 V). |
| Frequency | 320/400/480 kHz fixed | p.5 | — | — |
| Feedback reference | 1.213/1.25/1.287 V (±3 %) | p.5 | — | Poor accuracy for a CC reference. |
| Quiescent / shutdown current | 2.5/5 mA; shutdown 70/100 µA | p.5 | — | High standby drain. |
| Package | **TO263-5L** only | p.1 | IC ≤ 4 × 4 mm | **FAIL**. The TO-263 class is roughly 10 × 15 mm; exact dimensions are on the datasheet package page, not transcribed. |
| Disabled-state output | Boost path L + Schottky → output stays ≈ Vbat − Vd (inferred) | — | true disconnect | FAIL |

**Verdict:** XL6009 must be rejected. It is outside its specified input range at every Li-ion state of charge, has under half the needed switch current, and its estimated efficiency is about 75 % or worse at the 3.0 V/4 A point. It is also physically incompatible with the 22 mm board.

---

## 3. Comparison matrix

### 3a. Electrical limits

"pk" = peak, "val" = valley, "avg" = average inductor current. Rds(on) is typ (max) in mΩ. Page references are to the local PDF.

| Part (doc) | Topology / control | VIN start / operating | VOUT range | Switch/inductor current limit min/typ/max | Rds(on) LS / HS | fsw | VREF (accuracy) | Comp / SS / light-load mode |
|---|---|---|---|---|---|---|---|---|
| **TPS552882** (SLVSFC5) | 4-switch buck-boost, average-current mode. Boost FETs integrated, **buck FETs external** (DR1H/DR1L). | UVLO rising 2.8/2.9/3.0 V, falling 2.6/2.65/2.7 V; 2.7–36 V (p.6) | 0.8–22 V | avg **14/16.5/19 A** @RILIM 20 kΩ; pk 25 A typ (p.7) | boost leg 7.1 / 7.6 typ; buck leg = external FET | 200 k–2.2 MHz (RFSW), sync, ±7 % dither (p.7, 15–16) | 1.188/1.2/1.212 V (±1 %) (p.7) | ext COMP. SS 3/4/5 ms fixed (p.7). PFM/FPWM by MODE resistor (p.14). |
| **TPS55288** (SLVSF01B) | Same as TPS552882 + I²C | same; IQ 760 µA typ (p.6) | 0.8–22 V (DAC) | same (p.7) | 7.1 / 7.6 typ | same | DAC; ext-FB 1.117/1.129/1.141 V (p.7) | same; switching starts only after the OE bit is set over I²C (p.17). |
| **TPS552892** (SLVSH28A) | 4-switch buck-boost, fully integrated | UVLO 2.8/2.9/3.0 rising; VIN 3.0–36 V (p.6) | 0.8–22 V | avg **7/8/9 A**; pk HS 13 A, LS 12 A typ (p.7) | buck 22 / 14; boost 11 / 11 typ (p.7) | 200 k–2.2 MHz | ±1 % (p.1) | ext COMP. PFM/FPWM by MODE pin. |
| TPS55289 (SLVSGA9A) | as TPS552892 + I²C | 3.0–30 V | 0.8–22 V | avg **6.7/8 A** (p.7) | buck 22 / 14; boost 11 / 11 | 200 k–2.2 MHz | DAC | SS 2.5/3.6/5 ms |
| **TPS61288** (SLVSFP3C) | Sync boost, peak-current, adaptive off-time (SOO) | rising UVLO 2.3/2.4 V max; falling 1.8/1.9/2.0 V; 2.0–18 V (p.5–6) | 4.5–18 V | pk **12/15/17.1 A**, fixed (p.6) | 6.5 / 8.5 typ (no max) | 440/500/600 kHz fixed | 0.588/0.6/0.612 V (±2 %) | ext COMP. Internal SS 3 ms typ. Auto PFM only, no FPWM (p.11). |
| **MP3431** (Rev 1.0, 2017) | Sync boost, adaptive COT peak-current | start 2.7–13 V; operating 0.8–13 V; VDD UVLO 2.2/2.4/2.6 V rising (p.3–4) | VIN–16 V | pk **19/21.5/23.5 A** fixed (note 7: correlation, not production-tested) + programmable **average input current limit** (p.5, 19, 21) | 6.5 / 10 typ (p.5) | 500/600/700 kHz | 0.985/1/1.015 V (±1.5 %) (p.4) | ext COMP, ext SS (7.5 µA). PSM/USM/FCCM by MODE (p.15–17). |
| MP3432 (Rev 1.0, 2019) | as MP3431, + **auto pass-through in PSM** | same | VIN–16 V | pk programmable: 9.3/10/10.7 A @36 kΩ; RILIM(kΩ) = 320/I + 4 (p.5, 18, 20) | 6.5 / 10 typ | 500/600/700 kHz | ±1.5 % | as MP3431 |
| TPS61088-Q1 (SLVSE52A) | Sync boost, adaptive constant off-time peak-current | UVLO rising 2.7 V max; falling 2.4/2.5 V (p.6) | 4.5–12.6 V | pk **PFM 10.0/11.4/13.0 A**, FPWM 7.2/8.7/10.5 A @49.9 kΩ; ILIM = 550000/RILIM (PFM) (p.6, 12–13) | 18.0 (27.5) / 19.5 (29.7) (p.6) | 200 k–2.2 MHz (R FSW–SW) | 1.186/1.204/1.222 V (±1.5 %) | ext COMP. Ext SS (5 µA). PFM/FPWM by MODE. |
| TPS61088 commercial (ZHCSDP8A Rev A, Chinese) | same | 2.7–12 V | 4.5–12.6 V | pk PFM **10.6/11.9/13 A**, FPWM 9.0/10.3/11.4 A @RILIM 100 kΩ (p.5) | 11 (16.5) / 13 (18) (p.5) | 200 k–2.2 MHz | 1.186/1.204/1.222 V | as -Q1 |
| TPS61089 (SLVSD38C) | as TPS61088 | UVLO 2.7 V max rising; 2.7–12 V | 4.5–12.6 V | pk 9.0/10/11 A @100 kΩ; 7.3/8.1/8.9 A @127 kΩ (p.6) | 19 (31) / 27 (44) | 200 k–2.2 MHz | — | ext COMP. 4 ms built-in SS. |
| TPS61178 (SLVSDA7E) | Sync boost, fixed-freq peak-current | UVLO 2.6/2.7 rising, 2.2/2.3 falling; 2.7–20 V (p.5) | 4.5–20 V | pk 6.4/8/9.4 A @80.6 kΩ; ILIM = 745/RLIMIT(kΩ) ("up to 10 A") (p.5, 12) | 16 (25) / 16 (25) | ≤ 2.2 MHz + sync | 1.180/1.198/1.210 V | ext COMP. Precharge 2.6 ms + SS 3.2 ms. PFM (61178) / FPWM (611781). |
| TPS61022 (SLVSDX7D) | Sync boost, adaptive on-time, valley current | start 1.8 V; 0.5–5.5 V (p.5) | 2.2–**5.5** V | **val** 6.5/8/10 A (p.5) | 12 / 18 typ | 1 MHz | 585/600/615 mV (±2.5 %) | internal comp. SS ~700 µs. MODE PFM/FPWM. |
| TPS61236P (SLVSCK4A) | Sync boost, quasi-const on-time valley + **CC pin** | UVLO 2.2/2.3 V; VIN 2.3 V to VOUT − 0.6 V (p.4–5) | 2.9–5.5 V | **val** 6.5/8/9.5 A (−20…100 °C) (p.5) | 14 (30) / 14 (30) | 0.75/1/1.25 MHz | 1.219/1.244/1.269 V | internal comp + internal SS. PFM. |
| TPS61378-Q1 (Rev E) | Sync boost + integrated isolation FET | UVLO 2.2/2.3 V; 2.3–14 V | 4–18.5 V | pk **4.0/4.8/5.55 A** max setting (p.6) | 50 / 50; ISO 100 | 0.2–2.2 MHz | 0.788/0.8/0.812 V | ext COMP |
| LM5155x (SNVSB75E) | Non-sync boost controller (ext FET + diode) | 2.97 V (BIAS = VCC; VCC UVLO 2.75/2.85/2.95 V); 1.5 V supply if BIAS ≥ 3.5 V (p.1, 6) | set by FET/diode | CS threshold 100 mV ±7 % (ext Rsense) | external | 100 k–2.2 MHz | 0.99/1/1.01 V | ext COMP, ext SS |
| LM5156x (SNVSBI6) | as LM5155x (65 V) + dual random spread spectrum | same | — | 100 mV ±7 % | external | 100 k–2.2 MHz | ±1 % | same |
| XL6009 (§2) | Async boost, current mode | **5–32 V** | 1.25 V–(Vout max not transcribed) | 4 A typ | 110 (120) switch | 400 kHz | ±3 % | internal |

### 3b. Protection, disabled/short behaviour, thermal, package, model, sourcing

Sourcing: only values actually retrieved on 2026-10-24 are shown; everything else is UNKNOWN.

| Part | OVP | Disabled-state output | Output short / overload | TSD | RθJA std / EVM (°C/W) | Package, body | Recommended L | Regulates VOUT < VIN? | SPICE model | Sourcing |
|---|---|---|---|---|---|---|---|---|---|---|
| **TPS552882** | 22.5/23.5/24.5 V, fixed. Use the FB divider as the open-load clamp. | EN < 0.4 V: "all functions are disabled" (p.15). **Input isolated** because the external buck HS FET is off and its body diode is reverse-biased for Vin → out (inferred). | Avg-current limit + cycle peak limit. **Hiccup**: Vout < 0.8 V and avg current at limit → 76 ms off, then soft start (p.19). | 175 °C / 20 °C (p.8) | 47.5 / 25.8 (simulated EVM) (p.6) | VQFN-HR 26-pin RPM, **4.0 × 3.5 mm** | 4.7 µH nominal (TI table: XAL1010-472ME, IHLP5050EZER4R7, 125CDMCCDS-4R7MC — all ≥ 11 × 10 mm) (Table 8-2) | **Yes** (buck mode) | None listed on product page (EVMs only). UNKNOWN. | TI store inventory TPS552882RPMR **2,950** (PWR-20). Price UNKNOWN. |
| TPS55288 | same | same; plus optional output discharge 40/100/170 mA when OE = 0 and DISCHG = 1 (p.6, 17) | Hiccup only if the HICCUP bit is set (p.21) | 175 °C | 47.5 / 25.8 | same | 0.7–13 µH effective, 4.7 nom (p.5) | Yes | **Encrypted** PSpice (SLVMDD9) | UNKNOWN |
| TPS552892 | UNKNOWN (not transcribed) | Fully integrated buck HS FET off → input isolated (inferred) | UNKNOWN (not transcribed; family parts use hiccup) | UNKNOWN | 43.4 / 27.5 (p.5) | VQFN-HR 21-pin RYQ, **3.0 × 5.0 mm** | — | Yes | **Encrypted** PSpice (SLVME05) | UNKNOWN |
| TPS55289 | 22.5/23.5/24.5 V | as TPS552892 | Hiccup | 175 °C | 43.4 / 27.5 | RYQ 3.0 × 5.0 mm | 4.7 µH (typ app) | Yes | **Encrypted** (SLVMDY0) | UNKNOWN |
| **TPS61288** | 18.3/19/19.5 V, fixed | No disconnect. Output = Vbat through L + HS body diode (inferred). SW reverse leakage ≤ 1 µA with EN low (p.6). | Cycle-by-cycle 15 A typ only. No hiccup. A hard output short is not limited by the IC (inferred). | 160 °C / 20 °C | **71.4 / 33.6** (p.5) | VQFN-HR 11-pin RQQ, **2.5 × 3.0 mm**; TPS61288L "HotRod Lite" option (p.1) | 1.0–4.7 µH (design text); 0.8–5.6 µH effective (ROC). TI examples ≥ 10 × 11 mm (p.15). | **No** | "TPS61288 PSPICE Model" (SLVMDH8): encryption not stated, **UNKNOWN** | UNKNOWN |
| **MP3431** | 16.5 V typ | No disconnect (inferred). "If EN is low, VDD is disconnected from VIN and VOUT" refers to bias only (p.18). | Cycle peak 21.5 A + programmable average input-current clamp (COMP clamped, Vout droops) (p.19). No hiccup described. | 150 °C / 25 °C | 48 (JESD51-7) / 31 (EV board) (p.3) | QFN-13, **3 × 4 mm** | 1.5 µH typical (p.21) | **No** ("Boost output voltage: VIN to 16V", p.3) | **UNKNOWN** (MPS site blocked) | UNKNOWN. DigiKey listings MP3431GL-P / -Z seen in search results only. |
| MP3432 | 16.5 V | **Auto pass-through** in PSM when VIN > VOUT-SET: HS FET always on (p.16–17). Shutdown: no disconnect (inferred). | Programmable cycle peak limit. No hiccup. | 150 °C | 48 / 31 | QFN-13 3 × 4 mm | 1.5 µH | No (pass-through) | UNKNOWN | UNKNOWN |
| TPS61088(-Q1) | 12.7/13.2/13.6 V | No disconnect (inferred) | Cycle-by-cycle only | 150 °C / 20 °C | -Q1: 36.4 / 25.8 (p.5) | VQFN-20 RHL, **4.5 × 3.5 mm** | 0.47–10 µH, 2.2 nominal (p.5). TI table 1.2–2.2 µH, ≥ 7.3 × 7.2 mm (p.18). | No | **Unencrypted** PSpice transient (SLVMAU6 Rev A) | LCSC **C87357** TPS61088RHLR: stock 6,342; US$1.30 @1, 1.1552 @10, 1.0202 @30, 0.9182 @100, 0.8754 @500, 0.8557 @1000 (PWR-21). TI inventory: RHLR 26,416, QRHLRQ1 0 (PWR-20). TI product page **404**. |
| TPS61089 | 12.7/13.2/13.6 V | No disconnect (inferred) | Cycle-by-cycle | — | 53.4 | VQFN-HR 11 RNR 2.0 × 2.5 mm | — | No | **Unencrypted** (SLVMBK5 Rev C) | UNKNOWN |
| TPS61178 | 20.5/21/21.5 V | **DISDRV drives an external P-FET** that isolates the output in shutdown/short (p.11) | **Hiccup** at 20 A short limit or Vout < 30 %, 90 ms off (p.13) | 150 / 130 °C | 60.2 | VQFN-HR 13 RNW 3.0 × 3.5 mm | 0.47–3.3 µH | No | **Unencrypted** (SLVMC02, SLVMC10) | UNKNOWN |
| TPS61022 | 5.5/5.7/6.0 V | **True disconnect** in shutdown (p.10). **Pass-through** (HS fully on) when Vout > 101 % of target (p.11). | Current folds back below 1.8 V; ~0.7 A at Vout < 0.4 V (p.11) | 150 °C | 108.2 / 50.9 | VQFN 7-pin RWU 2.0 × 2.0 mm | 0.33–2.9 µH, 1.0 nominal | No (pass-through) | **Unencrypted** (SLVMCZ3 Rev A) | TI inventory TPS61022RWUR **0** (PWR-20) |
| TPS61236P | 5.60/5.80/5.93 V | **True disconnect** (p.11). Premature pass-through near VIN, current limited to ILIM_pre (p.11). | Precharge limit 0.25 A typ at a short; "only valid when VIN < 4.5 V" (p.14) | 140 °C | 28.7 | VQFN-9 RWL 2.5 × 2.5 mm | 0.7–1.3 µH | No | **Unencrypted** (SLVMAU0 Rev B) | UNKNOWN |
| TPS61378-Q1 | 19.3/20/20.5 V | True disconnect (integrated ISO FET) (p.1) | Hiccup (p.1) | 165 °C | 46.2 | QFN 3 × 3 mm, 16-pin | — | No (supports VIN close to VOUT, p.1) | "FPWM Version PSpice model" (SLVMDF2), UNKNOWN | UNKNOWN |
| LM5155x | FB-based 107/110/113 % VREF (p.7). Useless for open-load if FB is used for CC. | Boost diode path: Vout ≈ Vbat − Vd (inferred) | Peak limit; optional hiccup (LM51551) | — | 63.7 / 40.8 | WSON-12 3 × 2 mm | — | No | **Unencrypted** transient (SNVMBL2 Rev H) and average (SNVMBY3); TINA (SNVMBV7) | UNKNOWN |
| LM5156x | same | same | same (LM51561 variant) | — | 63.1 / 41.5 | WSON-12 3 × 2 mm | — | No | **Unencrypted** (SNVMBV9 Rev H, SNVMC69) | UNKNOWN |
| XL6009 | "SW PIN Built in Over Voltage Protection" (value not transcribed) | Schottky path (inferred) | "Built in current limit" | yes | — | TO263-5L | 33 µH (typ app) | No | none known | LCSC code not found; C73332 is XL4005E1 (PWR-22) |

---

## 4. Shortlisted parts — detailed notes, verbatim pin tables, land-pattern references

### 4.1 TPS552882 (rank 1). TPS55288 is the I²C sibling. Source PWR-10 (SLVSFC5, Nov 2020), PWR-09.

**Constant-current implementation**
- *Option A (built-in loop):* put Rsense between ISP and ISN in the output path. The loop regulates V(ISP−ISN) to **48/50/52 mV** (p.7), which is 12.5 mΩ for 4 A (≈ 0.2 W loss).
  - The FB divider sets the open-load voltage clamp, e.g. 5.5–6 V, with VREF 1.2 V ±1 %. This removes the need for a separate OVP divider.
  - The datasheet calls it "a slow constant current control loop" (p.4). Startup overshoot into a diode load is **UNKNOWN** and must be simulated or bench-tested.
  - The current setpoint is fixed by Rsense. Other levels need an injected offset at ISN/ISP (not covered by the datasheet) or option B.
  - The CC pin flags CC operation (open-drain) and PG flags 90/95 % (p.3).
- *Option B (fast loop):* a current-sense amplifier output is summed into FB. The ISP/ISN loop then stays as an independent backup current limit, for example set about 10 % above the maximum setpoint.
- *TPS55288:* the current limit is programmable 0–6.35 A in 50 mA steps (10 mΩ, 0.5 mV steps) and the Vout reference is a 10-bit DAC (p.19–21). This gives firmware set-points, but needs an I²C master. Switching starts only after OE = 1 (p.17).

**Other notes**
- **Gate drive at low Vin:** VCC is 5.2 V from VOUT when VIN < 5.9 V and VOUT > VIN, otherwise from VIN (Table 7-1, p.13). At start-up from 3.0 V, VCC comes from VIN, so the external buck FETs need a low-Vgs rating (inferred).
- **External buck-leg FETs:** in boost mode the buck HS FET is continuously on and carries the full input current (about 7.6 A at 3.0 V; p.18 §7.3.13). Its Rds(on) directly adds conduction loss.
- **Average inductor current limit:** programmable through RILIM, Eq. 5 (p.17), 16.5 A typ at 20 kΩ. Setting about 9–10 A lets the inductor be sized smaller than TI's 4.7 µH/11 mm examples.
- **VIN UVLO:** rising 2.8/2.9/3.0 V, falling 2.6/2.65/2.7 V. A start attempt at a sagging 2.8–3.0 V battery may not start.

**Pin table — verbatim, TPS552882 Table 5-1 (SLVSFC5 p.3–4)**

| PIN NO. | NAME | I/O | DESCRIPTION |
|---|---|---|---|
| 1 | DR1L | O | Gate driver output for low-side MOSFET in buck side |
| 2 | DR1H | O | Gate driver output for high-side MOSFET in buck side |
| 3 | VIN | PWR | Input power supply for the IC |
| 4 | EN/UVLO | I | Enable logic input and programmable input voltage undervoltage lockout (UVLO) input. Logic high level enables the device. Logic low level disables the device and turns it into shutdown mode. After the voltage at the EN/UVLO pin is above the logic high voltage of 1.15 V, this pin acts as programmable UVLO input with 1.23-V internal reference. |
| 5 | PG | O | Power good indication. When the output voltage is above 95% of the setting output voltage, this pin outputs high impedance. When the output voltage is below 90% of the setting output voltage, this pin outputs low level. |
| 6 | CC | O | Constant current output indication |
| 7 | DITH/SYNC | I | Dithering frequency setting and synchronous clock input. Use a capacitor between this pin and ground to set the dithering frequency. When this pin is short to ground or pulled above 1.2 V, there is no dithering function. An external clock can be applied at this pin to synchronize the switching frequency. |
| 8 | FSW | I | The switching frequency is programmed by a resistor between this pin and the AGND pin. |
| 9, 24 | PGND | PWR | Power ground of the IC. It is connected to the source of the low-side MOSFET. |
| 10 | AGND | PWR | Signal ground of the IC |
| 11, 26 | VOUT | PWR | Output of the buck-boost converter |
| 12 | ISP | I | Positive input of the current sense amplifier. An optional current sense resistor connected between the ISP pin and the ISN pin can limit the output current. If the sensed voltage reaches the current limit setting value in the register, a slow constant current control loop becomes active and starts to regulate the voltage between the ISP pin and the ISN pin. Connecting the ISP pin and the ISN pin together with the VOUT pin can disable the output current limit function. |
| 13 | ISN | I | Negative input of the current sense amplifier. An optional current sense resistor connected between the ISP pin and the ISN pin can limit the output current. If the sensed voltage reaches the current limit setting value in the register, a slow constant current control loop becomes active and starts to regulate the voltage between the ISP pin and the ISN pin. Connecting the ISP pin and the ISN pin together with the VOUT pin can disable the output current limit function. |
| 14 | FB | I | Connect to the center of a resistor divider to program the output voltage. |
| 15 | MODE | I | Setting the operation modes of the TPS55288x to select PFM mode or forced PWM mode in light load condition and to select the internal LDO or external 5 V for VCC by a resistor between this pin and AGND. |
| 16 | CDC | O | Voltage output proportional to the sensed voltage between the ISP pin and the ISN pin. Use a resistor between this pin and AGND to increase the output voltage to compensate voltage droop across the cable caused by the cable resistance. |
| 17 | ILIM | O | Average inductor current limit setting pin. Connect an external resistor between this pin and the AGND pin. |
| 18 | COMP | I | Output of the internal error amplifier. Connect the loop compensation network between this pin and the AGND pin. |
| 19 | VCC | O | Output of the internal regulator. A ceramic capacitor of more than 4.7 μF is required between this pin and the AGND pin. |
| 20 | BOOT2 | O | Power supply for high-side MOSFET gate driver in boost side. A ceramic capacitor of 0.1 µF must be connected between this pin and the SW2 pin. |
| 21, 25 | SW2 | I | The switching node pin of the boost side. It is connected to the drain of the internal low-side power MOSFET and the source of internal high-side power MOSFET. |
| 22 | BOOT1 | I | Power supply for high-side MOSFET gate driver in buck side. A ceramic capacitor of 0.1 µF must be connected between this pin and the SW1 pin. |
| 23 | SW1 | I | The switching node pin of the buck side. It is connected to the drain of the external low-side power MOSFET and the source of external high-side power MOSFET. |

TPS55288 (SLVSF01B p.3–4) uses the same pinout except for three pins:
- pin 5 = **SCL** "Clock of I2C interface"
- pin 6 = **SDA** "Data of I2C interface"
- pin 14 = **FB/INT** "When the device is set to use external output voltage feedback, connect to the center tap of a resistor divider to program the output voltage. When the device is set to use internal feedback, this pin is a fault indicator output. When there is an internal fault happening, this pin outputs logic low level."

**Land pattern:** RPM0026A (VQFN-HR, 1 mm max), drawing **4224618/A 10/2018**.
- Package outline: SLVSFC5 **p.38**
- Example board layout / land pattern: **p.39**
- Stencil: **p.40**
- The same drawing appears in SLVSF01B on p.52–54.

### 4.2 TPS61288 (rank 2 lead). Source PWR-03 (SLVSFP3C, Rev C).

**CC through FB:**
- Signal chain: low-side shunt (laser cathode → Rs → GND) → non-inverting amplifier (gain G) → FB, with VFB = 0.6 V at Iset. Example: Rs = 10 mΩ and 4 A gives 40 mV, so G = 15.
- Constraints:
  - VOUT must stay ≥ 4.5 V (ROC p.5); below that, regulation is not specified.
  - The 19 V OVP is far above a safe open-load voltage, so the FB network needs a second, diode-OR'd or summed divider from VOUT that clamps Vout at about 5.5–6 V.
  - FB bias current is ≤ 20 nA (p.6), which sets the maximum summing impedance.
  - Soft start is internal and fixed at about 3 ms (p.6, 11).
  - No FPWM, so at light load or low current setpoints it pulse-skips.
- **Flash/enable:**
  - EN toggling re-runs soft start.
  - In shutdown the battery still reaches the laser anode through L and the HS body diode, so a **series disconnect FET is mandatory** for hardware shutdown, open/short handling and the Vf < Vbat case.

**Inductor sizing conflict:** TI says "select the inductor with saturation current higher than the setting current limit" (p.15). The limit is fixed at 12/15/17.1 A, which implies a large inductor; TI's examples are all ≥ 10 × 11 mm (Table 9-2). This conflicts with the ≤ 7 × 7 mm goal unless saturation during fault events is accepted (to be decided with the passives agent).

**Thermal:** RθJA is 71.4 °C/W on the standard board. Assuming ≈ 0.4–0.6 W dissipated in the IC (assumption), the junction runs about 30–45 °C above ambient (Eq. 15, p.22).

**Pin table — verbatim, TPS61288 Table 6-1 (SLVSFP3C p.4)**

| NAME | NUMBER | I/O | DESCRIPTION |
|---|---|---|---|
| FB | 1 | I | Voltage feedback. Connect to the center tape of a resistor divider to program the output voltage. |
| COMP | 2 | O | Output of the internal error amplifier, the loop compensation network should be connected between this pin and the AGND pin. |
| PGND | 3 | PWR | Power ground of the IC. It is connected to the source of the low-side MOSFET. |
| SW | 4,9 | PWR | The switching node pin of the converter. It is connected to the drain of the internal low-side power MOSFET and the source of the internal high-side power MOSFET. |
| VOUT | 5 | PWR | Boost converter output |
| EN | 6 | I | Enable logic input. Logic high level enables the device. Logic low level disables the device and turns it into shutdown mode. |
| VIN | 7 | I | IC power supply input |
| BST | 8 | O | Power supply for high-side MOSFET gate driver. A ceramic capacitor of 0.1 µF must be connected between this pin and the SW pin. |
| AGND | 10 | - | Signal ground of the IC |
| VCC | 11 | O | Output of the internal regulator. A ceramic capacitor of more than 1.0 µF is required between this pin and ground. |

**Land pattern:** RQQ0011A (VQFN-HR, 1 mm max), drawing **4225610/A 12/2019**.
- Outline: **p.27** (body 2.4–2.6 × 2.9–3.1 mm)
- Land pattern example: **p.28**
- Stencil: **p.29** ("PIN 3 & 5: 89 %" paste coverage)
- Layout example: Fig 11-1, p.21. The SW, VOUT and PGND pads are the thermal path; there is no exposed centre pad.

### 4.3 MP3431 (rank 2 alternative). Source PWR-15 (Rev 1.0, 6/8/2017; distributor mirror — confirm the latest revision with MPS).

**CC through FB:** VREF is 1.0 V (±1.5 %), so G = 25 with a 10 mΩ shunt at 4 A.

**Built-in input-current clamp:**
- It acts on COMP and clamps the average input current. Datasheet example: R5 = 22 kΩ gives 13 A at VIN = 3.3 V (Eq. 9, p.21; RILIM is in kΩ and the limit depends on VIN).
- Equation as I reconstructed it, verified against that example: R = 980 / (3.45 × (I − (1.2 − 0.12·VIN))) − 1.
- This makes a useful second, independent current clamp, but it acts on input current, not laser current.

**Limitations:**
- The peak limit of 19–23.5 A is fixed, so the same inductor-Isat conflict as TPS61288 applies, only stronger.
- OVP is 16.5 V only, so an external open-load clamp is needed.
- MP3432 makes the peak limit programmable (9.3–10.7 A at 36 kΩ), but adds auto pass-through in PSM. Use FCCM or USM with MP3432 to avoid it.

**Pin table — verbatim, MP3431 "PIN FUNCTIONS" (p.15)**

| Pin # | Name | Description |
|---|---|---|
| 1 | SW | Converter switch. SW is connected to the drain of the internal low-side power MOSFET and the source of the internal high-side synchronous power MOSFET. Connect the power inductor to SW. |
| 2 | VDD | Internal bias supply. Decouple VDD with a 4.7μF ceramic capacitor placed as close to VDD as possible. When VIN is higher than 3.4V, VDD is powered by VIN. Otherwise, VDD is powered by the higher voltage of either VIN or VOUT. If the bias voltage connected to VDD is higher 3.4V, the regulator from VIN and VOUT is disabled. The VDD regulator starts working when VIN is higher than about 0.9V if EN is high. Supply VIN with a power source higher than 2.7V during VIN start-up to provide enough VDD power voltage. |
| 3 | SS | Soft-start programming. Place a capacitor from SS to AGND to set the VOUT rising slew rate. |
| 4 | COMP | Internal error amplifier output. Connect a capacitor and resistor in series from COMP to AGND for loop compensation. |
| 5 | FB | Feedback input. Connect a resistor divider from VOUT to FB. |
| 6 | AGND | Analog ground. |
| 7 | PGND | Power ground. |
| 8 | VOUT | Output. VOUT is connected to the drain of the high-side MOSFET. VOUT powers VDD when VOUT is higher than VIN and VIN is lower than 3.4V. |
| 9 | ILIM | Input current limit setting. A resistor in parallel with a capacitor is used to set the input current limit. Place a 1kΩ resistor in series with ILIM to avoid noise injection. If the input current limit function is not used, connect ILIM to AGND. |
| 10 | MODE | MODE selection. If MODE is floating, the MP3431 works in ultrasonic mode (USM). If MODE is high, the MP3431 works in forced continuous conduction mode (FCCM). If MODE is low, the MP3431 works in pulse-skip mode (PSM). MODE must always be higher than 0.2V in the application, even if in PSM. Place a 130kΩ + 20kΩ resistor divider from VDD to MODE to set the MP3431 in PSM. |
| 11 | EN | Chip enable control. When not in use, connect EN to VIN for automatic start-up. EN can program the VIN UVLO. Do not leave EN floating. |
| 12 | VIN | Input supply. VIN must be bypassed locally. Supply VIN with power source higher than 2.7V during VIN start-up to provide enough VDD power voltage. |
| 13 | BST | Bootstrap. A capacitor between BST and SW powers the synchronous HS-FET. |

**Land pattern:** "PACKAGE INFORMATION — QFN-13 (3mmx4mm)" with **RECOMMENDED LAND PATTERN** on **p.25**.
- Notes on that page: "land patterns of pin 1, 7 and 8 have the same length and width"; JEDEC reference MO-220.
- The dimensions are drawn graphically and cannot be extracted as text. Measure them from the PDF.
- The pin-out drawing is on p.2.

### 4.4 TPS61088 / TPS61088-Q1 (fallback). Source PWR-01 (SLVSE52A Rev A), PWR-02 (ZHCSDP8A Rev A).

**Strengths and features**
- Programmable ILIM (PFM: ILIM = 550000/RILIM for -Q1; the minimum can be 1.3–1.5 A below the formula, p.13 and p.16).
- Adjustable fsw 200 k–2.2 MHz.
- External SS and compensation.
- PFM/FPWM selectable. In FPWM the limit is lower: 7.2 A min.
- Unencrypted PSpice model (SLVMAU6).

**Weaknesses**
- 4.5 × 3.5 mm package.
- The -Q1 Rds(on) is 18–19.5 mΩ typ, which costs about 1–2 % efficiency at 3.0 V (§5).
- The commercial part's lifecycle is UNKNOWN (TI page 404).

**Pin table — verbatim, TPS61088-Q1 "Pin Functions" (SLVSE52A p.4)**

| NAME | NUMBER | I/O | DESCRIPTION |
|---|---|---|---|
| VCC | 1 | O | Output of the internal regulator. A ceramic capacitor of more than 1 µF is required between this pin and ground. |
| EN | 2 | I | Enable logic input. Logic high level enables the device. Logic low level disables the device and turns it into shutdown mode. |
| FSW | 3 | I | The switching frequency is programmed by a resister between this pin and the SW pin. |
| SW | 4, 5, 6, 7 | I | The switching node pin of the converter. It is connected to the drain of the internal low-side power MOSFET and the source of the internal high-side power MOSFET. |
| BOOT | 8 | O | Power supply for high-side MOSFET gate driver. A ceramic capacitor of 0.1 µF must be connected between this pin and the SW pin |
| VIN | 9 | I | IC power supply input |
| SS | 10 | O | Soft-start programming pin. An external capacitor sets the ramp rate of the internal error amplifier's reference voltage during soft-start |
| NC | 11, 12 | — | No connection inside the device. Connect these two pins to ground plane on the PCB for good thermal dissipation |
| MODE | 13 | I | Operation mode selection pin for the device in light load condition. When this pin is connected to ground, the device works in PWM mode. When this pin is left floating, the device works in PFM mode. |
| VOUT | 14, 15, 16 | O | Boost converter output |
| FB | 17 | I | Voltage feedback. Connect to the center tape of a resistor divider to program the output voltage. |
| COMP | 18 | O | Output of the internal error amplifier, the loop compensation network should be connected between this pin and the AGND pin. |
| ILIM | 19 | O | Adjustable switch peak current limit. An external resister should be connected between this pin and the AGND pin. |
| AGND | 20 | — | Signal ground of the IC |
| PGND | 21 | — | Power ground of the IC. It is connected to the source of the low-side MOSFET. |

**Land pattern:** RHL0020A, drawing **4219071/A 05/2017**.
- Outline: **p.32** (body 3.4–3.6 × 4.4–4.6 mm; exposed pad 2.05 ± 0.1 × 3.05 ± 0.1 mm)
- Land pattern example: **p.33**
- Stencil: **p.34**

### 4.5 TPS552892 (rank 3). Source PWR-12 (SLVSH28A).

- Standalone, fully integrated.
- Pin order 1–21: EN/UVLO, MODE, PG, CC, DITH/SYNC, FSW, VIN, SW1, PGND, SW2, VOUT, ISP, ISN, FB, COMP, CDC, AGND, VCC, BOOT2, BOOT1, EXTVCC (Table 5-1, p.3–4). The full descriptions are not transcribed verbatim here; transcribe them from p.3–4 if this option is chosen.
- Pin 2 MODE "can not be float in application".
- Pin 21 EXTVCC: high or floating selects the internal LDO.
- Land pattern: RYQ0021A, outline **p.32**, board layout **p.33**, stencil **p.34**.

---

## 5. Current and efficiency feasibility

**Formulas.** These match TI's Eq. 8–10 (TPS61088-Q1 p.17) and Eq. 2–4 (TPS61288 p.14–15).

- Iin(avg) = Vout·Iout / (η·Vin)
- D = 1 − η·Vin/Vout
- ΔIL = r·Iin(avg)
- Ipk = Iin(avg)·(1 + r/2)
- Ivalley = Iin(avg)·(1 − r/2)
- L = Vin·D / (fsw·ΔIL)

**Case Vin = 3.0 V, Iout = 4 A, η = 0.88** (computed with the formulas above):

| Vout (= Vf) | Iin avg (A) | D | r | ΔIL (A) | Ipk (A) | Ivalley (A) | L @500 kHz | L @600 kHz | L @1 MHz |
|---|---|---|---|---|---|---|---|---|---|
| 4.6 V | 6.97 | 0.426 | 30 % | 2.09 | 8.02 | 5.92 | 1.22 µH | 1.02 µH | 0.61 µH |
| 4.6 V | 6.97 | 0.426 | 40 % | 2.79 | 8.36 | 5.58 | 0.92 µH | 0.76 µH | 0.46 µH |
| 5.0 V | 7.58 | 0.472 | 30 % | 2.27 | 8.71 | 6.44 | 1.25 µH | 1.04 µH | 0.62 µH |
| 5.0 V | 7.58 | 0.472 | 40 % | 3.03 | 9.09 | 6.06 | 0.93 µH | 0.78 µH | 0.47 µH |
| 5.1 V (5.0 V + 0.1 V sense/disconnect drop) | 7.73 | 0.482 | 40 % | 3.09 | 9.27 | 6.18 | 0.94 µH | 0.78 µH | 0.47 µH |

**Minimum-limit margin** = (datasheet minimum ÷ requirement) − 1, at r = 40 %:

| Part (limit type) | Datasheet minimum | Vf 4.6 V | Vf 5.0 V |
|---|---|---|---|
| TPS552882 / TPS55288, avg @20 kΩ | 14.0 A | +101 % | **+85 %** |
| MP3431, peak (correlation-guaranteed) | 19.0 A | +127 % | **+109 %** |
| TPS61288, peak | 12.0 A | +43 % | **+32 %** |
| TPS61088 commercial Rev A, PFM @100 kΩ | 10.6 A | +27 % | +17 % |
| TPS61088-Q1, PFM @49.9 kΩ | 10.0 A | +20 % | +10 % |
| TPS61088-Q1, FPWM | 7.2 A | −14 % | −21 % |
| MP3432 @36 kΩ (programmable higher) | 9.3 A | +11 % | +2 % |
| TPS61022 / TPS61236P, valley | 6.5 A | +17 % | +7 % |
| TPS61089 @100 kΩ | 9.0 A | +8 % | −1 % |
| TPS552892, avg | 7.0 A | 0 % | −8 % |
| TPS55289, avg | 6.7 A | −4 % | −12 % |
| TPS61178 @80.6 kΩ | 6.4 A | −23 % | −30 % |
| TPS61378-Q1 @20 kΩ | 4.0 A | −52 % | −56 % |

Note the minimum-limit test conditions differ: TPS61288 is specified at 7.2 V → 16 V, the TPS6108x at the stated RILIM. Treat margins < 15 % as failing.

**Conduction-loss-only efficiency bound.**
- Assumptions: typical Rds(on); Irms² = Iavg²(1 + r²/12) with r = 35 %; 10 mΩ current shunt in the laser path; inductor DCR 5 or 10 mΩ; for TPS552882, an assumed 5 mΩ external buck HS FET.
- Switching, core, gate-drive and IQ losses are excluded and typically cost another 1–3 % (assumption).

| Part | Vin 4.0 V → 4.6 V | Vin 4.0 V → 5.0 V | Vin 3.0 V → 4.6 V | Vin 3.0 V → 5.0 V |
|---|---|---|---|---|
| TPS61288 (6.5/8.5 mΩ) | 97.5 % / 96.9 % | 97.4 % / 96.8 % | 96.4 % / 95.3 % | 96.2 % / 95.1 % |
| MP3431 (6.5/10 mΩ) | 97.4 % / 96.7 % | 97.3 % / 96.6 % | 96.2 % / 95.1 % | 96.0 % / 94.9 % |
| TPS61088 commercial (11/13 mΩ) | 97.0 % / 96.4 % | 96.9 % / 96.2 % | 95.4 % / 94.4 % | 95.2 % / 94.1 % |
| TPS61088-Q1 (18/19.5 mΩ) | 96.2 % / 95.6 % | 96.0 % / 95.3 % | 94.0 % / 93.0 % | 93.7 % / 92.6 % |
| TPS552882 (7.1/7.6 + 5 mΩ ext) | 97.0 % / 96.4 % | 96.9 % / 96.2 % | 95.4 % / 94.3 % | 95.1 % / 94.0 % |

Each cell shows DCR 5 mΩ / DCR 10 mΩ.

**Published curves near our operating point.** These are read by eye from the graphs (±2 %) and none are measured at our exact point.
- **TPS61088-Q1, Fig 1 (p.7), Vout 5 V, PFM:** at 4 A about 94–95 % (Vin 4.2 V), about 92–93 % (3.6 V), about 88–89 % (3.0 V). The curves fall off steeply toward 4–5 A.
- **TPS61288, Fig 7-5 (p.8), Vout 5.5 V, with a separate 3.3 V signal VIN:** at 4 A about 96–97 % (Vin 4.2 V), about 96 % (3.6 V), about 91–92 % (2.3 V).
- **TPS61022, Fig 6-1 (p.6), Vout 5 V:** feature claim 94.7 % at 3.6 V/3 A.
- **TPS61236P, Figs 1–3 (p.7), Vout 4.5–5.5 V.**
- **TPS55288/TPS552882:** no curves below Vin = 5 V (TPS55288 p.10 has Vin 5/9/12/20 V only). **UNKNOWN.**

**Verdict:**
- **≥ 86 % at 3.0 V: realistic** for every shortlisted part.
- **> 95 % at 4.0 V: plausible only for TPS61288/MP3431-class boosts** with DCR ≤ 5 mΩ, which may conflict with the 5×5–7×7 mm inductor size. It is unverified for the 4-switch buck-boost.
- The shunt costs I²R = 0.16 W per 10 mΩ, about 0.9 % at 18 W. Use 5 mΩ plus amplifier gain.

**Ability to regulate when the required Vout < Vin:**
- **Yes:** TPS552882, TPS55288, TPS552892, TPS55289.
- **No, uncontrolled current through L + HS FET body diode** (inferred): TPS61288, TPS61088, TPS61089, MP3431, TPS61178.
- **No, pass-through with the HS FET fully on** (worse): TPS61022 (p.11), MP3432 (p.16–17).
- **No, pass-through but limited to ILIM_pre** (0.25–1.7 A, p.5): TPS61236P.

**Design-pattern note (all boosts with CC through FB).**
- With CC via FB, an open load makes FB → 0, so Vout runs to the IC's OVP: 19 V (TPS61288), 16.5 V (MP3431), 13.2 V (TPS61088).
- Reconnecting a diode to that charged output capacitor is destructive. A **second FB path (voltage clamp at about 5.5–6 V)** is therefore mandatory, and so is a series disconnect FET.
- LM5155x/LM5156x OVP is sensed on FB (107–113 % of VREF, p.7), so it is ineffective in this scheme.

---

## 6. SPICE model availability

All model information is from ti.com product pages retrieved 2026-10-24 (PWR-18). The zip files were not downloaded, so "unencrypted" is TI's own label.

| Part | Model (TI lit #) | Encryption | ngspice usable? |
|---|---|---|---|
| TPS61088 / -Q1 | Unencrypted PSpice Transient Model Package (SLVMAU6, Rev A), listed on the -Q1 page | Unencrypted | Likely, after PSpice→ngspice syntax conversion. Untested. |
| TPS61089 | Unencrypted PSpice Transient (SLVMBK5, Rev C) | Unencrypted | Likely; untested |
| TPS61288 | "TPS61288 PSPICE Model" (SLVMDH8) | **UNKNOWN** (not labelled) | UNKNOWN |
| TPS61178 / TPS611781 | Unencrypted PSpice Transient (SLVMC02 / SLVMC10, Rev A) | Unencrypted | Likely |
| TPS61022 | Unencrypted PSpice Transient (SLVMCZ3, Rev A) | Unencrypted | Likely |
| TPS61236P | Unencrypted PSpice Transient (SLVMAU0, Rev B) | Unencrypted | Likely |
| TPS61378-Q1 | "TPS61378-Q1 FPWM Version PSpice model" (SLVMDF2) | **UNKNOWN** | UNKNOWN |
| TPS55288 | "TPS55288 encrypted PSpice model" (SLVMDD9) | **Encrypted** | **No** |
| TPS552882 | none listed (EVMs only) | — | **No model** |
| TPS55289 / TPS552892 | Encrypted PSpice (SLVMDY0 / SLVME05) | **Encrypted** | **No** |
| LM5155x | Unencrypted PSpice transient (SNVMBL2 Rev H); unencrypted average (SNVMBY3 Rev B); TINA-TI (SNVMBV7) | Unencrypted | Likely |
| LM5156x | Unencrypted transient (SNVMBV9 Rev H); unencrypted average (SNVMC69 Rev A) | Unencrypted | Likely |
| MP3431 / MP3432 | UNKNOWN (MPS site blocked automated access) | UNKNOWN | UNKNOWN |
| XL6009 | none found | — | No |

**Implication:** the rank-1 buck-boost has no usable model, so CC-loop and overshoot work must rely on a generic averaged 4-switch model or bench testing. For boosts, TPS61088's unencrypted model can stand in for the TPS6108x/TPS61288 class until SLVMDH8 is inspected.

---

## 7. Open questions / UNKNOWNs (for lead engineer)

1. **Vf vs Vbat:** we need the laser agent's Vf(I, T) at the lowest current setpoint and the hottest case. If Vf_min < 4.2 V + margin, a boost-only design needs either a series linear element that dissipates (Vbat − Vf)·I, or a "no-operation above Vbat X" interlock.
2. **TPS61088 lifecycle:** the ti.com product page, symlink datasheet and lit number SLVSCM8 all returned 404 on 2026-10-24. TI store inventory still shows 26,416 TPS61088RHLR. Confirm with TI or a distributor. The English Rev D (SLVSCM8D, Aug 2021) PDF was not retrieved.
3. **MP3431/MP3432:** only Rev 1.0 (2017/2019) distributor copies were available. Current revision, SPICE model, LCSC code, price and stock are all UNKNOWN. The guarantee of the 19 A minimum relies on "over-temperature correlation, not tested in production".
4. **TPS552882 CC loop:** the datasheet calls it "slow". Startup and step response into a diode load, and the overshoot magnitude, are UNKNOWN, and there is no model. Bench test or simulate with a generic model.
5. **Efficiency at our point:** no datasheet curve covers Vin 3–4.2 V with Vout 4.3–5 V at 4 A for the buck-boost. Boost curves (TPS61088-Q1 Fig 1, TPS61288 Fig 7-5) are close but are EVM conditions with large inductors.
6. **Inductor size vs current limit:**
   - TPS61288 has a fixed 12–17.1 A limit and MP3431 a fixed 19–23.5 A limit. TI's rule (Isat > current limit) pushes toward the 10 × 11 mm class.
   - TPS552882 (RILIM average limit) and TPS61088/MP3432 (programmable peak) allow a smaller Isat.
   - Needs passives-agent input.
7. **External buck FETs for TPS552882:**
   - Need about 5 mΩ, Vgs(th) compatible with VCC ≈ VIN at start-up, and 2 × small packages on the 22 mm board.
   - Footprint impact to be assessed.
8. **Sourcing:**
   - Only TPS61088RHLR (LCSC C87357 and TI inventory), TPS552882RPMR (TI inventory 2,950), TPS61022RWUR (TI inventory 0) and TPS61088QRHLRQ1 (TI inventory 0) were retrieved.
   - All other LCSC/JLCPCB codes, Mouser/DigiKey stock and prices are UNKNOWN.
   - The LCSC code for XL6009 was not found; C73332 = XL4005E1.
9. **Not evaluated** (datasheets not retrievable within budget): MAX77831, MAX77857, LT3757/LT3757A, LT8330, LTC3786, LTC7804, Silergy, Richtek, ETA, Injoinic and SGMicro parts. Candidates such as MAX77831/MAX77857 might fit and should be checked before freezing the architecture.
10. **Start-up at 2.8–3.0 V:**
    - TPS552882/TPS55288 rising UVLO is ≤ 3.0 V max and TPS552892 VIN min is 3.0 V, so they may refuse to start on a sagging cell.
    - TPS61288 (≤ 2.4 V) and MP3431 (2.7 V) are fine.
