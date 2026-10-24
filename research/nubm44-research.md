# Nichia NUBM44 (445–450 nm multimode blue laser diode): research report

Prepared 2026-10-24 by the laser-diode research specialist for the NUBM44 driver project: single-cell Li-ion boost-type constant-current driver, up to 4 A, 22 mm round PCB.
Sources are indexed in [`research/sources/nubm44-sources.md`](sources/nubm44-sources.md) and cited here as LD-xx. Local PDFs are in `research/datasheets/nubm44_*`.

**Provenance tags**

| Tag | Meaning |
|---|---|
| **PRIMARY** | Nichia document, regulation or standard. "PRIMARY (relative)" means a Nichia document for a sister part in the same φ9.0 mm package family, not for the NUBM44 itself. |
| **SECONDARY** | Vendor, module-maker or community measurement or statement. |
| **INFERRED** | Derived in this report by calculation or reasoning from the cited data. Engineering recommendations are also tagged INFERRED. |

## Headline findings

1. **There is no public Nichia specification for the NUBM44.**
   - Nichia never sold it individually. It is harvested from Nichia projector LD banks, and the forum consensus is that no official datasheet exists (LD-15, LD-18, LD-08).
   - The best spec-style table found is a module maker's datasheet (LD-05, Aug 2022). Its values match Nichia's published sister parts (LD-01 to LD-04).
2. **4 A is above the manufacturer-style rating.**
   - The typical operating current is 3.0 A (LD-05, LD-06). LD-05 gives a maximum operating current of 4.2 A, and an absolute-maximum optical output of 6.0 W at Tcase 25 °C.
   - At 4 A, measured units emit 5.6–6.6 W, so most reach or exceed that 6.0 W limit.
   - Nichia sister parts in the same package have absolute-maximum forward currents of only 3.0–4.0 A.
   - Treat 4 A as a deliberate overdrive ("turbo") level with an unquantified lifetime penalty.
3. **The case/stem is most likely electrically isolated (floating) from both anode and cathode.** Confidence is MEDIUM-HIGH. It is not documented by Nichia for this exact part, so verify on every unit (§3).
4. **Vf at 4 A measured 4.26–4.62 V** across 4 community datasets. Size the driver's compliance for 3.8–5.2 V at the diode pins, plus wiring drop (§4).
5. **Driver-critical hazard: plain-boost pass-through.**
   - A non-switching boost passes the cell voltage through the inductor and rectifier.
   - A full cell (4.2 V) therefore puts about 3.4–4.2 V across the diode. Community data show that is near threshold up to more than 3 A, i.e. Class 4 emission while "off".
   - A true load disconnect, and a way to regulate when VIN > Vf, are mandatory (§6.4).

---

## 1. Summary of key design values

| Parameter | Value | Conditions | Provenance | Source ID |
|---|---|---|---|---|
| Package | Nichia φ9.0 mm can, called "TO-5 9 mm" by hobbyists. Two leads Φ0.6 mm, 6.5 mm long, on a Φ2.54 mm circle, offset 1.0 mm from the flange centre line. Flange has two 90° V-notches and one 1.0 × 0.4 mm rectangular key notch. | Family drawing | PRIMARY (relative) + SECONDARY (APS NUBM47 drawing has the same layout) | LD-01 p.2, LD-03, LD-08 p.1/p.6, LD-07 |
| Lead count / photodiode | 2 leads, **no monitor photodiode** | – | PRIMARY (relative) + SECONDARY | LD-03 ("does not have Photo Diode"), LD-08 p.6 |
| Pin assignment | **Pin 1 = LD anode (+), pin 2 = LD cathode (−)** | Nichia numbering | PRIMARY (relative) + SECONDARY | LD-01, LD-02, LD-03, LD-04 p.12, LD-08 |
| Physical pin identification | Look at the lead side (back) with the small rectangular notch at 6 o'clock, so both pins sit above centre. **Right pin = anode (+), left pin = cathode (−).** | – | PRIMARY (relative, drawing interpretation) + SECONDARY | LD-03, LD-01, LD-08, LD-16 |
| Case/stem connection | **Isolated from both pins (floating).** Verify per unit. | – | INFERRED from PRIMARY (relative) + SECONDARY | LD-01–LD-04, LD-29, LD-15, LD-17 |
| Internal ESD Zener (antiparallel) | Probably present (Nichia family design); APS says none. **Unresolved.** | – | INFERRED / conflicting SECONDARY | LD-04, LD-05, LD-28 vs LD-08 |
| Typical operating current | 3.0 A | CW | SECONDARY | LD-05, LD-06 |
| Maximum operating current | 4.2 A | CW | SECONDARY (single source) | LD-05 |
| Absolute-maximum forward current | **UNKNOWN for NUBM44.** Sister parts: 3.0 A (NDB7K75), 3.5 A (NDB7Y75 and NUBM08 LDs), 4.0 A (NDB7Z75). | Tc or Tm 25 °C, or 0–30 °C | PRIMARY (relative only) | LD-03, LD-01, LD-04, LD-02 |
| Absolute-maximum optical output | 6000 mW | Tcase 25 °C | SECONDARY | LD-05 |
| Optical output (spec) | 5.0 W typ | If = 3.0 A | SECONDARY | LD-05 |
| Optical output (nameplate) | "6 W" (LD-06: "6 W @ 20 °C", current not stated) | – | SECONDARY (marketing) | LD-06, LD-07 |
| Measured optical output | 4.4–5.3 W at 3.0 A; **5.6–6.6 W at 4.0 A**; 6.2–7.8 W at 5 A. On good heatsinks output rolls over at about 5.6–5.9 A (about 7.1–7.6 W); with weaker cooling it is already flat near 6.2 W at about 4.9 A. | Community bench tests, 20–25 °C, various heatsinks | SECONDARY | LD-11, LD-12, LD-13, LD-14 |
| Threshold current | 250–450 mA (spec). Measured onset about 0.35–0.40 A. Reseller list says 150–350 mA (conflict). | CW, about 25 °C | SECONDARY | LD-05; LD-11, LD-12, LD-14; LD-06 |
| Slope efficiency | 1.8 W/A typ (spec). Measured about 1.7–2.1 W/A between 1 and 2 A, falling above about 4 A (thermal roll-over). | CW | SECONDARY / INFERRED (computed) | LD-05; LD-11, LD-12, LD-14 |
| Operating voltage at 3.0 A | 3.6–4.8 V (min/max). Measured 4.08–4.46 V. | If = 3.0 A | SECONDARY | LD-05; LD-12, LD-13, LD-14 |
| Operating voltage (reseller) | 3.6–5.2 V | Conditions not stated | SECONDARY | LD-06 |
| **Vf at 4.0 A** | **4.26–4.62 V measured.** Design range 3.8–5.2 V at the diode pins. | 20–25 °C. Cold adds about +0.1 V at 0 °C. | SECONDARY (measured); INFERRED (range) | LD-12, LD-13, LD-14 |
| Vf at very low current | 3.13 V at 0.01 A; 3.4 V at about 0.4 A (threshold) | 20 °C | SECONDARY | LD-13, LD-14 |
| Dynamic resistance dV/dI | About 0.15–0.25 Ω | 2–5 A | INFERRED | From LD-12, LD-13, LD-14 |
| Reverse voltage rating | **UNKNOWN (not specified).** "Allowable reverse current 85 mA" is given instead. | Tcase 25 °C | SECONDARY (NUBM44); PRIMARY (relatives give the same 85 mA) | LD-05; LD-01–LD-04 |
| ESD (HBM) rating | **UNKNOWN** (not published). Nichia only states the parts are sensitive to ESD and surges. | – | PRIMARY (relative, qualitative) | LD-01 §(7), LD-04 p.6 |
| Dominant wavelength | 438 / 445 / 455 nm (min / typ / max) | If = 3.0 A | SECONDARY | LD-05 |
| Measured spectrum | Peak 446 nm, about 1.5 nm FWHM (NUBM47 "V2") | 7 W output | SECONDARY | LD-08 |
| Wavelength temperature coefficient | About +0.07 nm/K | If = 3.0 A, NUBM08 relative | INFERRED from PRIMARY (relative) chart | LD-04 p.4 |
| Case temperature, operating | 0 to +65 °C (LD-05, LD-07). LD-06's list says 0 to +60 °C (conflict). | Measured at the diode backplate (LD-05) | SECONDARY | LD-05, LD-06, LD-07 |
| Storage temperature | −40 to +85 °C | – | SECONDARY (identical to PRIMARY relatives) | LD-05, LD-06; LD-01 |
| Thermal resistance | **UNKNOWN** (not published). Vendors recommend a mount below 1.5 °C/W. | – | SECONDARY | LD-06, LD-07 |
| Heat to remove at 4 A | About 10.4–12.3 W from measured data; plan for about 15 W worst case. | Electrical in minus optical out | INFERRED | From LD-12, LD-13, LD-14 |
| Vf temperature coefficient | About −3.8 mV/K per diode | 3.0 A, NUBM08 relative | INFERRED from PRIMARY (relative) chart | LD-04 p.4 |
| Optical output temperature coefficient | About −0.45 %/K of the 25 °C value | 3.0 A, NUBM08 relative | INFERRED from PRIMARY (relative) chart | LD-04 p.4 |
| Threshold vs temperature | 350 mA at 20 °C rising to 585 mA at 70 °C (T0 ≈ 97 K) | NUBM08 LD | PRIMARY (relative, read from chart) / INFERRED (T0) | LD-04 p.4 |
| Lifetime | Vendor claim: "typ 20,000 h at 25 °C". NUBM08 bank spec: B50 ≥ 10,000 h (20,000 h reference) and B1 ≥ 1,000 h at Tm 70 °C, 3.0 A ACC, end of life at Po × 0.5. **No data at 4 A.** | – | SECONDARY / PRIMARY (relative) | LD-06, LD-07, LD-13; LD-04 p.1 |
| Laser class | **Class 4** (IEC 60825-1, 21 CFR 1040.10) | ≥ 0.5 W CW visible | PRIMARY | LD-01, LD-03, LD-04, LD-23, LD-26 |

