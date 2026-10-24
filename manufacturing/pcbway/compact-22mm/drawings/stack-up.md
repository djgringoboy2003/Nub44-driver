# Fabrication stack-up and CAD review note

Engineering targets from DD-14 and DD-18; fabricator confirmation remains OPEN.
The per-variant placement source and generated PCB define the outline and layer order.

| Item | Design target / status |
|---|---|
| Layers | F.Cu / In1.Cu / In2.Cu / B.Cu |
| Finished board thickness | 1.6 mm target (DD-14) |
| Copper | 1 oz target on all layers (DD-14); confirm final construction with PCBWay |
| Finish | ENIG target (DD-14) |
| In1.Cu | GND reference plane; autorouter signal routing disabled |
| Outer layers | Power copper and signal routing; evaluation assembly on top |
| In2.Cu | Source-defined power copper and GND fill, with signal routing where permitted |
| Minimum routed width / clearance | 0.15 / 0.15 mm source design rules |
| Through via diameter / drill | 0.60 / 0.30 mm source design rules |
| Copper to outline rule | 0.30 mm; actual DRC findings control acceptance |

Exact laminate materials, dielectric thicknesses, finished copper tolerances, solder mask,
impedance requirements and approved stack-up drawing are UNKNOWN until the fabricator confirms them.
No controlled-impedance claim is made. The research stack-up example in DD-14 is not a fabrication
approval. Do not manufacture while Gate F is open or battery polarity remains blocked.

Gerber/drill and centroid coordinates use the board auxiliary origin. Bottom centroid X coordinates
retain their sign; side and rotation are checked against native KiCad position export. Assembly PDFs,
iBOM and native CAD must be reviewed together for orientation and solder access.

Rendered views currently show PCB geometry and any locally resolved models. Missing supplier models
and generated placeholder bodies prevent component-height or enclosure-clearance validation from the
render alone. Physical fit and thermal/electrical measurements remain Gate G work.
