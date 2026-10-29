# Design review report (2026-10-26)

> **Update after the independent audit of 2026-10-26** (`reports/comprehensive-project-audit.md`). The text below is
> the design review as written before the audit; these statements are superseded:
> - *"147 Python tests"*, *"26 host checks"*, *"11 behavioural simulations"*: now 202 Python tests, six firmware host
>   suites with 531 checks plus a 15-mutant check, and 12 simulations (SIM-11 is a frequency-response analysis of the
>   ngspice deck; SIM-12 is a tolerance sweep with one open finding, AUD-SIM-04).
> - *"Gate F ... passes its automated checks"* remains true, but release readiness is now reported per board:
>   both boards are DRAFT_REVIEW; the evaluation board needs five recorded human reviews to become a
>   PROTOTYPE_CANDIDATE (`reports/release-readiness.md`).
> - The firmware reviewed here had supervision and measurement-chain defects, now fixed (DD-28), including a
>   power-loss comparator reference in the wrong register that disabled the click mode change.

## Summary

| Board | Status |
|---|---|
| Evaluation board (Variant B, 45 × 40 mm) | Fully routed, passes its CAD checks. First prototype (DD-27) |
| Compact 22 mm board (Variant A) | Parked routing draft with 20 open signal connections |

- Both manufacturing file sets are DRAFT review artifacts.
- Gate F for the evaluation board passes its automated checks. That means the files are internally
  consistent; it is not a manufacturing release.
- No physical-validation evidence exists (Gate G open), and no manufacturing order has been placed.

## Verified evidence

| Check | Compact | Evaluation |
|---|---|---|
| Schematic ERC errors / warnings | 0 / 0 | 0 / 0 |
| Connectivity differences from specification | 0 | 0 |
| PCB footprints | 65 | 68 |
| DRC errors / warnings | 0 / 3 | 0 / 0 |
| Unconnected items / schematic parity findings | 20 / 0 | 0 / 0 |
| Power paths connected (current-flow review) | all | all |
| Export internal consistency | PASS (DRAFT) | PASS (DRAFT) |
| BOM lines / BOM parts / centroid rows | 48 / 53 / 52 | 48 / 53 / 52 |

The generated [validation register](../reports/validation-register.md) controls the gate state. DRC and export
manifests bind the placement, connectivity and parameter sources to the actual CAD bytes, and exported files
carry their own hashes. The two documented DRC omissions are explained in DD-20.

Other checks, all passing:
- 147 Python tests, including real KiCad geometry tests and failure/stale-evidence regressions.
- Firmware: the ATtiny1616 build and 26 host checks.
- 11 behavioural simulations. These models do not replace switching-waveform or fault measurements.
- 21 engineering calculation checks. Estimated efficiency at 4.0 V is 94.59 %, against the owner's ≥ 94 % target
  (DD-26).

## Owner decisions (2026-10-25)

- **Battery polarity:** centre spring = B+, ring = B−, marked on both boards' silkscreen (DD-12). T3.3 checks
  the host.
- **Laser current:** 4.5 A since 2026-10-29 (DD-36; 4.0 A under DD-13 before); the diode-life risk is accepted.
- **Efficiency:** ≥ 94 % accepted as a deviation from the brief's > 95 % (DD-26).
- **Evaluation board first:** the compact board stays a draft until bench data exists (DD-27).

## Review artifacts

Each `manufacturing/pcbway/<variant>/` package contains:
- eleven layer Gerbers;
- separate PTH/NPTH drills and drill maps;
- two BOM formats, centroid data and an iBOM;
- schematic, assembly and fabrication PDFs, and three board renders;
- a stack-up note, a review marker, a fabrication ZIP and the export evidence.

The renders show KiCad library 3D bodies and a generated TPS552882 placeholder. The PowerPAK MOSFETs have no
3D model, so height and enclosure validation remains open. The stack-up is an engineering target awaiting
fabricator confirmation.

The exact router inputs and sessions, with their source hashes, are archived under
`hardware/<variant>/routing/`. The editable native projects and placement sources remain the engineering
record. `package.ps1` creates an explicitly DRAFT review archive with a source/evidence inventory and the
recorded gates.

## Remaining work

1. **Order the evaluation prototype (owner, manually).**
   - Review the package and `engineering/layout-review.md`.
   - Confirm supplier stock and prices, which are partly UNKNOWN.
2. **Bench testing.** Follow the [assembly instructions](assembly.md) and the [bench plan](testing/test-plan.md),
   beginning with a rated dummy load. Gate G needs measured electrical, fault and thermal results on
   assembled hardware.
3. **Compact board.** With the bench data, choose HDI, a placement re-architecture or fewer parts
   ([compact routing assessment](../engineering/compact-feasibility.md)).
4. **HDI via-in-pad for the TPS552882 centre pads (DD-16).** This needs a fabrication quote and an owner decision.

This report does not claim production readiness.