---

## 2. Variants and identification

**What "NUBM44" means.** NUBM44 and NUBM47 are Nichia **LD-bank (array) designations** for blue projector light-source assemblies, not the part number of the individual TO-can. The individual can's Nichia part number is not public.

- LD-14: the part number is "unknown"; the name comes from the label on the array.
- LD-08: the arrays are sold under an exclusive agreement with a projector maker, so the diodes have to be de-soldered from the banks.
- LD-15: "Nichia doesn't even acknowledge this diodes existence because it was never intended to be sold individually."

Diodes reach the market as pulled units, often with tinned pins and "not guaranteed zero hours" (LD-20).

| Community name | Label codes seen | Bank size | Nominal power | Notes | Sources |
|---|---|---|---|---|---|
| NUBM44 "V1" (6 W) | NUBM44-71, NUBM47T | 8-diode bank (LD-14, LD-08). DTR: the "44" bank has 8 and the "47" bank has 10. | 6 W | Out of production for "several years" (LD-08) or "a few years" (LD-20) | LD-08, LD-14, LD-19, LD-20 |
| NUBM44 "V2" (7 W) | NUBM44-81, NUBM47-A1 | 10-diode bank (LD-14, LD-08). DTR says both the 8- and 10-diode blocks carry the V2 diode. | 7 W | About 10 % more efficient than V1 (DTR estimate, via LD-14) and lower threshold (LD-08). DTR measured 7.5 W at 4.5 A (via LD-27). | LD-08, LD-14, LD-20, LD-27 |

**Conflicts.**
- The 44/47, V1/V2 and 8/10-bank mapping is reported inconsistently (LD-14, LD-20 and LD-08 disagree in detail).
- Opt Lasers and LaserDiodeSource say the "NUBM44" has a *lower* threshold and *higher* efficiency than the "NUBM47" (LD-06, LD-07). APS says the opposite (LD-08).
- My view: these are batch and bin labels used loosely by sellers. For the driver they do not matter. All variants share the package, the pinout and a similar Vf, so set the driver by current, not by label.

**APS typical-values table, disregarded.** LD-08 p.1 lists "7 W at 3.7 A / 3.8 V, 14.44 W input, 48.5 % efficiency". That is internally inconsistent (3.8 V × 3.8 A = 14.44 W, not 3.7 A) and contradicted by every measured dataset, including APS's own 4.592 V at 5.8 A (LD-11).

**Close relatives often confused with the NUBM44.** Listed only to avoid confusion.

