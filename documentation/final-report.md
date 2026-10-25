# Design review report - 2026-10-24

The larger evaluation board is fully routed and passes the current CAD checks. The 22 mm compact board
remains a routing draft. Both manufacturing file sets are review artifacts. Evaluation Gate F passes its
automated checks since the 2026-10-25 polarity decision (REQ-BAT-04), and no physical-validation evidence exists.

## Verified evidence

| Check | Compact | Evaluation |
|---|---|---|
| Schematic ERC errors / warnings | 0 / 0 | 0 / 0 |
| Connectivity differences from specification | 0 | 0 |
| PCB footprints | 65 | 68 |
| DRC errors / warnings | 0 / 3 | 0 / 0 |
| Unconnected items / schematic parity findings | 43 / 0 | 0 / 0 |
| Export internal consistency | PASS (DRAFT) | PASS (DRAFT) |
| BOM lines / BOM parts / centroid rows | 48 / 53 / 52 | 48 / 53 / 52 |

The generated [validation register](../reports/validation-register.md) controls the gate state. DRC and export
manifests bind the authoritative placement, connectivity and parameter sources to actual CAD bytes; exported
files carry their own hashes. The two documented DRC omissions are explained in DD-20.
All 120 Python tests pass, including actual KiCad geometry tests and failure/stale-evidence regressions.
Firmware builds for ATtiny1616 and passes 26 host checks. Eleven averaged behavioural simulations pass;
those models do not replace switching-waveform or fault measurements. Twenty of twenty-one engineering
calculation checks pass; estimated efficiency at 4 V is 94.5883%, below the specified greater-than-95% target.

## Review artifacts

Each `manufacturing/pcbway/<variant>/` package contains eleven layer Gerbers, separate PTH/NPTH drills and
maps, two BOM formats, centroid data, iBOM, schematic/assembly/fabrication PDFs, three board views, stack-up
note, review marker, fabrication ZIP and export evidence. All generated PDFs open and images verify.
Renders currently show board geometry without resolved component bodies, so height/enclosure validation
remains open. The stack-up is an engineering target awaiting fabricator confirmation.

The exact router input/session and source hashes are archived under `hardware/<variant>/routing/`.
Replaying those checkpoints is documented there; a new autoroute requires renewed validation of source-defined
post-route corrections. The editable native projects and placement sources remain the engineering record.
`package.ps1` creates an explicitly DRAFT review archive with a source/evidence inventory and recorded gates.

## Remaining decisions and validation

- Battery polarity (REQ-BAT-04) is decided and marked on both boards; check the host against the labels (T3.3).
- Review evaluation gate-drive/bootstrap loops, Kelvin sense isolation, power necks and thermal current paths.
- Rework compact placement/fanout; retain its three connection-width warnings and 43 incomplete connections
  as open findings. See [the compact routing assessment](../engineering/compact-feasibility.md).
- Resolve the documented default-current risk and efficiency miss; verify sourcing data without inventing
  stock or prices.
- Follow [assembly instructions](assembly.md) and the [bench plan](testing/test-plan.md), beginning with a rated
  dummy load. Gate G needs measured electrical, fault and thermal results on assembled hardware.

No manufacturing order has been placed. This report does not claim production readiness.
