# PCBWay fabrication and assembly requirements (for the 22 mm round NUBM44 driver PCB)

Researched 2026-10-24 by the manufacturing/CAD research agent. Source IDs (MFG-xx) are listed in
`research/sources/manufacturing-sources.md`. Local text copies of every PCBWay page cited are in
`research/datasheets/mfg_pcbway_*_2026-10-24.txt`. Those copies are the evidence trail, so check
them if this summary and a live page ever disagree.

How to read this document:
- **"quoted"**: exact text from the source. Copy column names and values from these.
- **DERIVED**: my engineering inference from the quoted facts. It is not a PCBWay statement.
- **UNKNOWN**: I looked and found nothing. The note says where I looked.

PCBWay pages carry no revision dates (the footer reads "© 2024 PCBWay"). The two help articles
are dated, and that date is given with each. Every value below was read on 2026-10-24.

---

## 0. Decisive facts for our design (summary)

| Topic | Fact | Source |
|---|---|---|
| Board size (fab) | Standard minimum is "(min 3*3mm)". In the Advanced table, "Minimum finished pcb size" is "≥20mm" for the normal process, "10mm≤Size<20mm" for medium difficulty and "<10mm" for high. **A 22 mm board falls in the normal process.** | MFG-01 |
| Assembly of a round 22 mm board | **Must be panelized, with break-away rails.** Quoted: "If your PCB dimension is smaller than 50mmx100mm, or if your PCB is of any shapes (circular, or odd shape) other than rectangle, your boards must be panelized in an array for assembly." | MFG-03, MFG-09 |
| Rails | Quoted: "If the clearance between the board's edge and copper features is less than 3.5mm (138mil), or your boards need to be panelized for some reason, Break-away rails (Break-away tabs) must be added at the two longer paralleled edges of the boards". The PCBWay diagram shows **5 mm** rails. | MFG-03, MFG-04 (image) |
| Assembly panel size | Quoted: "Min panel for assembly can be 50*50mm and max can be 330*530mm. Panel design can be provided by you or we do the panel design according to your request." | MFG-04 |
| Trace/space | Standard tier: "0.1mm/4mil". Advanced table, per copper weight before compensation: outer 1 oz (35 µm) "≥5/6 mil" normal; **outer 2 oz (70 µm) "≥7/8mil" normal**; inner 1 oz "≥4/5 mil"; inner 2 oz "≥6/8 mil". | MFG-01 |
| Drill | "Min drill size is 0.15mm, max drill is 6.0mm. Any holes greater than 6mm or smaller than 0.2mm will be subject to extra charges." | MFG-01 |
| Annular ring | Standard: "0.15mm(6mil)". Advanced outer-layer "weld ring" at 1 oz: via ≥5 mil, component hole ≥10 mil. **At 2 oz: via ≥7 mil, component hole ≥12 mil.** | MFG-01 |
| Thickness options | "0.2,0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0, 2.4, 2.6, 2.8, 3.0, 3.2mm". The 4-layer minimum is "≥0.60mm" for the normal process. | MFG-01 |
| Copper | Outer: "1oz/2oz/3oz/4oz/5oz/6oz/7oz/8oz". Inner: "1oz/1.5oz/2oz/3oz/4oz", "for 4 to 10 layers". | MFG-01 |
| BOM to emit | PCBWay template header row (quoted, see §5.1): `Item #` · `*Designator` · `*Qty` · `Manufacturer` · `*Mfg Part #` · `Description / Value` · `*Package/Footprint ` · `Type` · `Your Instructions / Notes` | MFG-07 |
| Centroid to emit | PCBWay's own KiCad plugin writes `pos_x,pos_y,rotation,side,designator,mpn,pack,footprint,value,mount_type`. Units are mm and Y points up. Coordinates are relative to the KiCad drill/place (aux) origin. Rotation is KiCad-native degrees. Side is `top`/`bottom`. See §5.2. | MFG-19 |
| Rotation convention | PCBWay publishes **no** zero-orientation or rotation convention (UNKNOWN). Its own plugin passes KiCad's footprint orientation through **unchanged**. KiCad library footprints follow KLC F4.2, "Pin 1 is located in the upper left corner (IPC-7351)". | MFG-19, MFG-23 |

---

## 1. Fabrication capabilities: Standard PCB tier (quoted from MFG-01)

PCBWay defines the tiers as: "“Standard PCB” = Advanced + quick-order". The Standard table
reads as follows.