| Part | What it is | Key data | Source / provenance |
|---|---|---|---|
| NUBM08 | Nichia 8-LD **bank**, 455 nm | Per LD: (4.35) W at 3.0 A, λd 448–462 nm, Ith 280–480 mA, Vop 3.6–4.8 V at 3.0 A, If absolute max 3.5 A, Ir 85 mA, Zener per LD | LD-04, PRIMARY |
| NDB7K75 (sold by DTR as "NDB7A75") | Single φ9.0 mm diode, 448 nm | 3.5 W at 2.3 A, If max 3.0 A, Tc 0–60 °C, Zener, no PD | LD-03, PRIMARY |
| NDB7Y75 | Single φ9.0 mm diode, 455 nm. Closest current catalog analog of the NUBM44. | 5.0 W at 3.0 A, If max 3.5 A, Tc 0–30 °C, Vf 3.7/(4.0)/4.4 V at 3.0 A, Zener | LD-01, PRIMARY |
| NDB7Z75 | Single φ9.0 mm diode, 465 nm | 5.0 W at 3.5 A, If max 4.0 A, Tc 0–30 °C | LD-02, PRIMARY |
| NUBM07E | Reseller listings only ("465 nm 3 W 9 mm") | **UNVERIFIED.** No Nichia document found. | Search results only |
| NUBM48 | – | **UNKNOWN.** No information found. | – |
| "Brand new" / re-capped 445 nm 9 mm diodes (e.g. Z80 Lasers "brand new") | Not verifiably Nichia NUBM44 | Provenance unknown. Treat separately. | LD-13, LD-12 context |

---

## 3. Pinout and case connection (critical)

### 3.1 Package

- Nichia φ9.0 mm can (Φ9 −0.03 mm flange, 1.5 mm thick).
- Cap Φ7.3 mm with a 0.25 mm glass window. The emitting point is at the centre, about 1.9 mm above the reference plane.
- Two leads Φ0.6 ± 0.05 mm, 6.5 ± 0.5 mm long, on a Φ2.54 mm circle. The lead axis is offset 1.0 ± 0.1 mm from the flange centre line, away from the rectangular key notch.
- Flange has two 90° V-notches on the horizontal axis and a 1.0 × 0.4 mm rectangular notch on the vertical axis.
- Sources: LD-01 p.2 and LD-03 p.1 (Nichia φ9.0 mm floating-mount family, PRIMARY relative). The APS NUBM47 drawing shows the same layout (LD-08). Opt Lasers says the NUBM44 pins are "shifted by 1 mm" (LD-07).
- APS dimensions the leads as Ø0.45 mm. Nichia's family drawing says Φ0.6. Measure the leads if footprint accuracy matters.
- LD-07 calls the can a "custom TO-5 (9 mm) … with an integrated larger heat spreader".

### 3.2 Pin assignment and physical identification

- **Pin 1 = LD anode, pin 2 = LD cathode.** This is Nichia's numbering in every family document found: NDB7Y75, NDB7Z75, NDB7K75, and the NUxMxx bank outline that covers NUBM-series banks (LD-01, LD-02, LD-03, LD-04 p.12). APS labels the NUBM47/44 pins "1 (+)" and "2 (−)" (LD-08).
- **Physical identification.** Look at the lead (back) side and rotate the diode until the rectangular key notch is at 6 o'clock, so the two pins are above centre. **Right pin = anode (+), left pin = cathode (−).** Four independent depictions agree:
  - (a) LD-03 bottom view, placed below the side view in third-angle projection: notch at 12 o'clock, pins below centre, pin 1 on the left. Rotating it 180° gives the statement above.
  - (b) LD-01 pin view: notch at 6 o'clock, pins above centre, pin 1 on the right. This is the same view as (a) rotated 180°.
  - (c) LD-08 APS first-angle pin view, labelled (+) and (−): rotated to put the notch at 6 o'clock, the (+) pin is on the right.
  - (d) LD-16 (RedCowboy, 2023): "pins are both on the upper half of the back … right pin is positive … left pin is negative".
- **Disregard Lone Oceans' "pin 1 = cathode" drawing** (LD-14). The page says it is a generic TO-5 drawing, not a Nichia or NUBM44 document.
- **Confidence: MEDIUM-HIGH.** There is no NUBM44-specific Nichia drawing; the conclusion rests on consistent family drawings plus community corroboration. Always verify polarity electrically (§3.5).

### 3.3 Case/stem electrical connection: evidence

| # | Evidence | Type | What it supports |
|---|---|---|---|
| 1 | Nichia φ9.0 mm sister parts are explicitly "**φ9.0 mm Floating Mounted** with Zener Diode". Each drive circuit has only two terminals (1 anode, 2 cathode) and no stem connection. | PRIMARY (relative): LD-01, LD-02, LD-03 | LD electrically isolated from the stem |
| 2 | Nichia NDB4916 ("φ5.6 Floating Mounted with Photo Diode and Zener Diode"): the only stem connection is explicitly labelled "3. PD Cathode **(Flange)**"; the LD anode and cathode are separate pins. Nichia labels any flange connection, and "floating" refers to the LD. | PRIMARY (relative, terminology): LD-29 | Meaning of "floating"; no unlabelled case tie in the 9 mm parts |
| 3 | The Nichia NUBM08 bank (outline drawing covers "NUxMxxE / NUxMxx" banks) presses 8 LDs into one **Ni/Au-plated aluminium LD plate**, yet specifies Vop "when connected in series with the 8 LDs" (29–38 V). Series wiring through a shared conductive plate only works if every stem is isolated from its LD. NUBM44 diodes come from the same kind of 8- and 10-LD projector banks (LD-08, LD-19, LD-20). | INFERRED from PRIMARY (relative): LD-04 p.1, p.11–12 | Stem isolated from both electrodes |
| 4 | Z80 Lasers (NUBM44/47 vendor), 2025-03-10: "Neither. Both pins are isolated." 2025-03-11: case-negative or case-positive hosts both work. | SECONDARY: LD-15 | Case isolated on NUBM44/47 |
| 5 | DTR, 2018: "Ignore the case pin on the NUB/NUG diodes and use the notches to orientate." That means there is no case lead, unlike 3-pin generic diagrams. | SECONDARY: LD-17 | Consistent with (1)–(4) |
| 6 | Counter-evidence: **none found.** A search-engine summary pointed to a Wavelength Electronics FAQ about an anode-to-case diode. It was checked: a generic user question, not Nichia (LD-30). | – | – |

**Conclusion.** The NUBM44 stem (case/flange) is electrically **isolated from both the anode and the cathode**. **Confidence: MEDIUM-HIGH.** It is strongly supported by Nichia family documents, bank architecture and vendor statements, but Nichia has published no NUBM44-specific drawing.

### 3.4 Consequences for low-side current sensing with a grounded host

