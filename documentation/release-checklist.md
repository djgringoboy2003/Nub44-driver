# Release checklist

No tool in this repository places an order or uploads manufacturing data. Each level below is computed by
`automation/validation/validate.py` into `reports/release-readiness.md`; this checklist adds the human steps around it.

## A. Before asking for a prototype quote (PROTOTYPE_CANDIDATE)

- [ ] `validate.py` exits 0 and `reports/release-readiness.md` shows the board at **PROTOTYPE_CANDIDATE**:
  - ERC 0/0, netlist equals `connectivity.yaml`, DRC 0 errors / 0 warnings / 0 unconnected / 0 parity;
  - layout review and export package current for the board; package class `DRAFT_REVIEW` (never
    `DRAFT_REVIEW_INCOMPLETE_BOARD`);
  - calculation, simulation (SIM-01…11), firmware and sourcing evidence current and passing;
  - human reviews FP-U1, FP-L1, FP-POWERPAK, FP-RS1 and ORIENT recorded as DONE with reviewer, date and evidence.
- [ ] Firmware HEX built from the commit being ordered (`reports/firmware-evidence.json`), fuse values noted.
- [ ] `sourcing/sourcing-check.md` warnings read; UNKNOWN stock and prices confirmed with the supplier; no
      substitution of a part whose footprint, pin mapping or ratings have not been reviewed.
- [ ] Battery polarity labels checked against the host (T3.3).
- [ ] Owner decisions pending (see the dashboard, "Decisions and reviews required") either taken or knowingly
      deferred for a prototype.

## B. Placing the prototype order (owner, by hand)

- [ ] Upload the exact package files listed in `manufacturing/pcbway/<variant>/reports/export-check.json`; keep the
      quote and the fabricator's DFM/assembly questions with the order record.
- [ ] Record the order (date, fabricator order number, package SHA-256 of `<variant>-gerbers.zip`) in PROGRESS.md.

## C. Bench validation (Gate G)

- [ ] Program firmware and fuses; read the fuses back (T0.4).
- [ ] Run the bench plan in order with a rated dummy load; record every test with `automation/bench/bench.py`.
- [ ] `reports/bench-report.md` shows Gate G PASS for the board; requirement statuses updated to VERIFIED-TEST.

## D. Manufacturing release (MANUFACTURING_RELEASE)

- [ ] Gate G PASS for this variant from MEASURED records.
- [ ] No finding left in `pending_disposition` of `engineering/known-limitations.yaml`.
- [ ] PCBWAY-DFM review recorded as DONE in `engineering/release/design-reviews.yaml`.
- [ ] Signed approval file `manufacturing/approvals/<variant>.yaml` with `approver`, `date`,
      `level: MANUFACTURING_RELEASE`, `git_commit` and the SHA-256 of the fabrication ZIP, BOM and CPL of the exact
      package; `validate.py` checks that the hashes match.
- [ ] `reports/release-readiness.md` shows **MANUFACTURING_RELEASE**.