| Item | Capability (quoted) | Remark (quoted / condensed) |
|---|---|---|
| Layers | "1-14 layers" | |
| Material | "FR-4, Aluminum, Copper Base" | High-Tg and similar materials go through the Advanced tier |
| Size | "Single-sided PCB and double-sided PCB: 600*1200mm Multilayer PCB: 560*1150mm (min 3*3mm)" | |
| Outline tolerance | "±0.2mm/±0.5mm" | "±0.2mm for CNC routing, and ±0.5mm for V-scoring." |
| Thickness | "0.2-3.2mm" | "0.2,0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0, 2.4, 2.6, 2.8, 3.0, 3.2mm" |
| Thickness tolerance | t≥1.0 mm: "±10%". t<1.0 mm: "±0.1mm" | "Normally "+ Tolerance" will occur…" |
| Min trace / min spacing | "0.1mm/4mil" for each | |
| Outer copper | "1oz/2oz/3oz/4oz/5oz/6oz/7oz/8oz (35um/70um/105um/140um/175um/210um/245um/280um)" | |
| Inner copper | "1oz/1.5oz/2oz/3oz/4oz (35μm/50μm/70um/105um/140um)" | "Inner copper weight as per customer's request for 4 to 10 layers" |
| Drill (CNC) | "0.15-6.0mm" | Extra charge outside 0.2–6 mm (see §0) |
| Min annular ring | "0.15mm(6mil)" | "For pads with vias in the middle, Min width for Annular Ring is 0.15mm(6mil)." |
| Finished hole tolerance | "PTH: +/-0.08mm, NPTH: +/-0.05mm" | |
| Solder mask | "LPI". Colours: "Green ,Red, Yellow, Blue, White, Black, Matt green, Matte black, Purple, none" | "No extra charge (Green, Red, Yellow, Blue)" |
| Silkscreen | Min character width "0.15mm". Min character height "0.8mm". Width:height ratio "1:5" | Colours: "White, Black, Yellow, None", with "No extra charge (White, Black)" |
| Plated half holes | "Minimum Diameter of Plated Half Holes 0.4mm" | |
| Surface finish | "HASL with lead, HASL lead free, Immersion gold, OSP, Hard Gold, Immersion Silver, Immersion Tin, ENEPIG" | |
| Panelization | "V-scoring, Tab-routing, Tab-routing with Perforation (Stamp Holes)" | "Leave min clearance of 1.6mm between boards for break-routing. For V-score panelization, set the space between boards to be zero." |
| Test | "Fly Probe Testing (Free) and A.O.I. testing(free)" | |

## 2. Fabrication capabilities: Advanced table rows relevant to us (quoted from MFG-01)

Each row gives values in the order normal process / medium difficulty / high difficulty. A blank
means the page shows none.

| Item | Normal | Medium | High / note |
|---|---|---|---|
| Minimum finished PCB size | "≥20mm" | "10mm≤Size<20mm" | "<10mm" |
| Min board thickness, 4L | "≥0.60mm" | "0.40mm" | "<0.40mm" |
| Min board thickness, 1–2L | "≥0.3mm" | "0.25mm" | |
| Drill vs board thickness | "hole diameter 0.2mm: maximum board thickness 1.6mm", "0.25mm: maximum board thickness 2.0mm", "0.3mm≤Ф≤0.35mm, maximum board thickness 3.2 mm" | | |
| Thickness-to-diameter ratio | "≤8" | "8<…≤10" | "10<…≤12" |
| Hole-to-hole spacing | component hole "≥16MIL". Via (≤0.45 mm) "≥11MIL" | 14–16 mil | 13–14 mil |
| Inner isolation ring (hole to inner copper, before compensation), 4L | "≥7MIL" | "6MIL≤…<7MIL" | "5MIL≤…<6MIL" |
| Inner width/spacing, 35 µm | "≥4/5 mil" | "≥4/4 mil" | |
| Inner width/spacing, 70 µm | "≥6/8 mil" | "≥6/7mil" | |
| Outer width/spacing, 35 µm (1 oz) | "≥5/6 mil" | "≥5/5 mil" | |
| Outer width/spacing, 70 µm (2 oz) | "≥7/8mil" | "≥6/7mil" | |
| Outer width/spacing, 105 µm (3 oz) | "≥10/12 mil" | "≥8/10 mil" | |
| Outer weld ring, 35 µm | via "≥5mil". Component hole "≥10mil" | via ≥4, comp ≥8 mil | |
| Outer weld ring, 70 µm | via "≥7mil". Component hole "≥12mil" | via ≥6, comp ≥10 mil | |
| Line-to-board-edge (CNC milling) | "0.25mm" | "0.20mm" | "<0.20mm" |
| SMT pad width | "≥12mil" | "≥9mil" | |
| Solder mask opening | "≥2mil" | "1.5" | "1". Note: "1mil is only concentrated in the BGA area… the maximum is 3mil" |
| Solder mask bridge (dam), Cu <2 oz | "4（spacing between ICs is 8 mil, green oil），variegated or black oil≥4.5mil" | "3-4 …" | |
| Solder mask bridge (dam), Cu ≥2 oz | "5" | "4" | |
| Via plugging | "0.20mm≤hole diameter≤0.40mm，plug hole fullness 70%" | "0.4mm< hole diameter ≤0.70mm", "fullness 100%" | Board thickness "0.40mm≤board thickness≤2.4mm" |
| Castellated hole diameter | "≥0.5mm" | "0.5mm>diameter≥0.4mm" | |
| Castellated hole spacing (edge to edge) | "≥0.3mm" | "0.3mm>diameters≥0.2mm" | |
| ENIG plating | Ni "100-150 µin". Au "1-8 µin" | Ni "200 µin" | Au ">8 µin" |
| Full-board gold plating | Ni "100-150 µin". Au "1-10 µin" | Au "10-50 µin" | "Order center check the final price" |
| Gold finger | Ni "120-150 µin". Au "1-30 µin" | Au "30-50 µin" | |
| Hole copper, through hole | "18-25 µm" | "30-50 µm" | ">50 µm" |
| HASL processing capacity | component hole ">0.5mm". Board thickness "0.5mm≤board thickness≤3.5mm". "2um≤thickness of Tin≤30um" | hole 0.4–0.5 mm | |
| Multilayer thickness tolerance | T≤1.0: "±0.10". 1.0: "±0.13". 1.6: "±0.18" | | |
| Shape tolerance | "tolerance≥±0.15mm" | "±0.10mm≤tolerance<±0.15mm" | |
| Bow and twist | "≤0.75%" | | |
| Acceptance criteria | "IPC2 level standard" | | "IPC Level 3 standard" |