- With an isolated case, pressing the diode into a metal module or host body tied to battery negative does **not** by itself connect LD− to ground. The case alone will not bypass a low-side sense resistor. INFERRED.
- Residual paths that **would** bypass a low-side sense resistor. INFERRED, typical build failure modes:
  - LD leads or solder joints touching a brass, copper or aluminium module bore or the host.
  - Chipped lead-sealing glass.
  - Pre-wired third-party modules deliberately made "case-negative" (LD-15 shows vendors treat either convention as acceptable).
  - Unit-to-unit uncertainty, because Nichia does not document this part.
- Required practice. RECOMMENDATION (INFERRED):
  - (a) 100 % incoming check of every diode, and again after pressing into its module: case-to-pin-1 and case-to-pin-2 must read open on a DMM ohms range. Use ESD precautions.
  - (b) Never bond LD− to the host or module body anywhere in the harness.
  - (c) Prefer a current-sense arrangement that a host short **cannot** bypass, or insulate the module from the host.
  - (d) Add a start-up or periodic plausibility check: the sensed current must track the commanded ramp, otherwise shut down.
- ILX makes the same point for case-tied lasers: with an earth-referenced electrode, "no other node … should be connected to earth (otherwise you may short your diode, or worse, short a current-sensing element)" (LD-21 p.12).

### 3.5 Polarity and health check before first power-up

INFERRED from the Nichia drive-circuit diagrams (LD-01, LD-03) and the low-current data in LD-13.

1. **DMM diode test, if the internal Zener is present.** Red on pin 2 (cathode) and black on pin 1 (anode) forward-biases the Zener and should read a silicon drop (about 0.5–0.8 V). The opposite direction should read OL (or a high value), because the GaN LD needs about 3.1 V even at 10 mA (LD-13).
2. **If both directions read OL**, the unit may lack the Zener (APS claims NUBM44/47 have none, LD-08). Confirm polarity with a current-limited source (≤ 10 mA, compliance ≤ 3.5 V): forward conduction at about 3.0–3.2 V with faint blue LED-like glow marks pin 1 as the anode. Wear eyewear anyway.

---

## 4. Electrical characteristics

### 4.1 Spec-style values for the NUBM44 vs Nichia sister parts

| Parameter | NUBM44 (LD-05, SECONDARY) | NDB7Y75 455 nm (LD-01) | NDB7Z75 465 nm (LD-02) | NDB7K75 448 nm (LD-03) | NUBM08 bank, per LD (LD-04) |
|---|---|---|---|---|---|
| Absolute-max forward current | not given (Iop max 4.2 A) | 3.5 A (Tc 0–30 °C); max rating 3.0 A (derating figure) | 4.0 A | 3.0 A (Tc 25 °C) | 3.5 A (Tm 25 °C) |
| Absolute-max optical power | 6.0 W (Tcase 25 °C) | – | – | – | – |
| Allowable reverse current | 85 mA | 85 mA | 85 mA | 85 mA | 85 mA |
| Operating case temperature | 0 to +65 °C | 0–30 °C (20–30 °C recommended) | 0–30 °C | 0–60 °C | 0–70 °C (Tm) |
| Optical output | 5.0 W typ at 3.0 A | 4.5 min (5.0) W at 3.0 A | 4.5 min (5.0) W at 3.5 A | 3.4 / 3.5 / 3.6 W at 2.3 A | (4.35) W at 3.0 A |
| Dominant wavelength | 438 / 445 / 455 nm | 448 / (455) / 462 nm | 462 / (465) / 472 nm | 440 / 448 / 455 nm | 448 / (455) / 462 nm |
| Threshold | 250–450 mA | 250 / (320) / 420 mA | 300 / (400) / 500 mA | 200 / 270 / 350 mA | 280–480 mA |
| Slope efficiency | 1.8 W/A typ | 1.6 / (1.8) / 2.1 W/A | 1.4 / (1.7) / 2.0 W/A | 1.5 / 1.7 / 2.0 W/A | (1.7) W/A |
| Vop / Vf at the rated current | 3.6–4.8 V at 3.0 A | 3.7 / (4.0) / 4.4 V at 3.0 A | 3.8 / (4.1) / 4.5 V at 3.5 A | 4.0 / 4.3 / 4.7 V at 2.3 A | 3.6–4.8 V at 3.0 A |
| Divergence ∥ / ⊥ | 5/10/25° and 35/46/55° (FWHM) | 8/10.5/14° and 40/46/52° (1/e²) | same as NDB7Y75 | 10/14/20° and 40/46/50° (1/e²) | collimated by the bank lens |
| Photodiode / Zener | none (LD-08) / disputed | none / yes | none / yes | none / yes | – / yes |

Values in parentheses are Nichia "reference" figures.

LD-05's 3.6–4.8 V at 3.0 A range, its 85 mA allowable reverse current and its −40/+85 °C storage range are identical to the Nichia NUBM08 per-LD values. That suggests LD-05 was transcribed from a Nichia NUBM-series bank document. INFERRED.

### 4.2 Measured V/I/optical data (SECONDARY, community measurements)

- Measurements are not traceable to Nichia. None of the sources state whether voltage was measured at the diode pins (4-wire) or at the driver terminals.
- "Read from chart" values were extracted from published chart images by pixel analysis. Reading error is about ±0.03 V and ±50–100 mW.
- Target currents with no measured point are shown as "–". The nearest actual point is given; nothing is interpolated.

**Dataset key.**

| ID | Diode and source | Conditions |
|---|---|---|
| M1 | DTR, NUBM44-V1 (LD-14 chart "Data by DTR, compiled 12/2018"). Read from chart. | Voltage logged at 0.1 V resolution; power measured through a G2 lens (so slightly low) |
| M2 | Endurance unit "A", NUBM44/47 (LD-12, table 1) | Tabulated |
| M3 | Endurance unit "B", NUBM44/47 (LD-12, table 2) | Tabulated |
| M4 | Endurance "updated laser diodes datasheet (since December 2021)" (LD-13). **Diode model not stated** on the page (appears in the NUBM44/47 section). | Diode temperature 20 °C (21–22 °C above 5.4 A) |
| M5 | APS, "6 W-rated" Nichia blue diode (LD-11 p.5, same series as LD-10 "LowThermalImpedanceHeatsink-052419"). Read from chart. | Gentec calorimeter, sustained CW, air-cooled low-thermal-impedance heatsink. **No voltages** except as noted. |

