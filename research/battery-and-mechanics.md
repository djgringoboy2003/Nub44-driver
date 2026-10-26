# Battery and Mechanical Integration Research: 22 mm NUBM44 Boost Driver

- **Scope:** cell selection, electrical suitability at 5 to 8 A, undervoltage, contact polarity, pill/driver mechanics, existing products, and clicky/e-switch mode switching.
- **Load assumed:** NUBM44 at up to 4 A × ~4.6 V ≈ 18.4 to 20 W out. A boost converter at 86 to 95 % efficiency makes that **19.4 to 23.3 W in (22 W nominal)**.
- **Date:** 2026-10-24.
- **Source IDs:** `BAT-xx` refer to `research/sources/battery-sources.md`.
- **Local datasheet copies:** `research/datasheets/bat_*`.

**How the evidence is labelled:**

- **Mfr:** manufacturer document.
- **Indep.:** independent test (Battery Mooch or HKJ / lygte-info.dk).
- **Vendor claim, unverified:** the rating comes only from a rewrapper's wrapper or listing. Where HKJ measured such a cell, the measurement is given next to the claim.
- **Derived:** my own arithmetic on sourced data. The method is shown.
- **Assumption / UNVERIFIED:** an engineering estimate with no source fetched in this session. Measure these values.

---

## 1. Summary

**Recommended formats.** Use an **18650 or 21700 high-drain cell**. Two conditions apply:

- The manufacturer CDR must be **≥ 15 A**, and an independent rating must also be **≥ 15 A**.
- DC internal resistance should be **≤ ~25 mΩ**.

Preferred cells:

| Format | Cells | Mooch independent rating |
|---|---|---|
| 18650 | Molicel P28A, Molicel P26A | 25 A each |
| 18650 | LG HG2 | 20 A for the 2018 lot; 17 A for later lots |
| 18650 | Samsung 30Q, Sony/Murata VTC6 | 15 A each |
| 21700 | Samsung 40T | 30 A for the 40T3 |
| 21700 | Molicel P42A | ~25 A |
| 21700 | Samsung 50S | 20 A |
| 21700 | Molicel P45B | Mfr 45 A with 80 °C cut-off; independent value not retrieved |

Sources: BAT-04, BAT-06 to BAT-09, BAT-11 to BAT-15.

**Why ≥ 15 A:**

- **Worst-case battery current is 7.6 to 8.3 A.** This is 22 to 23.3 W drawn at a driver-input voltage of 2.9 to 2.8 V (§3.3).
- **Mooch's own guidance** is to stay under the CDR, and under 75 % of CDR for high-capacity cells (BAT-11). That puts the floor at 8.3 A / 0.75 ≈ **11 A**.
- **15 A gives about 1.9× margin.** In practice it also selects cells with ≤ 25 mΩ DCIR, which keeps sag and self-heating low (§3).
- **10 A-class "high-capacity" cells are not acceptable.** Examples: Samsung 35E/35E3 (8 A CDR), LG MJ1 (10 A, 45 mΩ), Panasonic NCR18650GA (10 A, 44 mΩ), Samsung 50E (9.8 A). They would run at 80 to 100 % of CDR, or above it, near end of discharge (BAT-11).

**Run time at 22 W in.** These figures use cell energy to 3.0 V at ~6 A (HKJ data, BAT-17):

- 18650: about **22 to 26 min**
- 21700: about **31 to 36 min**
- 14500, 18350 and 18500 high-drain cells: **7 to 11 min**

**Formats rejected or marginal:**

| Format | Verdict | Key numbers |
|---|---|---|
| **16340 / RCR123A** | **Unsuitable** | The best credible cell, Vapcell INR16340 800 mAh, carries a 7 A *vendor claim*. HKJ says it "can easily deliver 3A, but it pressed above that", and it delivered only 141 mAh at 15 A. Its 10 s-pulse IR is ≈ 65 to 70 mΩ at mid-charge and 130 to 225 mΩ when full. That gives a cell self-heating of 3.5 to 4.8 W at our current. The model collapses near empty (V_oc 3.4 V), meaning it cannot deliver 22 W. Most other 16340s are rated 3 A. Protected 16340s trip at 2.8 to 5.6 A (median 4.4 A, n = 18). Sources: BAT-17, BAT-36 to BAT-38. |
| **14500** | **Marginal at best; effectively unsuitable** | Only the Vapcell H10 (10 A, *vendor claim*) can do it. HKJ measured 849 mAh (2.80 Wh) at 10 A, but only 581 mAh above 3.2 V. Its IR is ~30 to 35 mΩ and "production [is] not completely consistent". That means about **7 min** of run time and ~30 K adiabatic self-heating. Sony US14500V is rated 5 A. Protected 14500s trip at 2.1 to 5.4 A (median 3.5 A, n = 25). Sources: BAT-17, BAT-32 to BAT-35. |
| **18350** | **Marginal** | Vapcell 1100 mAh 9 A and 850 mAh 10 A are *vendor claims*, partly confirmed by HKJ at 10 A. They have ~31 to 39 mΩ and 2.6 to 3.1 Wh, giving about **8 min**. HKJ reports 10 A as "a bit compromised" (Keeppower IMR18350) and "serious trouble at 15A" (Vapcell 1100). Sources: BAT-28 to BAT-31. |
| **18500** | **Marginal** | Only the Efest IMR18500 1000 mAh (10 A, *vendor claim*; HKJ found it "can deliver 15A") is electrically OK. Its ≈ 4.0 Wh gives about **11 min**. High-capacity 18500s are rated ≤ 4 A, or are protected cells that trip at 4.8 to 8.9 A. Sources: BAT-17, BAT-25 to BAT-27. |
| 18650 / 21700 | **Recommended** | See the table above. |