**DERIVED design rules for our board.** Use these in KiCad's DRC and in the FreeRouting rules.
- 1 oz outer layers: track/space ≥0.15/0.15 mm (5.9 mil, meeting the "≥5/6 mil" normal rule).
- 2 oz outer layers (the 8 A input copper): track/space ≥0.20/0.20 mm (meeting "≥7/8mil").
- Copper to routed board edge ≥0.25 mm, except where edge plating is wanted.
- Via 0.3 mm drill / 0.6 mm pad. That gives a 0.15 mm ring, which meets every row above, including the 2 oz via row (≥7 mil = 0.178 mm).
- Do not use 0.2 mm drills on a board thicker than 1.6 mm.
- Solder-mask dam ≥0.1 mm (≥0.127 mm with 2 oz copper). Mask opening ≥0.05 mm per side.
- Silkscreen text ≥0.8 mm high with a ≥0.15 mm stroke.

FreeRouting v2.5.0 also states "Default copper-to-edge clearance is capped cleanly at 250 µm"
(MFG-26). That matches PCBWay's 0.25 mm normal-process line-to-edge rule.

## 3. 4-layer stack-ups (MFG-12)

Local extract: `research/datasheets/mfg_pcbway_4layer-stackups_2026-10-24.txt`. The page reports
"4 Layers Total: 112" stack-ups, but only 43 are server-rendered; the rest load through the page's
filter UI. Its filter offers inner copper of 0.5/1/1.5/2/3/4/5 oz and outer copper of 1–5 oz.

Every 4-layer build is L1 Cu / PP / L2 Cu / CORE / L3 Cu / PP / L4 Cu. Outer copper is a thinner
base foil "Plating to" the finished weight (0.5 oz base for 1 oz finished, 1.5 oz base for 2 oz).
The page warns: "Friendly Reminder: This is a through-hole board stack-up, not applicable for blind
and buried vias."

PCBWay's rule for choosing the residual-copper column: above 60% use the 70% stack-up, 40–60% use
50%, and ≤40% use 30%. For example: "Inner layer Residual copper ratio > 60%, it is suitable to
choose a lamination structure with 70% inner layer Residual copper ratio." Our inner layers will be
mostly plane, so **the 70% column applies (DERIVED)**.

| Finished (nominal) | Outer / inner Cu | Prepreg each side (type, DK, thickness after lamination) = L1–L2 and L3–L4 dielectric | Core (DK 4.6), thickness without / with Cu | Finished thickness (70% residual Cu) |
|---|---|---|---|---|
| 1.6 mm | 1 oz / 1 oz | 7628 RC46%, DK 4.74, 0.1855 mm | 1.03 / 1.1 mm | 1.61 mm ±10% |
| 1.6 mm | 2 oz / 1 oz | 7628 RC46%, DK 4.74, 0.1855 mm | 0.93 / 1.0 mm | 1.58 mm ±10% |
| 1.6 mm | 2 oz / 1.5 oz | 7628 RC46%, DK 4.74, 0.1803 mm | 0.895 / 1.0 mm | 1.57 mm ±10% |
| 1.2 mm | 1 oz / 1 oz | 7628, 0.1855 mm | 0.63 / 0.7 mm | 1.21 mm ±10% |
| 1.2 mm | 2 oz / 1 oz | 2116 RC58%, DK 4.45, 0.1195 mm | 0.73 / 0.8 mm | 1.24 mm ±10% |
| 1.0 mm | 1 oz / 1 oz | 7628, 0.1855 mm | 0.43 / 0.5 mm | 1.01 mm ±10% |
| 1.0 mm | 2 oz / 1 oz | 3313 RC58%, DK 4.45, 0.0925 mm | 0.53 / 0.6 mm | 0.99 mm ±0.1 mm |
| 0.8 mm | 1 oz / 1 oz | 7628, 0.1855 mm | 0.23 / 0.3 mm | 0.81 mm ±0.1 mm |
| 0.6 mm | 1 oz / 1 oz | 3313, 0.0925 mm | 0.23 / 0.3 mm | 0.62 mm ±0.1 mm |
| 0.6 mm | 2 oz / 1 oz | 3313, 0.0925 mm | 0.13 / 0.2 mm | 0.59 mm ±0.1 mm |

Notes:
- The 50% and 30% columns are in the local extract.
- The 0.8 mm 2 oz/1 oz entries list "Outer Base Copper 0.5OZ". That looks like a data error on the page, so confirm it with PCBWay before relying on it.
- Stack-ups with 2 oz inner copper are not in the rendered subset, so they are **UNKNOWN**. The page filter offers 2 OZ inner. Check on the page or in the quote form.
- For 2-layer boards PCBWay publishes no stack-up beyond the thickness list. A 2-layer board is a single core.