| Target I | Dataset | Actual I (A) | Vf (V) | Popt (W) | Tag / source |
|---|---|---|---|---|---|
| 0.5 A | M1 | 0.50 | 3.5 | 0.23 | SECONDARY, read from chart, LD-14 |
| 0.5 A | M2 | 0.50 | 3.42 | 0.30 | SECONDARY, LD-12 |
| 0.5 A | M3 | 0.38 / 0.70 | 3.39 / 3.54 | 0.04 / 0.57 | SECONDARY, LD-12 |
| 0.5 A | M4 | 0.52 | 3.69 | 0.42 | SECONDARY, LD-13 |
| 0.5 A | M5 | 0.4 / 0.6 | – | 0.06 / 0.42 | SECONDARY, read from chart, LD-11 |
| 1 A | M1 | 1.00 | 3.7 | 1.23 | SECONDARY, read from chart, LD-14 |
| 1 A | M2 | 1.02 | 3.62 | 1.41 | SECONDARY, LD-12 |
| 1 A | M3 | 1.01 | 3.65 | 1.10 | SECONDARY, LD-12 |
| 1 A | M4 | 1.00 | 3.93 | 1.32 | SECONDARY, LD-13 |
| 1 A | M5 | 1.0 | – | 1.14 | SECONDARY, read from chart, LD-11 |
| 2 A | M1 | 2.00 | 4.1 | 3.14 | SECONDARY, read from chart, LD-14 |
| 2 A | M2 | 2.04 | 3.90 | 3.52 | SECONDARY, LD-12 |
| 2 A | M3 | 2.16 | 3.95 | 3.07 | SECONDARY, LD-12 |
| 2 A | M4 | 2.00 | 4.25 | 3.16 | SECONDARY, LD-13 |
| 2 A | M5 | 2.0 | – | 2.88 | SECONDARY, read from chart, LD-11 |
| 3 A | M1 | 2.90 (no 3.0 A point) | 4.3 | 4.72 | SECONDARY, read from chart, LD-14 |
| 3 A | M2 | 3.05 | 4.10 | 5.32 | SECONDARY, LD-12 |
| 3 A | M3 | 3.01 | 4.12 | 4.40 | SECONDARY, LD-12 |
| 3 A | M4 | 3.00 | 4.46 | 4.88 | SECONDARY, LD-13 |
| 3 A | M5 | 3.0 | – | 4.46 | SECONDARY, read from chart, LD-11 |
| 3.5 A | M1 | 3.50 | 4.5 | 5.60 | SECONDARY, read from chart, LD-14 |
| 3.5 A | M2 | 3.50 | 4.18 | 5.93 | SECONDARY, LD-12 |
| 3.5 A | M3 | 3.47 | 4.20 | 5.01 | SECONDARY, LD-12 |
| 3.5 A | M4 | 3.52 | 4.55 | 5.62 | SECONDARY, LD-13 |
| 3.5 A | M5 | 3.4 / 3.6 | – | 5.05 / 5.32 | SECONDARY, read from chart, LD-11 |
| **4 A** | M1 | 4.00 | **4.6** | 6.25 | SECONDARY, read from chart, LD-14 |
| **4 A** | M2 | 3.99 | **4.26** | 6.61 | SECONDARY, LD-12 |
| **4 A** | M3 | 3.98 | **4.28** | 5.60 | SECONDARY, LD-12 |
| **4 A** | M4 | 4.00 | **4.62** | 6.23 | SECONDARY, LD-13 |
| **4 A** | M5 | 4.0 | – | 5.83 | SECONDARY, read from chart, LD-11 |
| 4.5 A | M1 | 4.50 | 4.7 | 6.84 | SECONDARY, read from chart, LD-14 |
| 4.5 A | M2 | 4.45 | 4.34 | 7.14 | SECONDARY, LD-12 |
| 4.5 A | M3 | 4.45 | 4.35 | 5.98 | SECONDARY, LD-12 |
| 4.5 A | M4 | 4.49 | 4.69 | 6.81 | SECONDARY, LD-13 |
| 4.5 A | M5 | 4.4 / 4.6 | – | 6.31 / 6.50 | SECONDARY, read from chart, LD-11 |
| 5 A | M1 | – (chart ends at 4.5 A) | – | – | – |
| 5 A | M2 | 5.02 | 4.43 | 7.76 | SECONDARY, LD-12 |
| 5 A | M3 | 5.04 | 4.43 | 6.18 (flat from 4.9 A) | SECONDARY, LD-12 |
| 5 A | M4 | 5.00 | 4.77 | 7.28 | SECONDARY, LD-13 |
| 5 A | M5 | 5.0 | – | 6.80 | SECONDARY, read from chart, LD-11 |
| >5 A | M4 | 5.71 / 5.92 | 4.87 / 4.90 | 7.57 / 7.57 (roll-over) | SECONDARY, LD-13 |
| >5 A | M5 / APS | 5.8 | 4.592 (LDC4020 display, LD-11 p.2) | 7.11 | SECONDARY, LD-11 |

**Single operating points from other sources.**

| Point | Detail | Tag / source |
|---|---|---|
| DTR | 6 W at 3.5 A × 4.53 V; 7 W at 4.7 A × 4.77 V (quoted by Endurance) | SECONDARY, LD-13 |
| APS | 6 W at 4.7 A × 4.70 V. Also "7 W at 5.8 A × 5.9 V = 26.62 W": the product implies **4.59 V**, matching LD-11's 4.592 V, so "5.9 V" is a typo. | SECONDARY, LD-13, LD-11 |
| Lone Oceans | 0.4 A / 3.4 V / <0.1 W; 0.6 A / 3.6 V / 0.5 W; 1.35 A / 3.9 V / 2.0 W; 4.5 A / 4.7 V / 7.0 W. The 7.0 W assumes V2 is 10 % better than V1. | SECONDARY, LD-14 |
| DTR (V1, 2015) | 6.8 W at 4.5 A (meter maximum); about 2 min at 5.5 A with the meter pegged | SECONDARY, LD-19 |
| DTR (V2) | 7.5 W at 4.5 A (reported by Laserbran, LD-27) | SECONDARY, LD-27 |
| A. Barnett (V2) | 10.39 W at 5.4 A / 5 V "after freezing the diode" | SECONDARY, LD-14 |

**At 4.0 A** (INFERRED from the table above):

| Dataset | Vf (V) | Popt (W) | Pin = V × I (W) | Heat = Pin − Popt (W) | Electrical-to-optical efficiency |
|---|---|---|---|---|---|
| M1 | 4.6 | 6.25 | 18.4 | 12.2 | 34 % |
| M2 | 4.26 | 6.61 | 17.0 | 10.4 | 39 % |
| M3 | 4.28 | 5.60 | 17.0 | 11.4 | 33 % |
| M4 | 4.62 | 6.23 | 18.5 | 12.3 | 34 % |