**"Physically fits" versus "electrically suitable".** A 22 mm driver does not decide the cell format; the host tube does. The driver can be made to contact any of these cells. However, only 18650 and 21700 high-drain cells deliver 22 W continuously within their independent ratings with acceptable sag.

**Polarity (§5).** In electrochemistry the battery *cathode* is the **positive** electrode during discharge. The universal flashlight/driver convention is **centre spring = battery positive (B+)** and **outer ring = battery negative (B−)**, reached via tailcap → body → pill. So "centre spring connected to the battery cathode" means **centre spring = B+**, which agrees with the earlier documentation. Confidence is **high**. The owner must still confirm this on the actual host (procedure in §5.4).

---

## 2. Cell table

Notes on the columns:

- **CDR** = continuous discharge rating.
- **Mooch E-score** = Wh delivered down to 3.2 V at the stated current (BAT-11 definitions).
- **HKJ @10 A** = capacity and energy to 2.8 V at 10 A, read from HKJ's index table (BAT-17). In that table, "full" means discharge to 2.8 V.
- **Max temp** is the discharge temperature limit from the datasheet. "Surface" means cell-surface temperature; otherwise it is ambient.

### 2.1 18650

| Cell | Capacity | Mfr CDR | Independent rating / test | IR | Cut-off | Max temp (discharge) | Sources |
|---|---|---|---|---|---|---|---|
| **Molicel INR-18650-P28A** | 2800 mAh typ, 2600 mAh min (V1) / 2700 mAh min (V2) | **35 A** "maximum discharge current" | Mooch: **25 A** continuous, 35 A "temperature-limited" (keep < 60 °C). E-score **8.4 Wh @5 A, 7.9 Wh @10 A**. HKJ: 2596 mAh / 9.12 Wh @10 A. | AC ≤ 20 mΩ; DC 20 mΩ (10 A/1 s) per Mfr. Mooch 18.2 mΩ. HKJ pulse ≈ 19 to 21 mΩ mid-SOC. | 2.5 V | −40 to 60 °C ambient | BAT-04, BAT-05, BAT-10, BAT-11, BAT-15, BAT-18 |
| Molicel INR-18650-P26A | 2600 mAh | 35 A (Mooch "Rated CDR" column; datasheet not retrieved) | Mooch: **25 A** / 35 A. E-score 7.9 Wh @5 A, 7.5 Wh @10 A. HKJ: 2531 mAh @10 A. | Mooch 15.2 mΩ (2021 lot) | UNKNOWN (datasheet not retrieved) | UNKNOWN | BAT-11, BAT-17 |
| **Samsung INR18650-30Q** | 3000 mAh nominal (≥ 2900 mAh @10 A) | **15 A** at 25 °C | Mooch: **15 A**, 20 A only if kept ≤ 75 °C. E-score **7.5 Wh @10 A**, 6.3 Wh @15 A. HKJ: "can handle about 15A continuous", 2799 mAh / 9.67 Wh @10 A. | AC ≤ 26 mΩ (spec v0.0, 2014). A later spec quoted by HKJ gives < 18 mΩ AC and < 30 mΩ DC. Mooch 22.1 mΩ. | 2.5 V | −20 to 75 °C surface | BAT-01, BAT-11, BAT-19 |
| **Sony/Murata US18650VTC6** | 3000 mAh rated, 3120 mAh typ | **15 A**; 30 A only with 80 °C cut-off (official spec as quoted by HKJ) | Mooch: **15 A**, 20 A only if < 80 °C. E-score **7.7 Wh @10 A**. HKJ: just under 80 °C at 15 A; reached 91 °C in the 20 A and 30 A tests. 2870 mAh @10 A. | 12.8 mΩ typ AC (tech info rev 0.1). Spec 8 to 18 mΩ (per HKJ). Mooch 21.4 mΩ. | 2.0 V spec end-of-discharge; 2.5 V in rate tests | −20 to 60 °C | BAT-02, BAT-11, BAT-20 |
| **LG INR18650HG2** | 3000 mAh | **20 A** | Mooch: **20 A** (2018 lot), **17 A** for the later "QR-code" lot and HG2L. E-score 7.5 to 7.8 Wh @10 A. HKJ: 81 °C after a 20 A run; 2702 mAh @10 A. | AC ≤ 20 mΩ. Mooch 23.8 to 24.0 mΩ. | 2.5 V | −20 to 75 °C surface | BAT-03, BAT-11, BAT-21 |
| *Counter-example:* Samsung 35E3 | 3350 mAh | 8 A | Mooch 8 A; IR 26.7 mΩ | — | — | — | BAT-11. **Unsuitable** (CDR ≤ worst-case current). |
| *Counter-example:* LG MJ1 | 3500 mAh | 10 A | Mooch 10 A; IR 45.1 mΩ; E-score 5.7 Wh @10 A | — | — | — | BAT-11. **Marginal / not recommended.** |

### 2.2 21700