## 4. Special processes (vias, edge plating, castellation, finish)

### 4.1 Via covering, plugging and via-in-pad
- Via covering (MFG-14) lists the IPC-4761 types:
  - Tented, types I-a/I-b: "usually for vias up to 0.3 mm".
  - Tented and covered: types II-a/II-b.
  - Plugged: types III-a/III-b, "about 0.4 to 0.5 mm".
  - Plugged and covered: types IV-a/IV-b.
  - Filled: type V.
  - Filled and covered: types VI-a/VI-b.
  - Filled and capped: type VII, "Used for via-in-pad".
- The default covering type and the cost of each option are **UNKNOWN**. MFG-14 states neither.
- In practice the KiCad Gerber dialog shown in PCBWay's own KiCad 8 guide (MFG-17) has **"Tent vias" ticked**. This means no mask opening over vias.
- Via-in-pad (MFG-13): BGA vias "requires resin filling, with an electroplated cap for convenient customer soldering". The listed disadvantages are "Higher production cost" and "Longer production time". The page gives no price and no order-form procedure, so both are **UNKNOWN**.
- **DERIVED:** avoid via-in-pad. Put thermal vias for the converter IC and MOSFETs beside the pads, tented. Alternatively, accept open thermal vias in an exposed pad and specify plugged vias as an order note.

### 4.2 Edge plating (side plating), relevant to a perimeter contact ring (MFG-15)
- Quoted design rules:
  - "overlapping copper (i.e. copper surfaces, pads or traces) should be used to define the metalized areas in CAD layout file."
  - "The minimum overlap value should be 0.5mm."
  - "For the connection layers, a minimum of 0.3mm of a connecting copper line must be defined."
  - "On non-connection layers, the copper should be kept at least 0.8mm apart from the edge of outer contour."
- Restrictions (quoted or condensed):
  - The plating cannot cover the full edge length because the board is held in the production panel, so "some gaps are required when placing the rout label".
  - Edge plating is defined before through-hole plating, so **V-scoring cannot be used**.
  - "it should be solder mask opening in the file."
- Finish: PCBWay "usually recommends immersion gold or immersion silver" for edge plating. ENIG, ENEPIG and HASL are listed as possible.
- Ordering: "If there is a demand for side plating boards, please feel free to contact us!" Text notes in the files are allowed. This is a **manual quote, and the price is UNKNOWN**.
- **DERIVED for our round board:** a full 360° plated ring is not possible. Plan for gaps at the tab or rout positions, and state the plated arcs in a fab drawing or note.

### 4.3 Castellated (plated half) holes (MFG-16, MFG-01)
- Quoted:
  - "Typically,the minimum half-hole diameter is 0.6mm,but PCBWay accepts a minimum half-hole diameter of 0.4mm."
  - "Minimum edge-to-edge spacing between holes:0.55mm.If it is between 0.47mm and 0.55mm,there will be an increase in price and lead time."
  - "Minimum solder mask bridge size:0.1mm."
- Placement: "Place the center point of each plated half-hole precisely on the edge or outline of the PCB". Define them as PTH "in the drill file, such as *.drills_pth.xln file, *pth.drl file".
- Pads: "Each plated half-hole must be within a pad on each copper layer (including inner layers for a 4-layer board)".
- The Advanced table gives a normal-process diameter of "≥0.5mm" and spacing of "≥0.3mm". This differs from the 0.55 mm spacing on MFG-16. **Use ≥0.6 mm holes at ≥0.55 mm edge-to-edge spacing to satisfy both.**
- The page's thickness/diameter table is partly garbled in the source. The legible rows are:
  - ≤1.0 mm board: 0.4 mm holes, 0.25 mm minimum after routing.
  - 1.2–1.6 mm board: 0.4–0.6 mm holes, 0.25 mm after routing; 0.7–0.9 mm holes, 0.35 mm; ≥1.0 mm holes, 0.45 mm.

### 4.4 Surface finish
- Available finishes are listed in §1.
- No statement about QFN or fine-pitch finish choice was found on the pages reviewed, so PCBWay's own recommendation is **UNKNOWN**.
- **DERIVED recommendation:** use **ENIG** ("Immersion gold"). It gives a planar surface for QFN or exposed-pad parts. It is also what PCBWay recommends for edge plating (§4.2), and it is lead-free.
- HASL constraints (quoted in §2): component holes >0.5 mm, and board thickness 0.5–3.5 mm.

## 5. Assembly (PCBA) data formats

### 5.1 BOM: official PCBWay template (MFG-07, local `mfg_pcbway_Sample_BOM_PCBWay.xlsx`)

`Sheet1` has a title in cell D2: "xxxx xxxx xxxxx xxPCS BOM  (Sample Bill of Materials)". **The
header is row 6**. Exact cell texts, A6 to I6, are below. Note the leading asterisks and the
**trailing space** in G6.

```
Item # | *Designator | *Qty | Manufacturer | *Mfg Part # | Description / Value | *Package/Footprint  | Type | Your Instructions / Notes
```