### 4.3 Interpretation for the driver

All points in this section are INFERRED unless a source tag is given.

- **Vf at 4 A spread: 4.26–4.62 V** across 4 datasets. Part of the spread is probably the unknown measurement point (pins vs driver terminals).
- **Worst-case Vf at 4 A.** LD-05's 4.8 V maximum at 3.0 A, plus the 3 A → 4 A increment measured in M2–M4 (+0.16 V) and M1 (+0.3 V), gives about **5.0–5.1 V at 25 °C**. At 0 °C add about +0.1 V (−3.8 mV/K × −25 K), giving **about 5.2 V**.
- **Low-Vf units.** The spec minimum is 3.6 V at 3.0 A, so expect about 3.8 V at 4 A.
- **Compliance recommendation.** About 5.5 V at 4 A at the LD connection, plus wiring and contact drop.
- **Low-current Vf.** About 3.1 V at 10 mA and 3.4–3.5 V near threshold (0.4–0.5 A). This matters for pass-through (§6.4).
- **Dynamic resistance.** About 0.15–0.16 Ω (M2–M4, 3–5 A) to 0.25 Ω (M1, 2–4 A). A 0.1 V error in output voltage is about 0.4–0.7 A of current error, so only current regulation is acceptable.
- **Output at 4 A is 5.6–6.6 W.** That is at or above LD-05's 6.0 W absolute-maximum optical output for most units.
- **Roll-over.** On good heatsinks output saturates at about 5.4–5.9 A (M4, M5). With weaker cooling M3 is already flat at about 6.2 W by 4.8–5.0 A.
- **Nichia sister-part curve (PRIMARY relative, LD-04 p.4, read from chart, bank voltage ÷ 8, Tm 25 °C).** Per LD: 3.46 V at 0.5 A, 3.66 V at 1.0 A, 3.83 V at 1.5 A, 3.96 V at 2.0 A, 4.09 V at 2.5 A, 4.20 V at 3.0 A. The shape is consistent with M2 and M3.

### 4.4 Does 4 A exceed the manufacturer's rating?

**Yes, on the best available evidence:**

- 4 A is 33 % above the 3.0 A typical operating current (LD-05, LD-06).
- 4 A does not exceed LD-05's 4.2 A maximum operating current, but LD-05 is not a Nichia document.
- At 4 A most units exceed LD-05's 6.0 W absolute-maximum optical output.
- Nichia's φ9.0 mm sister parts are rated 3.0–4.0 A absolute maximum (LD-01 to LD-03). The NDB7Y75 derates to a 3.0 A maximum rating over Tc 0–30 °C.

Nichia states that lifetime falls as current, optical power and temperature rise, and that absolute-maximum ratings must not be exceeded "even if … only for a short period of time" (LD-01 §(3)).

The true Nichia absolute-maximum current for the NUBM44 is **UNKNOWN**.

### 4.5 What builds actually run, and lifetime observations (SECONDARY)

- **Common hobby practice is 3.5–4.5 A.**
  - Lone Oceans "turbo" 4.2–4.6 A, with a 5.5 A design maximum (LD-14).
  - Laserbran used 4.5 A with a 60 s on / 60 s off duty (LD-27).
  - DTR ran 4.5 A and briefly 5.5 A (LD-19).
  - Endurance tested to about 5 A (LD-12).
- **APS long runs.** 30 h at about 6.9 W and 72 h at about 6.8 W with no visible decay, on a low-thermal-impedance air-cooled heatsink. The driver was set to 5.8 A and read 4.592 V (LD-11).
- **Heatsinking matters more than current.** With a 35 mm copper heatsink and no forced air, a NUBM47 set to 8 W fell to about 5.3 W over 2 h (−33.8 %). A small fan held a sustained 7.3 W (LD-08).
- **Pulse limit.** One NUBM44-V2 failed catastrophically at **17 A peak** (100 µs pulses at 100 Hz, TEC 22 °C) (LD-09).
- **No quantitative lifetime data at 3.5–4.5 A was found.** The only rated data is the relative NUBM08 bank: B50 ≥ 10,000 h at 3.0 A, Tm 70 °C (LD-04).
- ILX gives a rule of thumb of roughly an order of magnitude less lifetime per 30 °C rise in case temperature (LD-21, generic, not NUBM44-specific).

---

## 5. Thermal

**Limits.**
- NUBM44 case operating temperature 0 to +65 °C, measured at the diode backplate (LD-05). LD-07 and the LD-06 text agree; LD-06's spec list says 0 to +60 °C.
- Storage −40 to +85 °C (LD-05).
- Sister parts for context (PRIMARY relative): NDB7K75 0–60 °C (LD-03); NDB7Y75 and NDB7Z75 0–30 °C, 20–30 °C recommended (LD-01, LD-02); NUBM08 bank plate 0–70 °C (LD-04).

**Thermal resistance.** **UNKNOWN**: no junction-to-case value is published. Vendors recommend a TO-can mount below **1.5 °C/W** and quote "approximately 12 W" of heat at full power (LD-06, LD-07, SECONDARY).

**Heat at 4 A.**
- 10.4–12.3 W from measured data (§4.2, INFERRED).
- Worst case: about 5.0–5.2 V × 4 A = 20–21 W in, about 5.5 W out, so **about 15 W**.
- Design the host and heat path for 15 W, or limit run time.

**Steady-state budget (INFERRED arithmetic).** To hold the case at ≤ 60 °C in 25 °C ambient with 12 W, the total case-to-ambient thermal resistance must be ≤ (60 − 25) / 12 ≈ 2.9 °C/W. A fanless handheld relies on thermal mass, which is why community builds run 30–60 s duty cycles (LD-27).

**Temperature coefficients.** INFERRED from the Nichia NUBM08 bank curves at 3.0 A (PRIMARY relative, read from chart, LD-04 p.4).

| Quantity | Bank data (8 LDs) | Per LD / normalised |
|---|---|---|
| Vf | 34.4 V at 5 °C to 32.4 V at 70 °C | **−3.8 mV/K per LD** |
| Optical output | 38.7 W at 5 °C to 28.0 W at 70 °C | **−0.45 %/K** relative to the 25 °C value |
| Threshold | 350 mA at 20 °C to 585 mA at 70 °C | T0 ≈ 97 K |
| Wavelength | – | +0.07 nm/K |