| Cell | Capacity | Mfr CDR | Independent rating / test | IR | Cut-off | Max temp | Sources |
|---|---|---|---|---|---|---|---|
| **Samsung INR21700-40T** | 4000 mAh std (≥ 3900 mAh @10 A) | **35 A** without temperature cut; 45 A with 80 °C cut | Mooch (40T3, 2021): **30 A** continuous, 40 A if kept < 80 °C; best at ≤ 25 A. HKJ: 3738 mAh / 13.23 Wh @10 A. | AC ≤ 12 mΩ. Mooch DC avg 12.9 mΩ. | 2.5 V | −20 to 60 °C ambient; ≤ 80 °C surface | BAT-06, BAT-12, BAT-22 |
| **Molicel INR-21700-P42A** | 4200 mAh typ, 4000 mAh min | **45 A** "continuous" (V3, 2019; HKJ quote: "cycle life is reduced at high rates") | Mooch (2020): true continuous estimate **~25 A**; the 45 A figure is temperature-limited (max 85 °C, 75 °C recommended). HKJ: 3898 mAh / 13.84 Wh @10 A. | AC 10 mΩ typ; DC 16 mΩ (10 A/1 s) typ | 2.5 V | −40 to 60 °C | BAT-07, BAT-14, BAT-23 |
| **Molicel INR-21700-P45B** | 4500 mAh typ, 4300 mAh min | **45 A** continuous with 80 °C cut-off | Mooch tested it (2022-05-17, "an incredible cell"). **His rating value was not retrieved: UNKNOWN.** Not in the HKJ index. | AC 7 mΩ (30 % SOC); DC 15 mΩ (50 % SOC) typ. Molicel web page: max IR 13.8 mΩ, "22 % lower DCR than P42A". | 2.5 V | −40 to 60 °C | BAT-09, BAT-10, BAT-16 |
| **Samsung INR21700-50S** | 5000 mAh typ, 4800 mAh min (10 A) | **25 A** without temperature cut; 45 A with 80 °C cut | Mooch: **20 A** (his cells neared 90 °C at 25 A); 35 A non-continuous if < 80 °C. Tested 5117 and 5122 mAh. | AC ≤ 14 mΩ; DC UNKNOWN | 2.5 V | −20 to 60 °C ambient | BAT-08, BAT-13 |
| Sony/Murata US21700VTC6A | 4000 mAh | 30 A (40 A with 80 °C cut). This is the official spec as quoted by HKJ; the datasheet was not retrieved. | HKJ: "can easily deliver 20A"; heat problems at 30 A (one cell's internal fuse blew). 3616 mAh / 12.66 Wh @10 A. | UNKNOWN | UNKNOWN | UNKNOWN | BAT-24 |

### 2.3 18500, 18350, 14500, 16340 (small formats)

| Format | Cell | Capacity | CDR | Independent test (HKJ) | IR | Cut-off | Sources |
|---|---|---|---|---|---|---|---|
| 18500 | Efest IMR18500 1000 mAh (2017) | 1000 mAh | 10 A / 15 A pulse (**vendor claim, unverified**; Efest is a rewrapper) | "can deliver 15A". 1151 mAh / 3.97 Wh @10 A. | Derived R(3→10 A) ≈ 29 mΩ | UNKNOWN | BAT-17, BAT-25 |
| 18500 | Vapcell INR18500 L22 | 2200 mAh | 4 A (**vendor claim**) | Delivers 4 A with a small capacity drop. Unsuitable at 6 to 8 A. | AC ≤ 50 mΩ (vendor) | 2.5 V | BAT-26 |
| 18500 | Panasonic NCR18500A | 2040 mAh typ | UNKNOWN (not in quoted spec) | "not a high current battery" | Derived R(0.2→3 A) ≈ 74 mΩ | UNKNOWN | BAT-27 |
| 18500 | Keeppower 18500 2000 mAh P1850C2 (protected) | 2000 mAh | UNKNOWN | **Protection trips at 7.7 A** | — | — | BAT-17 |
| 18350 | Vapcell INR18350 1100 mAh "9A" | 1100 mAh | 9 A (**vendor claim**) | "can also deliver the rated 9A, but … serious trouble at 15A". 954 mAh / 3.09 Wh @10 A, but only 544 mAh above 3.2 V. | Pulse ≈ 31 to 35 mΩ mid-SOC; vendor AC ≤ 25 mΩ | 2.5 V | BAT-28 |
| 18350 | Vapcell INR18350 850 mAh "10A" | 850 mAh | 10 A (**vendor claim**) | "can deliver the rated 10A". 816 mAh / 2.63 Wh @10 A (745 mAh to 3.0 V). | Vendor AC ≤ 27 mΩ | 2.5 V | BAT-29 |
| 18350 | Keeppower IMR18350 750 mAh | 750 mAh | 8 A / 15 A pulse (**vendor claim**) | Good to 7 A; 10 A "a bit compromised"; 632 mAh @10 A | Derived R(3→10 A) ≈ 47 mΩ | 2.5 V | BAT-30 |
| 18350 | Keeppower 18350 1200 mAh P1835C2 (protected) | 1200 mAh | 8 A (vendor) | 5 A fine; "7A is limited by the protection"; HKJ estimate ~8 A | Derived R(0.2→3 A) ≈ 66 mΩ | 2.5 V | BAT-31 |
| 14500 | Vapcell INR14500 H10 | 1000 mAh | 10 A (**vendor claim**) | 849 mAh / 2.80 Wh @10 A; only 581 mAh above 3.2 V at 10 A. "factory has not got a completely consistent production yet". | Pulse ≈ 30 to 35 mΩ mid-SOC, > 40 mΩ below ~3.2 V; vendor AC ≤ 18 mΩ | 2.5 V (−20 to 75 °C vendor) | BAT-32 |
| 14500 | Sony US14500V | 680 mAh | 5 A (Sony spec as quoted by HKJ) | Fairly constant to 5 A. **Below our current.** | — | 2.5 V | BAT-33 |
| 14500 | Keeppower 14500 1000 mAh P1450C2 (protected) | 1000 mAh | 1.9 A | **Trip 3.9 A** | — | 2.75 V | BAT-35 |
| 16340 | Vapcell INR16340 800 mAh (White) | 800 mAh | 7 A (**vendor claim**) | "can easily deliver 3A, but it pressed above that"; 141 mAh at 15 A | Pulse ≈ 65 to 70 mΩ mid-SOC, 130 to 225 mΩ when full. This contradicts the vendor's "≤ 20 mΩ AC". | 2.5 V | BAT-36 |
| 16340 | Vapcell INR16340 T8 | 850 mAh | 3 A (vendor) | 554 mAh at 3 A vs 887 mAh at 0.2 A | Vendor AC ≤ 65 mΩ | 2.5 V | BAT-37 |
| 16340 | Keeppower 16340 P1634C2 (protected) | 850 mAh | 3 A | **Trip 4.4 A** | — | 2.5 V | BAT-38 |

**Small-format coverage.** No independent test was found of any 16340 at ≥ 7 A, or of any 14500 other than the H10 at 10 A. That covers HKJ's index (tests through ~2021) and one targeted search. Newer cells are **UNKNOWN**, and Mooch does not publish 14500 or 16340 ratings in the tables retrieved.

---

## 3. Voltage sag, run time and heating

### 3.1 Model and formulas

- **Constant input power** at the driver terminals: `P_in = V_drv · I`.
- **Voltage at the driver:** `V_drv = V_oc − I·(R_cell + R_path)`.
- **Solved for V_drv:** `V_drv = [V_oc + √(V_oc² − 4·R_tot·P_in)] / 2`. If the term under the root is negative, the source cannot deliver P_in and the operating point collapses.
- **Losses:** `P_cell = I²·R_cell` and `P_path = I²·R_path`.
- **Run time:** `t ≈ E_cell(to 3.0 V @ ~6 A) / (P_in + P_path)`.
- **Adiabatic self-heating:** `ΔT ≈ P_cell·t / (m·c)`, with an **assumed** c = 0.9 J g⁻¹ K⁻¹. This is an upper bound with no host heat-sinking. It also ignores heat flowing in from the laser head.

**Inputs:**

| Input | Value | Basis |
|---|---|---|
| P_in | 22 W | 19.4 to 23.3 W range |
| R_cell | Mooch DCIR where available, otherwise Mfr DC or HKJ pulse IR (§2); ×1.5 near empty (conservative) | HKJ's 10 s-pulse IR charts show IR rising ~1.2 to 1.5× by ~3.2 V and ≥ 1.5× near 3.0 V (BAT-18, BAT-28, BAT-32, BAT-36) |
| R_path | **Assumed 20 mΩ** (bypassed springs, good switch) and **60 mΩ** (unbypassed springs plus a clicky) | **UNVERIFIED.** Measure this (§6.4). |
| E_cell | Derived: HKJ's mWh to 3.0 V interpolated linearly between the 3 A and 10 A columns | BAT-17 |

The script is `sag_calc.py`, kept in the session scratchpad.

**Derived effective resistance.** Taking the average voltage as `V_avg = mWh / mAh` (to 2.8 V):

```
R(3→10 A) = (V_avg@3A − V_avg@10A) / 7 A
```

| Cell | R(3→10 A) |
|---|---|
| 40T | 12.1 mΩ |
| VTC6A | 13.0 mΩ |
| P42A | 14.0 mΩ |
| P28A | 16.2 mΩ |
| 30Q | 19.0 mΩ |
| VTC6 | 19.1 mΩ |
| HG2 | 21.5 mΩ |
| Efest 18500 | 28.7 mΩ |
| 14500 H10 | 31.5 mΩ |
| Vapcell 18350 1100 | 39.1 mΩ |
| Keeppower IMR18350 | 47.1 mΩ |

These agree with Mooch's start-of-discharge DCIR to within a few mΩ.

### 3.2 Results at 22 W

| Cell | V_oc (state of charge) | R_path | I (A) | V_cell terminal | V_driver | P_cell (W) | P_path (W) |
|---|---|---|---|---|---|---|---|
| P28A 18650 | 4.1 (full) | 20 mΩ | 5.66 | 4.00 | 3.88 | 0.58 | 0.64 |
| P28A 18650 | 3.7 (mid) | 20 mΩ | 6.36 | 3.58 | 3.46 | 0.74 | 0.81 |
| P28A 18650 | 3.7 (mid) | 60 mΩ | 6.97 | 3.57 | 3.15 | 0.89 | **2.92** |
| P28A 18650 | 3.4 (near empty, R×1.5) | 20 mΩ | 7.19 | 3.20 | 3.06 | 1.41 | 1.03 |
| P28A 18650 | 3.4 (near empty) | 60 mΩ | **8.19** | 3.18 | **2.68** | 1.83 | **4.03** |
| 30Q 18650 | 3.7 | 20 mΩ | 6.41 | 3.56 | 3.43 | 0.91 | 0.82 |
| 30Q 18650 | 3.4 | 60 mΩ | 8.41 | 3.12 | 2.62 | 2.34 | 4.24 |
| HG2 18650 | 3.7 | 20 mΩ | 6.44 | 3.55 | 3.42 | 0.99 | 0.83 |
| 40T 21700 | 3.7 | 20 mΩ | 6.30 | 3.62 | 3.49 | 0.51 | 0.79 |
| 40T 21700 | 3.4 | 60 mΩ | 7.94 | 3.25 | 2.77 | 1.22 | 3.79 |
| P42A 21700 | 3.7 | 20 mΩ | 6.34 | 3.60 | 3.47 | 0.64 | 0.80 |
| Efest 18500 (10 A) | 3.7 | 20 mΩ | 6.51 | 3.51 | 3.38 | 1.23 | 0.85 |
| Vapcell 18350 (9 A) | 3.7 | 20 mΩ | 6.56 | 3.48 | 3.35 | 1.42 | 0.86 |
| Vapcell 18350 (9 A) | 3.4 | 60 mΩ | 9.19 | 2.95 | 2.39 | 4.18 | 5.07 |
| Vapcell 14500 H10 | 3.7 | 20 mΩ | 6.56 | 3.48 | 3.35 | 1.42 | 0.86 |
| Vapcell 16340 (7 A claim) | 3.7 | 20 mΩ | 7.17 | 3.21 | 3.07 | **3.49** | 1.03 |
| Vapcell 16340 (7 A claim) | 3.4 | 60 mΩ | — | — | **collapse** | — | — |

**Run time and heating** (operating point at V_oc 3.7 V):

| Cell | E to 3.0 V (Wh) | Run time (R_path 20 / 60 mΩ) | P_cell (W) | Adiabatic ΔT, cell only |
|---|---|---|---|---|
| P28A | 9.07 | 24 / 22 min | 0.74 to 0.89 | 25 to 28 K |
| 30Q | 9.51 | 25 / 23 min | 0.91 to 1.10 | 32 to 35 K |
| VTC6 | 9.89 | 26 / 24 min | 0.88 to 1.06 | 33 to 36 K |
| HG2 | 9.23 | 24 / 22 min | 0.99 to 1.19 | 34 to 37 K |
| 40T | 13.03 | 34 / 31 min | 0.51 to 0.61 | 17 to 18 K |
| P42A | 13.79 | 36 / 33 min | 0.64 to 0.77 | 22 to 24 K |
| Efest 18500 | 4.04 | 11 / 10 min | 1.23 to 1.50 | mass UNKNOWN |
| Vapcell 18350 1100 | 3.17 | 8 / 8 min | 1.42 to 1.75 | 30 to 34 K |
| Vapcell 14500 H10 | 2.79 | 7 / 7 min | 1.42 to 1.75 | 29 to 32 K |
| Vapcell 16340 | n/a (no ≥ 6 A data) | < 5 min est. | 3.5 to 4.8 | unsuitable |

**Cross-check against Mooch's E-scores** (Wh to 3.2 V at 10 A):

| Cell | E-score | Run time at 22 W |
|---|---|---|
| P28A | 7.9 | ~21 min |
| VTC6 | 7.7 | ~21 min |
| 30Q | 7.5 | ~20 min |
| HG2 | 7.5 | ~20 min |

These are lower than the HKJ figures because they use a 3.2 V end-point.

### 3.3 Interpretation

1. **Worst-case battery current.** At the LVP threshold it is `I = P_in / V_drv`:
   - 22 W at 2.9 V gives **7.6 A**.
   - 23.3 W (20 W out at 86 %) at 2.8 V gives **8.3 A**.

   The cell, springs and switch must be specified for **≥ 8.5 A continuous**.
2. **Path resistance matters as much as cell choice among good cells.** Raising R_path from 20 to 60 mΩ has two effects:
   - The driver-input voltage near empty falls from ~3.06 V to ~2.68 V.
   - **2.9 to 4.3 W** is dissipated in springs, switch and threads. That heats the cell top and tail, and the LVP trips with charge still left in the cell.

   Bypassed springs and a low-resistance switch are therefore required (§6.4).
3. **Sag from the cell alone** at mid-charge and 6.4 A is 0.12 to 0.16 V for the recommended 18650s and 0.08 to 0.10 V for the 21700s. For 14500/18350 cells it is ~0.22 V. For the best 16340 it is ~0.5 V.
4. **Heat.** The recommended cells self-heat about 0.5 to 1.2 W, which is acceptable. The 14500/18350 cells self-heat 1.4 to 1.8 W in a cell of only 20 to 26 g. The 16340 self-heats 3.5 to 10 W.

   The host also receives the laser module's waste heat (see the laser-diode report). Cell temperature must stay within the datasheet discharge limits: **60 °C ambient** (Samsung, Molicel, Sony) and **75 °C surface** (30Q, HG2). Temperature-limited "45 A" ratings require an 80 °C cut-off.

---

## 4. Undervoltage recommendation

**Manufacturer end-of-discharge voltages:**

- 2.5 V for Samsung 30Q/40T/50S, LG HG2, Molicel P28A/P42A/P45B and the Vapcell small cells (BAT-01, -03 to -09, -28, -32, -36).
- 2.0 V spec end-of-discharge for Sony VTC6 (BAT-02, BAT-20).
- Protected Keeppower 14500: 2.75 V (BAT-35).

**Recommended LVP scheme for this driver.** These are design values derived from §3; validate them in test.

1. **Measure at the driver input, with time filtering.** Average over ≥ 0.5 to 2 s so that start-up and mode-change transients don't trip the LVP.
2. **Warning / step-down at V_in(loaded) ≤ 3.1 V.** Reduce laser current to ≤ 50 % and give an indication (blink or step).
3. **Hard shutdown at V_in(loaded) ≤ 2.9 V** (absolute floor 2.8 V), latched.
   - Clear the latch only on a full power cycle.
   - At power-up, if the *resting* voltage is < 3.2 V, allow only a low mode, or refuse to start.
   - At 7.6 A with a good path (R_tot ≈ 45 mΩ), a 2.9 V shutdown corresponds to a resting voltage of ≈ 3.2 V. That leaves margin above the 2.5 V spec minimum.
   - With a 60 mΩ path, the same threshold trips at a resting voltage of ≈ 3.6 V, wasting ~40 % of capacity. Two remedies:
     - **IR-compensated LVP:** estimate `V_oc ≈ V_in + I_in·R_est` and shut down at an estimated V_oc ≈ 3.2 V, keeping the absolute 2.8 V floor.
     - **Fix the path resistance.**
4. **Converter UVLO must sit below the firmware LVP**, for example UVLO ≤ 2.6 V.
   - Otherwise the converter can "hiccup": the load drops, the cell recovers 0.2 to 0.4 V, and the converter restarts. A pulsing class-4 laser is a safety issue.
   - Firmware must latch off, not rely on UVLO.

**Protected versus unprotected cells.** HKJ measured PCB trip currents (BAT-17), summarised below.

| Format | n | Trip range | Median | Implication at 5 to 8 A |
|---|---|---|---|---|
| 14500 | 25 | 2.1 to 5.4 A | 3.5 A | **Will trip** |
| 16340 | 18 | 2.8 to 5.6 A | 4.4 A | **Will trip** |
| 18350 | 4 numeric + 2 "High" | 4.0 to 8.0 A | 6.6 A | Will trip / marginal |
| 18500 | 11 | 4.8 to 8.9 A | 7.2 A | Marginal |
| 18650 | 99 numeric + 14 "High" | 2.8 to 20 A (2019–2020 tests: 6.1 to 18.8 A) | 8.5 A | **Coin-flip.** Only use protected cells with a verified trip ≥ 12 A. |
| 21700 | 3 numeric + 2 "High" | 11.2 to 15 A | 14.4 A | Usually OK |

In this table, "High" means the cell did not trip within HKJ's test range.

- **Prefer unprotected high-drain cells plus driver-side LVP.** Protected cells are also longer and lose some voltage at high current (HKJ, BAT-31, BAT-38). A protection trip during use gives an abrupt shutdown, which is tolerable but should be documented.

**Button top versus flat top.**

- **How HKJ classifies tops (BAT-17):**
  - "SB" (small-diameter button) usually makes a cell 1 to 2 mm longer.
  - "flat: The top is flat and may be below the border", meaning recessed below the wrap or insulator.
  - "Button top and protected batteries will be longer."
- **Most recommended high-drain cells are flat-top.** 30Q, VTC6, P26A, P28A, HG2, 40T and VTC6A are all "flat"; P42A is "LB" (large button).
- **The centre spring must reach a recessed flat top** with margin. Design for at least 1.5 to 2 mm of guaranteed compression with a flat-top cell (assumption; confirm on the host).
- **The spring tip must fit inside the exposed positive cap** so it cannot bridge to the can's crimp (B−) through a damaged wrap. Measure the cap diameter on the target cells (UNKNOWN; not retrieved).
- **Keep battery-side components** within a keep-out that a tilted cell cannot reach.

---

## 5. Polarity: terminology and host convention

### 5.1 Terminology

- **Electrochemistry.** The cathode is the electrode from which conventional current leaves a polarised device. In a battery in use (a galvanic cell discharging), the cathode is the **positive terminal**. When recharging, the cathode is the negative terminal (Wikipedia "Cathode", last edited 2026-08-09, BAT-40).
  - Li-ion datasheets avoid this ambiguity by saying **positive / negative** terminal. The 30Q spec, for example, speaks of "positive and negative terminal" (BAT-01).
  - Industry naming calls the positive (oxide) electrode the "cathode", named for discharge.
  - The **IUPAC Gold Book** wording ("electrode at which reduction occurs") **could not be retrieved** this session. The site is Cloudflare-protected, and the archived ID C00896 now maps to a different term in Gold Book v5.0.0 (BAT-39). The verbatim IUPAC text is **UNVERIFIED**.
- **Electronics.** For a diode, including an LED or laser diode, the cathode is "the negative terminal at the pointed end of the arrow symbol", i.e. the n-side (BAT-40). Colloquially many electronics people therefore read "cathode" as "negative".
- **Consequence.** "Centre spring connected to the battery cathode" is **ambiguous by itself**:
  - Electrochemical reading: **B+**.
  - Diode-style colloquial reading: **B−**.

  The phrase may also have been carried over from wiring the laser diode's cathode (LD−). The two documents differ only in which convention the writer had in mind.

### 5.2 Host / driver convention evidence

- **Flashlight forum explanation (BLF, 2012).** "The center spring on the driver is positive." "Battery neg goes through the tailcap switch to the host to the support spring to the pill/outer ring of driver."
  - This was written by Rufusbduck to correct another member's description of the spring as negative, and a second member agreed (BAT-41).
  - This exchange also shows the same confusion arising in the community.
- **OSH Park driver PCB project.** It labels the exposed copper rim on the driver as "Batt-" and/or ground (BAT-42). This comes from a search-engine summary; the page was not fetched.
- **Physical convention.** Cylindrical cells in head-driver flashlights are inserted button/positive toward the head spring. The negative can contacts the tail spring, which returns through the tail switch and the body tube to the head, the pill and the driver ring (BAT-41).
  - HKJ's emphasis on button versus flat tops for spring-contact equipment reflects this (BAT-17).
- **Not obtained this session:** Kaidomain/Convoy/NANJG driver listings, laser-host 20 mm/22 mm boost-driver listings, and ToyKeeper/Anduril hardware docs. All are **UNKNOWN**.

### 5.3 Recommended interpretation

**Centre spring = battery positive (B+).** This is the "cathode" in the electrochemical/IUPAC sense during discharge.

**Outer ring / retaining-ring contact = battery negative (B−, driver GND).** It returns via the host body and the tail switch.

This matches the earlier documentation and the industry convention. **Confidence: high (~90 %) for a conventional head-driver laser/flashlight host.** In schematics and the BOM, use **"B+ (centre spring)"** and **"B− (outer ring)"** and **never "cathode/anode"** for battery contacts.

### 5.4 Residual ambiguity: owner must confirm

**Outcome (2026-10-25):** the owner accepts either orientation provided the board marks it, so the
convention above stands (DD-12). Both boards carry B+/B− silkscreen labels. The host facts below remain
UNKNOWN, and bench test T3.3 checks the host against the labels before first power.

**UNKNOWN for the owner's host:**

- Whether the host is reverse-polarity (cell positive toward the tail). Such hosts exist but were not documented here.
- Whether the driver sits at the tail (tail-cap drivers).
- Whether the body is isolated, for example by anodised threads or an insulated tube.
- Whether the tail switch is in the negative path. In most clicky hosts it is, which means the ring is **not connected to B− while the switch is off**. This matters for e-switch or standby designs.

**Verification procedure:**

1. Insert the intended cell, close the tail, and switch on.
2. With a DMM, measure from the pill/body to the spring-contact point (or to a probe touching the cell top through the pill). The spring should read **+3.x V** relative to the body.
3. Repeat with the switch off to confirm which path the switch breaks.
4. Check that the laser module's case and heatsink are isolated from both LD pins, or establish which pin they share.
   - If the LD case is common to LD− and the host body is B−, a low-side current-sense resistor would be shorted.
   - NUBM44 case polarity is **UNKNOWN** in this report; it is for the laser-diode research.

**Design hedge:** add reverse-polarity protection on the battery input, for example a P-MOSFET ideal diode. A backwards flat-top cell, or a reversed host, then cannot destroy the driver.

---

## 6. Mechanical integration notes

| Topic | Finding | Status |
|---|---|---|
| Driver diameters / adapters | 17 → 22 mm brass driver adapters (Convoy) are common. A builder fitted a 17 mm driver into a 23.5 mm cavity using them. | BLF search summary (BAT-43); detail not individually verified |
| Ground contact | The driver's outer ring is B−/GND. It is clamped by a retaining ring, or by press-fit or solder into the pill. One builder had to add solder to a driver ring "too thin to be secured by the retaining ring". | BAT-41, BAT-42, BAT-43 (summary) |
| PCB thickness | Common 17/20/22 mm flashlight drivers are typically 1.6 mm FR-4, with some at 1.0 to 1.2 mm. | **UNVERIFIED** this session; measure the host's retaining-ring thread depth and pill shoulder. |
| Ring width (battery side) | A continuous exposed-copper annulus is needed where the retaining ring or pill shoulder presses. Suggested start: **≥ 1.0 to 1.5 mm radial width**, ENIG, with stitching vias to inner GND planes. | **Assumption.** Measure the retaining-ring ID/OD and pill shoulder. |
| Component height, battery side | Must clear the retaining ring and a flat-top cell's insulator ring, and must not be reachable by a tilted cell. Suggested start: ≤ 1.0 to 1.5 mm and inside the retaining-ring ID; preferably all tall parts on the LED (pill) side. | **Assumption / UNKNOWN.** Measure the host. |
| Centre spring | One build needed a tall spring: "D-type spring (5/8/8/0.8 mm)", reported as "barely enough" for a 17 mm driver. Use a through-hole or SMD battery spring with ≥ 1.5 to 2 mm reserve travel for flat tops (§4). | BAT-43 (summary); dimensions not verified |
| Spring resistance (derived) | `R = ρ·L/A` for a conical spring of 0.8 mm wire, ~5 turns, mean diameter 6.5 mm (L ≈ 102 mm). Results in the next table. | Derived from typical resistivities (**UNVERIFIED**); measure with 4-wire |
| Spring bypass | A 20 AWG copper braid/wire 25 mm long: **0.8 mΩ, 53 mW at 8 A**. 22 AWG: 1.3 mΩ, 84 mW. **Bypass both head and tail springs.** Choose a low-resistance tail switch and clean, un-anodised contact faces. | Derived |
| Total path budget | Target **R_path ≤ 20 mΩ** (springs + contacts + switch + threads), i.e. ≤ 0.16 V and ≤ 1.3 W at 8 A. 60 mΩ costs ~4 W and early LVP (§3). | Target (assumption-based) |

**Derived spring resistance by material** (0.8 mm wire, L ≈ 102 mm):

| Spring material | R | Drop at 8 A | Dissipation at 8 A |
|---|---|---|---|
| Phosphor bronze | ≈ 23 mΩ | 0.19 V | **1.5 W** |
| Beryllium copper | ≈ 16 mΩ | — | 1.0 W |
| Carbon steel | ≈ 41 mΩ | — | 2.6 W |
| Stainless 302 | ≈ 146 mΩ | — | 9 W |

**Other mechanical and electrical notes:**

- **High-current routing.** About 8.5 A flows from the spring pad to the converter input. Use short, wide copper polygons (≥ 2 oz, or multiple layers with via arrays) between the spring pad, input capacitors, the converter and the ring.
- **Spring pad.** It must carry the spring's solder joint *and* the bypass wire joint. Use a large plated through-hole spring pad, or a spring with a soldered braid to a separate pad.
- **Keep-out.** Cover the battery side with solder mask except the ring and the spring pad. This avoids shorts to a damaged cell wrap or crimp.

---

## 7. Existing products and their claims

- **UNKNOWN.** One targeted search was made for 20 to 22 mm NUBM44 boost drivers: "X-Boost", "SXD", "FlexDrive", "Lazeerer", and Lasertack/DTR boost drivers. It returned nothing relevant.
- **No product claims are recorded.** None of input range, set currents, efficiency, size, mode scheme or known problems is recorded, to avoid inventing them.
- The only adjacent data point is a flashlight (LED) boost driver, the 17 mm MTN-BST2. A search summary describes it as 3 to 5.5 V in, for 6 V LEDs up to ~4.5 A, drawing ~10 A peak from the battery (BAT-44). This is a search snippet only and is not a laser driver.
- **Action:** the owner or the converter agent should supply product links. The vendor pages and LaserPointerForums threads should then be captured as claims.

**Engineering cautions for any boost laser driver.** These come from topology analysis, not product reports.

1. **"Glow when off" / bleed-through.** A disabled boost converter does not disconnect input from output. Current can still flow battery → inductor → rectifier, or the synchronous FET's body diode, → output. That puts V_out ≈ V_bat − V_diode, about 3.2 to 4.0 V, on the LD.
   - With an e-switch, or any always-powered design, the LD can glow or leak current while "off".
   - **A true output/load disconnect, or an input cut-off switch, is required.** Flag this to the converter agent.
2. **Hot-plug / start-up overshoot.** The output capacitor is charged to open-circuit voltage when no load is attached. Never connect the LD to a powered driver.
   - Soft-start and an output-voltage clamp are needed.
   - Test on a dummy load (diode string plus sense resistor) first.

---

## 8. Mode-switching methods

> References for this section were **not fetched this session**. The description is standard practice; verify against ToyKeeper's firmware repository (`https://github.com/ToyKeeper/anduril`, formerly Launchpad "flashlight-firmware") before citing. Both links are UNVERIFIED.

**Clicky (power-cycle) mode change.** The tail clicky removes all power. On each boot the MCU decides whether the preceding off-period was **short**, meaning "advance mode", or **long**, meaning "reset / remember mode". Three methods are common:

1. **Off-time capacitor (OTC).** A small capacitor on an MCU pin is charged while on. It discharges through leakage or a resistor while off. At boot the ADC reads its voltage: high means a short tap.
   - Needs one ADC pin and a capacitor.
   - The threshold drifts with temperature and leakage.
2. **RAM decay ("noinit" variable).** A flag lives in an uninitialised SRAM section. The MCU's VCC is held up briefly by a diode-isolated capacitor.
   - After a short off-time the RAM pattern survives; after a long one it decays.
   - This needs no extra pin, but the timing depends on the hold-up capacitor, MCU leakage and temperature.
3. **On-time EEPROM memory.** A "pending" flag is written at power-up and cleared after N ms of on-time. A quick off/on then reads the flag and advances.
   - This needs EEPROM wear-levelling.
   - It measures on-time rather than off-time.

**Requirements specific to a laser driver:**

- The output must default to **off/safe** during MCU start-up, brown-out and reset.
- The converter enable pin must be pulled to the off state by hardware.
- Mode advance must never pass through a higher current transiently.
- Regulatory features (key switch, emission delay) belong to the safety/compliance review and are out of scope here.

**E-switch requirements:**

- **The MCU must be permanently powered.** The tail must not break the circuit, i.e. there is no clicky. If a clicky remains, an e-switch adds nothing.
- **Switch hardware.** A switch input pin with a pull-up connects to a pad that the switch shorts to GND, which is the ring/host body. This is usually a side-switch board wired to a driver pad.
- **Standby budget at µA level:**
  - MCU sleep current.
  - A switched battery-voltage divider.
  - Converter EN-off current.
  - Leakage.

  For example, 20 µA drains a 3 Ah cell in about 17 years. 1 mA drains it in about 4 months.
- **Laser-specific requirement:** a true load disconnect (§7 item 1), so the LD cannot glow in standby.
- **Mechanical needs:** a pad and wire route for the switch on the pill side, and optionally an indicator LED.

---

## 9. Open questions / UNKNOWNs

1. **Owner's host polarity and topology** (§5.4): spring polarity (decided by the board labels, DD-12), which path the tail switch breaks, body isolation, and LD case-to-pin connection (NUBM44 case polarity UNKNOWN). These must be measured.
2. **Host mechanical drawing.** Pill bore (exactly 22.0 mm?), shoulder depth, retaining-ring thread, ring ID/OD, maximum battery-side component height, spring free/compressed height, and cell type (flat or button) are all UNKNOWN.
3. **Real R_path.** Springs, tail switch and threads are assumed at 20 to 60 mΩ; measure with a 4-wire method at ≥ 5 A.
4. **Mooch ratings not retrieved:**
   - The current 21700 table, which moved to Patreon post 137974946 (HTTP 403).
   - P45B and P42A values after 2020.
   - Any 14500/16340 ratings (probably none exist).
   - The 18650 data are from the 2022-07-01 table. Mooch notes ratings can change and that table says "Do not share after September 1, 2022", so newer lots may differ.
5. **Datasheets not retrieved:** Molicel P26A, Murata VTC6A, the official Samsung 30Q v1.x (only tentative v0.0 local), LG HG2 Rev5, Vapcell OEM spec sheets, and the Panasonic NCR18500A rating.
6. **IUPAC Gold Book cathode entry:** verbatim text not retrieved (BAT-39).
7. **Existing NUBM44 20 to 22 mm boost drivers:** no data (§7).
8. **Driver mechanics norms** (PCB thickness, ring width, spring part numbers): not sourced this session.
9. **Thermal interaction:** laser head heat into the cell, and whether an NTC near the cell or spring is warranted. Recommend one on the driver's battery side; coordinate with the thermal/laser report.