Sample rows, verbatim:
- `1 | U1 | 1 | Linear | LTC3780EG#PBF | IC BUCK-BOOST CONV 24-SSOP | 24-SSOP | SMD |`
- `2 | U2,U4 | 2 | Fairchild | LM2904M | … | 8-SOIC | DNS |`
- `8 | R16, R31 | 2 | Panasonic | ERJ-6ENF4702V | … | 0805 | SMD |`
- `15 | CN3,CN4 | 2 | Molex | 53047-0510 | … | 5POS | thru-hole |`

Conventions visible in the template:
- One line item per unique part.
- Designators are comma-separated in one cell. The template has both "U2,U4" and "R16, R31".
- `Type` takes `SMD`, `thru-hole` or **`DNS`** (do not stuff). This is the template's own way to mark DNP parts.

Text rules (quoted):
- SMT ordering guide (MFG-06): "Please fill in designators(references), quantity, package and part numbers." Also: for resistors and capacitors without a part number, "value and package information is needed". And "It's also better list components as PTH or SMD." And "We do not accept BOM files in pdf".
- File requirements (MFG-05): "We accept the BOM in the format of .xls, xlsx or .csv." Kitted fields: "Line#", "Quantity Per Part Number", "Reference Designator", "Part Number", "Part Description", "Package", "Type (Surface mount, Thru-hole or Hybrid)". Turnkey adds "Manufacturers Name", "Manufacturers Part Number", "Distributors Part Number".
- Plugin README (MFG-20): necessary fields are "Designator", "Quantity", "MPN/Part Number" and "Package/Footprint". "Manufacturer" and "Description/value" are optional.

**BOM CSV written by PCBWay's own KiCad plugin.** These are PCBWay Fabrication Toolkit and
PCBWay Plug-in v1.0.5, sharing an identical `process.py` (MFG-19, MFG-20):
- File name: `<board>.kicad_pcb_bom.csv` (Toolkit) or `PCBWay_bom.csv` (Plug-in).
- Encoding `utf-8-sig` (UTF-8 with BOM). Written with Python `csv.writer` defaults: comma separator, minimal quoting, `\r\n` line ends.
- Header, for KiCad ≥8:

```
Designator,Quantity,Value,Footprint,Package,MPN,DNP,Mount_Type[,<any other non-empty footprint field, in first-seen order>]
```

- `Designator` holds refs joined with `", "`. Rows are grouped on value + footprint + package + MPN, and DNP parts get a row each.
- `DNP` is `Yes` or empty. `Mount_Type` is `smt` or `tht`.
- `Footprint` is the library item name only.
- MPN is read from the first footprint field present among: `mpn, MPN, Mpn, PCBWay_MPN, part number, Part Number, Part No., Mfr. Part No., Mfg Part, Manufacturer_Part_Number`.
- Package is read from: `pack, PACK, Pack, package, PACKAGE, Package, case, CASE, Case`.
- These footprint fields are never added as extra columns: `ki_fp_filters, DNP, Reference, Value, Datasheet, Footprint`, plus the MPN and package keys. So, for example, `Manufacturer` and `Description` become extra columns when they are non-empty.
- Gotcha: the plugin marks a part DNP if **a field named DNP exists in any letter case, even when empty**, or if Value == "DNP", or if KiCad's DNP attribute is set. Do not add a "DNP" user field to symbols.
- Footprints flagged "exclude from BOM" are omitted. Designators containing `**` are skipped.

**Recommendation (DERIVED).** Emit the BOM in the official template columns, as `.xlsx` or `.csv`
with the header in the first row. PCBWay accepts `.csv` (quoted above). Whether their intake is
tolerant of the header sitting in row 1 instead of row 6 is not stated, though a hobbyist's
reordered CSV was understood (MFG-24). The headers can be copied verbatim from above.
- Mark DNP lines with `Type = DNS` and say "DO NOT PLACE" in `Your Instructions / Notes`.
- Mark hand-soldered or manual parts as `thru-hole` or with a note.
- Optionally also emit the plugin-style CSV. The two carry the same data.

### 5.2 Centroid / pick-and-place

PCBWay's text requirements (quoted):
- "The Centroid file describes the position and orientation of all the surface mount parts, which includes the reference designator, X and Y position, rotation and side of Board (Top or Bottom)." (MFG-05, MFG-09)
- "Only surface mounting parts are listed in the Centroid." "THT designators can be excluded." (MFG-05, MFG-06)
- "designators in pick&place file should match the designators in silkscreen layer or assembly drawing file." (MFG-06)
- Accepted as "Centroid (Pick & Place PNP file, or XY Data or files in other formats)" (MFG-02).
- Units, delimiter and rotation convention are **not specified** on PCBWay pages.
- A PCBWay help article (pcbway.ru mirror) reportedly says the file may be Excel, .txt or .pos, in mm. This is from a search-result snippet only; I did not open it (UNVERIFIED).

The PCBWay sample centroid file (MFG-08, local `mfg_pcbway_sample_centroid_file.txt`) is
Altium/Protel style: whitespace-aligned, units in mil with a `mil` suffix, and CRLF line ends. Its
header line is:

```
Designator Footprint               Mid X         Mid Y         Ref X         Ref Y         Pad X         Pad Y TB      Rotation Comment
```

A sample row: `R25        0603R             1763.386mil   1148.425mil   1763.386mil   1148.425mil   1763.386mil   1178.425mil  T        270.00 RES`.
`TB` is `T` or `B`. Rotations are 0–360 with two decimals; "360.00" appears for 0°.