Consequences:
- The negative Vf coefficient means constant-voltage drive runs away thermally (LD-14).
- At fixed current the cold output rises: at 0 °C and 4 A, output is about 11 % above the 25 °C value. INFERRED.
- ILX warns that at low temperature lasers can exceed safe optical power even within rated current (LD-21).

**Heat-sinking practice.**
- Press-fit copper or aluminium modules (12 mm, 20 mm, 35 mm) with thermal compound (LD-14, LD-20, LD-08, LD-27). Water and TEC cooling are used only above about 8 W (LD-08).
- Nichia rules, PRIMARY (relative), LD-01 §(4)–(5), LD-04 §6/8:
  - Do not solder the LD to the heatsink.
  - Do not stress the cap, window or lead glass.
  - Hand-solder only, 350 °C for 3 s, ≥ 2 mm from the lead base.
  - Bend each lead only once, ≤ 90°, ≥ 2 mm from the base.
  - Lead push or pull force ≤ 5 N.
- Recommendation (INFERRED): an NTC on the diode module, with derating starting around 50–55 °C and shutdown before the 65 °C rated maximum.

---

## 6. Protection and handling requirements for the driver

Each item is a design requirement (INFERRED) with its supporting source.

1. **Constant-current (ACC) drive only.**
   - Nichia: "This LD should be operated in an automatic current control (ACC) circuit" (LD-01 §(3); LD-03; LD-04).
   - With r_d ≈ 0.15–0.25 Ω, voltage drive is uncontrollable (§4.3).
   - Add an independent hardware current clamp set just above the highest setpoint (ILX, LD-21).
2. **No overshoot, ever.**
   - Turn-on and every mode change must ramp monotonically.
   - Nichia warns that too short a rise time can damage the LD "even though there seems to be no issues … with the waveform … observed with an oscilloscope" (LD-01 §(3)). Nichia also says to avoid overshoot "as the laser operation is started" (LD-03).
   - Recommendation: a soft-start of about 50–250 ms from zero. ILX says >100 ms suffices against turn-on transients (LD-21); Lone Oceans used about 200–250 ms (LD-14).
   - Peak current must never exceed the chosen hard limit, and must stay ≤ 4.2 A (LD-05) under all conditions.
3. **Power on/off, contact bounce and battery events.**
   - Nichia: spikes, chattering and inrush at power on/off must not exceed absolute-maximum current (LD-01, LD-03, LD-04).
   - Gate emission with a debounced logic enable. Never make or break the LD or battery path while the converter is running. LPF builders warn of "power up spikes" (LD-19).
   - Keep the converter disabled until VIN and the reference are settled (UVLO). Shut down cleanly at low battery rather than hiccuping.
4. **Boost pass-through (critical).** INFERRED from SECONDARY data.
   - A non-switching boost passes VIN to VOUT through the inductor and the rectifier or high-side body diode. If a "bypass" FET is on, there is no rectifier drop at all.
   - With a 4.2 V cell the diode sees about 3.4–4.2 V. Measured diodes conduct at those voltages:
     - 3.69 V: 0.52 A / 0.42 W (M4).
     - 3.70 V: 1.27 A / 1.95 W (M2).
     - 3.90 V: 2.04 A / 3.52 W (M2).
     - 4.20 V: 3.61 A / 6.1 W (M2).
   - That is **uncontrolled Class 4 emission while "off"**, and loss of regulation whenever VIN > Vf(Iset). Low modes (Vf 3.5–3.9 V) always hit this; on a full cell so can 3–3.5 A on low-Vf units.
   - Required: a **true output disconnect** that blocks in the off state (series switch, or a converter with load disconnect), and a regulation scheme valid for VIN above and below Vf (buck-boost, or boost plus a linear or series element).
   - Flag for the converter and battery agents: at 4 A into a 5.2 V worst-case diode from a 3.0 V cell at about 88 % efficiency, input current is about 7.9 A.
5. **Output capacitance, open load and re-connection.**
   - With the LD open, a CC boost rises to OVP. Re-closing an intermittent contact, or hot-plugging a diode, dumps C_out into the LD.
   - Illustration: from a 6.0 V OVP into a diode at about 4.3 V with r_d ≈ 0.16 Ω gives roughly 10 A above the operating current, limited only by ESR and wiring. APS destroyed a diode at 17 A peak (LD-09).
   - Requirements:
     - Set OVP just above the maximum expected Vf (about 5.5–6 V).
     - **Latch off** on open-load rather than retrying.
     - Never connect or disconnect the LD with the driver powered.
     - Keep the capacitance directly across the LD minimal and inside the regulation loop.
     - Avoid spring or tail-cap contacts in the LD current path.
   - Loose contacts behave as variable impedance and cause overdrive (LD-22). ILX recommends shutting the output if the control loop saturates (LD-21).
6. **Reverse voltage and current.**
   - No reverse-voltage rating exists. The allowable reverse current is **85 mA** (LD-05; Nichia relatives LD-01 to LD-04), conducted by the internal Zener if fitted.
   - Fit an **antiparallel Schottky across the LD at the driver's output pads**, cathode to LD anode. It should be rated for the converter's full fault current, with a forward drop below the Zener's silicon drop (about 0.6–0.7 V), so that reverse current bypasses the LD. If the diode has no Zener (APS claim, LD-08), the Schottky is the only reverse protection.
   - Add reverse-battery protection at the converter input.
   - Every driver must "prevent reverse bias of the diode junction" (LD-21, LD-22).
7. **Ripple and noise.**
   - Nichia gives no ripple limit (**UNKNOWN**).
   - ΔI ≈ ΔV_out / (r_d + R_sense). For example, 50 mV p-p gives about 0.2–0.3 A p-p.
   - Recommendation: ≤ 5 % p-p at 4 A, with the peak below the hard limit. The pulsating boost output needs adequate filtering.
8. **Fault tolerance.**
   - Nichia: "failure modes … can be either a short circuit or an open circuit" (LD-01, LD-03, LD-04).
   - The driver must survive both: a shorted LD means regulated current into about 0 V; an open LD triggers OVP and latch-off.
   - Add a plausibility check that the sensed current tracks the commanded current.
9. **Current sense and grounding.** See §3.4: per-unit isolation check, no LD− connection to the host, and sensing that cannot be bypassed.
10. **ESD and installation handling.**
    - Grounded wrist strap through 1 MΩ, grounded leak-free soldering iron, ionizer, RH > 40 % (LD-04 p.6).
    - **Short the LD leads together** during storage and installation until the driver is connected (LD-21, LD-22).
    - Do not connect or disconnect scope probes or meter leads while the LD is operating (LD-04).
    - Follow the soldering and bending limits in §5 (LD-01).
    - Forward-polarity transients are absorbed by the LD itself, so they must be prevented at the source: soft-start, no hot-plug, compact layout.
