# Previous design: preserved reference material

## Status of the files

The project brief says the earlier conceptual work might include:

| File | Described as | Found? |
|---|---|---|
| `nubm44_driver.kicad_pcb` | Mechanical template, circular outline, no routed circuit | **No** |
| `nubm44_driver_report.md` | Conceptual design report | **No** |
| `nubm44_driver_schematic.png` | Illustrated circuit diagram | **No** |
| `detailed_schematic.png` | Illustrated circuit diagram | **No** |
| `detailed_wiring_schematic.png` | Illustrated wiring diagram | **No** |
| `project_package.zip` | Bundle of the above | **No** |

Search performed on 2026-10-24:

- `C:\NUBM44 driver` (the workspace) was empty: no files, not a git repository.
- `C:\Users\rober` was searched recursively for `nubm44*`, `*nubm44*`, `detailed_wiring*` and `project_package.zip`.
  The only matches were Claude Code's own project folders and a Windows "Recent" shortcut to the workspace folder.

None of the previous files exist on this machine, so none could be preserved here. If they turn up later,
copy them into this folder unchanged and add a row to the table above. They are **reference material only**.
Do not import them into the design as evidence of electrical correctness.

## What the brief tells us about the previous concept

The brief describes the earlier concept in enough detail to audit it, even without the files:

- The PCB was a circular mechanical template only. It had no routed electronic circuit.
- The wiring diagrams were illustrations, not pin-to-pin schematics.
- Proposed parts: XL6009 boost converter, LM358 op-amp, ATtiny13 MCU, AO3400A switching MOSFET,
  AO4407A reverse-polarity MOSFET, 0.15 Ω current-sense resistor (rated 0.5 W), 10 µH boost inductor.
- Feedback: an LM358 arrangement that was never fully defined, plus a diode connected into the regulator
  feedback node without verification.
- Battery polarity: the original specification and the earlier documentation contradict each other
  (see `engineering/requirements.md`, REQ-BAT-04).

The audit of each item, with datasheet evidence, is in
[`engineering/previous-design-audit.md`](../../engineering/previous-design-audit.md).