**Positions CSV written by PCBWay's own KiCad plugin** (MFG-19, MFG-20). This is the format PCBWay's
toolchain ingests from KiCad, so replicate this one:
- File name: `<board>.kicad_pcb_positions.csv` (Toolkit) or `PCBWay_positions.csv` (Plug-in). Encoding `utf-8-sig`, Python `csv.writer`.
- Header:

```
pos_x,pos_y,rotation,side,designator,mpn,pack,footprint,value,mount_type
```

- `pos_x = (fp.x − aux_origin.x) / 1e6` mm.
- `pos_y = −(fp.y − aux_origin.y) / 1e6` mm. **Y is positive up, relative to the board's drill/place (aux) origin.**
- `rotation = fp.GetOrientation().AsDegrees()`. This is KiCad-native, counter-clockwise positive, with no offset table and no bottom-side correction.
- `side` is `top` or `bottom`. Bottom X is **not** negated.
- Numbers are plain Python floats, e.g. `12.5`.
- All footprints not flagged "exclude from position files" are included, THT ones too (`mount_type=tht`). DNP parts are **not** filtered out. Designators containing `**` are skipped.

**KiCad's own CSV position file**, for comparison (KiCad 10.0.6 source, MFG-21):
- Header: `Ref,Val,Package,PosX,PosY,Rot,Side`.
- Ref, Val and Package are double-quoted. Numbers use `%f`. Y is sign-inverted (Y up). Rotation comes from the same `GetOrientation().AsDegrees()`. Side is `top` or `bottom`.
- `kicad-cli pcb export pos` **defaults to inches and ascii**: "--units … Options are in (default) or mm" (MFG-22). Always pass `--format csv --units mm --use-drill-file-origin`, and add `--smd-only` or `--exclude-dnp` as wanted.
- Mapping to the plugin format:

| KiCad column | Plugin column |
|---|---|
| Ref | designator |
| Val | value |
| Package | footprint |
| PosX | pos_x |
| PosY | pos_y |
| Rot | rotation |
| Side | side |

- Secondary evidence (MFG-24): a hobbyist's PCBWay order was accepted with KiCad-CLI CSV headers renamed to `Designator,Value,Footprint,Mid X,Mid Y,Rotation,TB` and `bottom`→`B`.

**Rotation / zero orientation.**
- PCBWay states no convention: **UNKNOWN**. I searched the PCBWay help centre, assembly pages and FAQ.
- Evidence that KiCad-native rotation is what PCBWay expects: their own plugin sends it unconverted.
- Official KiCad footprints follow KLC F4.2, "Footprints should be oriented such that Pin 1 is located in the upper left corner (IPC-7351)". Per KLC F6.2 the footprint anchor is at the body centroid (MFG-23).
- The plugin README says "our engineers will double check the files before the production."
- **DERIVED:** keep custom footprints KLC-conformant (pin 1 top-left, origin at body centre). Ship polarity marks on silkscreen plus an assembly-drawing PDF, and expect PCBWay's DFM query for any doubtful part.

### 5.3 Polarity, designators, DNP, side (MFG-06)
- "Please add polarity cathode or anode mark and pin 1 in silkscreen layer." If marks are not wanted on the board, send an assembly drawing.
- Side: quote form "Stencil Side": "Top", "Bottom", "Top+Bottom (On Single Stencil)", "Top & Bottom (On Separate Stencil)" (MFG-10).
- DNP: the only PCBWay conventions are the template's `Type = DNS` (MFG-07) and the plugin's `DNP = Yes` column. No PCBWay prose about DNP was found.

### 5.4 Files PCBWay needs for PCBA
- Quoted (MFG-05): "The same Gerber files in format of RS-274X that you send to us for your PCB fabrication will be required to assemble your boards." "As a minimum request, PCB assembler needs the files of three layers: Silkscreen, Copper (Track) and Solder Paste."
- From the FAQ (MFG-09): "We need Gerber files, Centroid data and BOM for your PCBA orders." Also: "please also send assembly drawings, instructions and photos".
- **Include F.Paste and B.Paste Gerbers.**

## 6. Panelization for our 22 mm round board

Quoted requirements:
- Special reminders and FAQ (MFG-03, MFG-09):
  - "If your PCB dimension is smaller than 50mmx100mm, or if your PCB is of any shapes (circular, or odd shape) other than rectangle, your boards must be panelized in an array for assembly."
  - "once we start fabricating your boards we will have the panelization file (solder paste data), we will transfer the data to PCBA department to create the stencil to match the panelized PCB."
  - Rails (§0): at "the two longer paralleled edges".