11. **Temperature.** NTC derating and shutdown (§5). Optionally cap the current when cold.
12. **Setting and verifying current.**
    - Use the real diode or a proper dummy load. Do not put a DMM in series: loose leads caused misreadings and overdrive risk in LPF reports (LD-19, LD-22).
    - Nichia advises monitoring optical power while adjusting current (LD-04 §4).

---

## 7. Safety and regulatory notes

**Classification.**
- Nichia classifies these diodes **Class 4** under IEC 60825-1 and 21 CFR 1040.10 (LD-01, LD-03, LD-04). The Class 3B CW AEL is 0.5 W (LD-26).
- At 5–7 W CW the product is Class 4 by a wide margin. Even the 0.4–3.5 W pass-through leak in §6.4 is Class 3B or 4.

**US: FDA 21 CFR 1040.10(f) requirements for Class IV laser systems** (LD-23, PRIMARY):

| Clause | Requirement |
|---|---|
| (f)(1) | Protective housing |
| (f)(2) | Safety interlocks on removable housing parts |
| (f)(3) | A readily available **remote interlock connector** |
| (f)(4) | A **key-actuated master control**: "The key shall be removable and the laser shall not be operable when the key is removed." |
| (f)(5)(ii),(iv) | An **emission indicator** active "during emission" and "sufficiently prior to emission … to allow appropriate action to avoid exposure", and "clearly visible through protective eyewear" |
| (f)(6) | A permanently attached **beam attenuator** |
| (f)(7) | Controls located so that operation does not require exposure |
| (f)(10) | A **manual reset** before emission can resume after remote-interlock interruption or loss of main power lasting more than 5 s |

- 21 CFR 1040.11(b) and (c) limit surveying/levelling/alignment and **demonstration laser products to Class IIIa** (LD-24). A 4 A NUBM44 handheld cannot lawfully be sold in the US as a pointer or demonstration product.
- DTR sells these diodes as components, exempt from 1040.10/1040.11 requirements for complete products (LD-20).
- FDA reporting and variance procedures were not researched (**UNKNOWN**).

**IEC 60825-1:2014.**
- Engineering clauses: 6.2 protective housing, 6.3 access panels and interlocks, 6.4 remote interlock connector, 6.5 manual reset, 6.6 key control, 6.7 laser radiation emission warning, 6.8 beam stop or attenuator, 6.16 power limiting circuit. Labelling: 7.7 Class 4 (LD-25).
- **Only the table of contents was read**, so the clause details are UNKNOWN.

**Driver-level implications (INFERRED, not legal advice).**
- Build a hardware enable chain: key or lockout, plus a remote-interlock input, plus a firmware enable. Every element must independently block emission, and the §6.4 pass-through must be closed.
- Drive an emission-indicator LED that lights before and during emission. Pick a colour visible through 445–450 nm eyewear, such as red or amber, depending on the eyewear's transmission.
- A **2 s turn-on delay** is cited by ILX as a CDRH requirement (LD-21). The CFR text read says only "sufficiently prior", so treat 2 s as common practice and verify it.
- No automatic resumption of emission after battery removal or an interlock trip.
- A full compliance assessment is required before any product release.

---

## 8. Open questions / UNKNOWNs

| # | Item | Status | What was searched or tried |
|---|---|---|---|
| 1 | Official Nichia NUBM44 spec (diode or bank) | **Not public.** Nichia does not sell or acknowledge the part (LD-15, LD-18, LD-08). | Web searches: "Nichia NUBM44 specification sheet", "NUBM44 datasheet pdf forward voltage threshold", "NUBM44-V2 Nichia", "NUBM44 UTZ-SF", "SPECIFICATIONS FOR NICHIA BLUE LASER DIODE bank NUBM44", "Nichia NUBM47 bank specification". Nichia spec API (`led-ld.nichia.co.jp/api/data/spec/ld/<part>.pdf`) returned 404 for NUBM44, NUBM44E, NUBM47, NUBM08, NUBM07E, NUBM31T, NUBM34, NUBM43, NDB7A75, NDB7875. |
| 2 | Absolute-maximum forward current | **UNKNOWN** (relatives 3.0–4.0 A; LD-05 Iop max 4.2 A) | As above |
| 3 | Reverse-voltage rating | **UNKNOWN** (only 85 mA allowable reverse current) | Nichia relatives; LD-05; LPF searches on reverse polarity found nothing |
| 4 | ESD HBM rating | **UNKNOWN** | Nichia relatives and vendors: qualitative statements only |
| 5 | Junction-to-case thermal resistance | **UNKNOWN** | Vendors give only a mount recommendation (<1.5 °C/W) |
| 6 | Internal Zener present? | **Conflicting.** Probably yes (LD-04, LD-05, LD-28); APS says no (LD-08). | No teardown or decap evidence found. Resolve with the §3.5 DMM test on received parts. |
| 7 | Case isolation | MEDIUM-HIGH confidence "isolated", not Nichia-documented for this part | §3.3. **Verify every unit and module.** |
| 8 | Vf at 4 A distribution | Only 4 datasets (4.26–4.62 V); measurement point not stated | Recommend measuring 4-wire on received units at 1, 2, 3, 4 A |
| 9 | NUBM44-specific temperature coefficients | Inferred from the NUBM08 relative | – |
| 10 | Allowed current ripple | **UNKNOWN** | Not given in any Nichia document found |
| 11 | Lifetime at 3.5–4.5 A or at Tcase 50–65 °C | **UNKNOWN** (no quantitative data) | APS 30 h / 72 h runs only (LD-11) |
| 12 | NUBM07E and NUBM48 | No reliable data; NUBM48 nothing found | Reseller search only |
| 13 | Reseller power points (BeamQ / Odicforce: 5.2 W @ 3 A … 7.3 W @ 4.5 A) | **Unverified, not used.** Pages not retrieved before the usage limit. | – |
| 14 | Exact US emission-delay requirement | CFR text says "sufficiently prior"; the 2 s figure comes only from ILX (LD-21) | eCFR blocked; Cornell LII copy read |
| 15 | Diode identity in Endurance's Dec-2021 table (M4) | Not stated on the page | Wayback copy of LD-13 |
| 16 | Thorlabs handling and tutorial guidance | Not retrievable (bot-check or TLS failure), so not cited | Thorlabs spec-sheet PDFs |