- Assembly capability page (MFG-02): "Min Board Size: 10mm x 10mm (Boards smaller than this size need to be panelized)". It also says: "We can assemble boards in Rectangular, Circular and any Odd Shapes. (For shapes other than rectangle, you need to panelize the boards in an array, and add break-away rails at the two longer paralleled edges…)". The 10 mm and 50×100 mm thresholds conflict, but **the round-shape rule applies to us either way**.
- Panel page (MFG-04):
  - "Min panel for assembly can be 50*50mm and max can be 330*530mm."
  - "For panel with tab routes, 1.6mm space is needed between boards."
  - Stamp holes: "diameter should be ≥0.45mm, regular diameter is 0.55mm-0.6mm. Holes space has to be ≥0.35mm, usually we will add 5-6 holes to each tab". A plain tab "has to be at least 2mm" wide.
  - V-score spacing "0mm or 3mm". "V-scoring has to be continuous and can not be stopped in panel".
  - Fiducials: "usually there are 3 fiducial marks in each panel. Marks diameter is 1.0mm with 1.7mm soldermask opening and placed in the middle of edge rails."
  - Tooling holes: "Usually there are 4 mounting holes per panel". The sizes appear only in the page images. Local copies are `mfg_pcbway_panel-mounting-holes_image.jpg` and `mfg_pcbway_panel-fiducials_image.jpg`. I read the images as follows:
    - Rail width **5 mm**.
    - Tooling hole **ϕ2.0 mm** centred **2.5 mm × 2.5 mm** from the panel corner.
    - Fiducial **ϕ1 mm**, centred 2.5 mm into the rail and **5 mm** from the panel end.
- Rail-width text, component-to-rail clearance and panelization fee are **UNKNOWN** (not stated).

**DERIVED panel example** (let PCBWay draw it, or draw it ourselves):
- A 3 × 2 array of 22 mm discs, tab-routed with 1.6 mm gaps between boards and to the rails, plus two 5 mm rails on the long edges.
- X = 3·22 + 2·1.6 = **69.2 mm**. Y = 2·22 + 1.6 + 2·1.6 + 2·5 = **58.8 mm**. That meets the 50×50 mm minimum. A 2 × 2 array is too narrow at 45.6 mm.
- Use 4–6 mouse-bite tabs per disc. Keep stamp holes out of any edge-plated arc.
- Add 3 fiducials and 4 ϕ2 mm tooling holes on the rails as above.
- V-scoring is impossible on a circular outline: V-cuts must be continuous straight lines.

## 7. Gerber, drill and readme expectations

- **Format:** RS-274X (MFG-05, MFG-10 "Gerber RS-274X").
- **X2:** PCBWay's KiCad 8 guide (MFG-17, "Last updated on 26/06/2024") and KiCad 9 guide (MFG-18, "Last updated on 11/09/2025") both show **"Use extended X2 format (recommended)" unticked**.
- **Other Gerber settings in those screenshots:**
  - Coordinate format "4.6, unit mm".
  - "Use Protel filename extensions" unticked. KiCad names files `*.gbr`, and PCBWay's plugin does the same: `SetUseGerberProtelExtensions(False)`.
  - Plot drawing sheet unticked.
  - The KiCad 9 guide has "Generate Gerber job file" and "Include netlist attributes" ticked. The KiCad 8 guide has both unticked.
  - "Subtract soldermask from silkscreen" is ticked in the KiCad 8 guide and unticked in the KiCad 9 guide. The plugin uses `SetSubtractMaskFromSilk(True)`.
  - The KiCad 8 guide has "Tent vias" ticked.
  - Layers highlighted in both guides: **F.Cu, B.Cu, F.Paste, B.Paste, F.Silkscreen, B.Silkscreen, F.Mask, B.Mask, Edge.Cuts**, plus In1/In2.Cu for 4-layer.
- **Outline:** Edge.Cuts is plotted as its own Gerber. The plugin calls it "Board Outline" and sets `SetExcludeEdgeLayer(True)`, so the outline is not merged into other layers. Draw the circle as one closed Edge.Cuts shape.
- **Drill (Excellon):**
  - KiCad 8 guide: Excellon, "PTH and NPTH in single file" **unticked** (separate files), Minimal header unticked, Oval holes "Use route command (recommended)", Origin "Absolute", Units "Millimeters", Zeros "Decimal format (recommended)", Map file format "PostScript".
  - KiCad 9 guide: same, except **"PTH and NPTH in single file" is highlighted as ticked**, and "Generate map" is unticked.
  - So PCBWay accepts both. **Prefer separate PTH/NPTH**, which their own plugin also does. Castellated holes must be in the PTH file (§4.3).
  - The plugin (MFG-19) calls `drlwriter.SetOptions(False, True, <aux origin>, False)`. Read against KiCad's `EXCELLON_WRITER::SetOptions(aMirror, aMinimalHeader, aOffset, aMerge_PTH_NPTH)`, that means no mirror, minimal header, offset = aux origin, PTH/NPTH not merged. This reading is DERIVED from the signature; I did not run the plugin.
  - It then calls `drlwriter.SetFormat(False)`, which by KiCad's `SetFormat(bool aMetric, …)` signature means inch units (DERIVED from the signature), and `CreateDrillandMapFilesSet(dir, True, False)`, i.e. **no drill map**.
  - **A drill map is not required.**
- **Origin:** PCBWay's KiCad 9 guide shows "Use drill/place file origin" ticked for Gerbers. The plugin uses the aux origin for Gerbers, drill and positions. **Set the KiCad drill/place origin**, for example at the board centre or at the lower-left of the board's bounding box, and use it consistently in Gerber, drill and centroid output.
  - Caution: the same KiCad 9 guide's drill dialog shows Origin "Absolute". Mixing the two misaligns drills against copper unless the aux origin is at (0,0). Do not copy that combination.
- **Netlist:** the plugin also writes an IPC-D-356 netlist (`IPC356D_WRITER`, `…_netlist.ipc` or `PCBWay_netlist.ipc`). This is optional, but it helps their flying-probe test.
- **Readme or fab notes:**
  - PCBWay specifies **no readme format (UNKNOWN)**.
  - The quote form has an optional field: "Please fill in the layer order from top to bottom here. (Optional)" / "…according to the layer names in the Gerber file." (MFG-10).
  - The side-plating page says to "add text notes to the file". The panel page says "You can leave message about panel design to us when you submit new order".
  - **DERIVED readme content:**
    - Board name, revision and date.
    - Layer order mapped to file names.
    - Finished thickness, copper weights (outer/inner), material and Tg.
    - Finish (ENIG), mask and silk colours.
    - Via treatment (tented / plugged).
    - Special processes: edge plating arcs, castellation.
    - Panel instructions: 3×2, 5 mm rails, fiducials, tooling holes, mouse bites.
    - PCBA side(s), DNP policy, contact.
- **PCBWay plugin output layout, for reference:**
  - Toolkit: `<project>/pcbway_production/<YYYY-MM-DD-HH-MM-SS>/` containing `<board>.kicad_pcb_gerber.zip` (Gerbers and drill), `…_bom.csv`, `…_positions.csv` and `…_netlist.ipc`.
  - Plug-in: zips everything and HTTP-POSTs it to `https://www.pcbway.com/Common/KiCadUpFile/` with form fields `boardWidth`, `boardHeight` and `boardLayer`, then opens the returned redirect URL. We should **not** call that endpoint from scripts.
  - The plugin forces `m_SolderMaskMargin = 0` and `m_SolderMaskMinWidth = 0` in the board's design settings before plotting.

## 8. Ordering, quantities, lead time, pricing (only what was found)

- **Minimum PCBA quantity:** "Our minimum is as low as 5 pieces." (MFG-02). The quote form quantity list starts at 5 (MFG-10).
- **Parts sourcing (MFG-02):**
  - "Consigned/kitted: We prefer you supply all the parts…"
  - "Turn-key: … We do not mark up on the parts cost… We will always ask for your approval before making any decisions."
  - "Partial Turn-key/Combo: This is our regular practice which you offer the main devices and components, while we source the rest for you."
- **Consigned overage (MFG-03):**
  - 0603–2225, SOT, SOD and MELF parts "require a minimum of 50 pieces and have to exceed the required quantity by 30 pieces".
  - 0201, 0402 and miniature parts need a minimum of 100, and must exceed the required quantity by 50.
  - Expensive parts need "1-5 pieces" extra.
  - "Unused and excessive parts … will not be returned by default."
- **Assembly limits (MFG-02):**
  - Passives "as small as 01005, 0201,0402". "we can assemble 0.25mm fine pitch parts". BGA "0.3mm pitch for rigid PCBs".
  - Max assembly board "250mm x 500mm". Single- or double-sided. Leaded or lead-free solder.
  - Testing: AOI, X-ray "checks for BGAs, QFN", ICT and functional test.
- **Lead time:**
  - "Our assembly time ranges from 24 Hours to a few weeks." Turn-time "begins immediately after all the parts are ready and all the PCB files … Centroid … BOM … are complete" (MFG-02).
  - Marketing tile: "PCBA lead time 3-5 days" (MFG-10).
  - Turnkey time "largely depends on how quick we can get all the parts" (MFG-09).
- **Pricing structure (MFG-09):** "Our online instant quote system gives the rough idea of the cost of PCBA which include the tooling, laser cut steel stencil, and labor. In case of Turn-key or partial Turn-key PCBA, the cost of parts will be added."
  - Quote inputs: "Quantity", "No. of Unique Parts", "Number of SMD Parts", "Thru-Holes" (MFG-10).
  - **Setup fee and per-joint price: UNKNOWN.** They are not published. A live instant quote needs the web form, which I did not submit.
- **Published price points (MFG-10, MFG-11):**
  - "1-14 layers PCB Fab $5 /10pcs".
  - "$29 /20 pcs" PCBA.
  - "PCBA provides free stencil" next to "$15 /pcs". Standalone stencil prices include, for example, "Valid area 190 × 290 mm $10.00" and "370 × 470 mm $15.00".
- **$29 PCBA promo conditions** (PCBWay blog, "Oct 21,2026", MFG-11):
  - "All components must be supplied by PCBWay"; rigid PCBs only.
  - "No more than 20 boards per order". "a maximum of 200 components" per board, 600 in total.
  - "no more than 100 different component types". Through-hole joints ≤100.
  - New customers can use it once a month, returning customers twice. It covers assembly only. Fabrication, parts and shipping are quoted separately.
  - **DERIVED:** our board is likely to qualify if PCBWay sources all the parts.

## 9. Open items to confirm with PCBWay (in the order notes or with a sales rep)

1. Whether they will panelize the round board for us, and the fee (UNKNOWN).
2. Edge-plating price and minimum gap or tab rules for a 22 mm disc. This is a manual quote.
3. Default via treatment (tented vs plugged) and the cost of plugging.
4. Whether a 2 oz outer / 2 oz inner 4-layer stack-up is available in the thickness we choose.
5. Confirmation that KiCad-native rotation in the plugin-style CSV is accepted as-is, which their own plugin implies.
