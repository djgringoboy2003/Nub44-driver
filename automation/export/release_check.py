"""Per-board release readiness (audit AUD-MFG-01/02, AUD-VAL-06). Never places an order.

Levels, each requiring everything below it:

  DRAFT_REVIEW           the PCBWay package exists and is internally consistent (files, BOM, centroid, hashes);
                         it may describe an incomplete board and is for review only.
  PROTOTYPE_CANDIDATE    the CAD is complete and current (ERC, netlist parity, 0 unconnected, DRC clean, layout
                         review and export bound to the current sources); calculation, simulation (SIM-01..11),
                         firmware and sourcing checks pass; every required human review (engineering/release/design-reviews.yaml)
                         is recorded as DONE. The owner may then order a prototype by hand.
  MANUFACTURING_RELEASE  additionally: Gate G bench evidence passes for this variant (reports/bench-summary.json),
                         no finding awaits disposition, the fabricator DFM review is recorded, and a signed approval
                         file (manufacturing/approvals/<variant>.yaml) matches the exact package hashes.

The level is computed from validation-register entries; this module adds no PASS of its own.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

LEVELS = ("NONE", "DRAFT_REVIEW", "PROTOTYPE_CANDIDATE", "MANUFACTURING_RELEASE")
CAD_CHECKS = ("ERC", "NET", "ROUTE", "PARITY", "DRC", "LAYOUT", "EXPORT")
COMMON_CHECKS = ("VAL-CALC-EVID", "VAL-SIM-EVID", "VAL-FW-TEST", "VAL-FW-BUILD", "VAL-SRC")
SIM_GATE_IDS = tuple(f"VAL-SIM-{i:02d}" for i in range(1, 12))
APPROVAL_FIELDS = ("approver", "date", "level", "git_commit", "gerber_zip_sha256", "bom_sha256", "cpl_sha256")


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def _yaml(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def review_blockers(root: Path, variant: str, level: str) -> list[str]:
    data = _yaml(root / "engineering/release/design-reviews.yaml")
    if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
        return ["design-review register missing or malformed (engineering/release/design-reviews.yaml)"]
    out = []
    for r in data["reviews"]:
        if not isinstance(r, dict) or r.get("level") != level or variant not in (r.get("variants") or []):
            continue
        done = r.get("status") == "DONE" and all(r.get(k) for k in ("reviewer", "date", "evidence"))
        if not done:
            out.append(f"human review {r.get('id')} not recorded as DONE")
    return out


def approval_blockers(root: Path, variant: str) -> list[str]:
    path = root / "manufacturing" / "approvals" / f"{variant}.yaml"
    data = _yaml(path)
    if not isinstance(data, dict):
        return [f"no signed approval file manufacturing/approvals/{variant}.yaml"]
    out = [f"approval file lacks {k}" for k in APPROVAL_FIELDS if not data.get(k)]
    if data.get("level") != "MANUFACTURING_RELEASE":
        out.append("approval file is not for MANUFACTURING_RELEASE")
    pkg = root / "manufacturing" / "pcbway" / variant
    for key, rel in (("gerber_zip_sha256", f"{variant}-gerbers.zip"), ("bom_sha256", "assembly/BOM_PCBWay_template.csv"),
                     ("cpl_sha256", "assembly/CPL_PCBWay.csv")):
        if data.get(key) and data.get(key) != _sha(pkg / rel):
            out.append(f"approval {key} does not match the current package ({rel})")
    return out


def bench_blockers(root: Path, variant: str) -> list[str]:
    try:
        summary = json.loads((root / "reports" / "bench-summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["no bench evidence summary (reports/bench-summary.json); Gate G open"]
    v = (summary.get("variants") or {}).get(variant) if isinstance(summary, dict) else None
    if not isinstance(v, dict):
        return [f"no bench evidence for {variant}; Gate G open"]
    if v.get("gate_g") != "PASS":
        missing = v.get("not_passed") or []
        return [f"Gate G bench evidence incomplete for {variant}: {len(missing)} required tests not PASS"
                + (f" (e.g. {', '.join(missing[:5])})" if missing else "")]
    return []


def readiness(variant: str, entries: list[dict], root: Path, pending: list[str]) -> dict:
    st = {}
    for e in entries:
        st.setdefault(e["id"], []).append(e)

    def check(eid: str) -> str | None:
        found = st.get(eid, [])
        if len(found) != 1:
            return f"{eid}: {'missing' if not found else 'duplicated'}"
        e = found[0]
        return None if e["status"] == "PASS" else f"{eid}: {e['status']} ({str(e.get('detail', ''))[:140]})"

    blockers = {lvl: [] for lvl in LEVELS[1:]}
    if (b := check(f"VAL-EXPORT-{variant}")):
        blockers["DRAFT_REVIEW"].append(b)
    ids = [f"VAL-{c}-{variant}" for c in CAD_CHECKS] + list(COMMON_CHECKS) + list(SIM_GATE_IDS)
    ids += sorted(k for k in st if k.startswith("VAL-CALC-") and k != "VAL-CALC-EVID")
    blockers["PROTOTYPE_CANDIDATE"] += [b for b in map(check, ids) if b]
    blockers["PROTOTYPE_CANDIDATE"] += review_blockers(root, variant, "PROTOTYPE_CANDIDATE")
    blockers["MANUFACTURING_RELEASE"] += bench_blockers(root, variant)
    blockers["MANUFACTURING_RELEASE"] += [f"finding awaiting owner disposition: {p}" for p in pending]
    blockers["MANUFACTURING_RELEASE"] += review_blockers(root, variant, "MANUFACTURING_RELEASE")
    blockers["MANUFACTURING_RELEASE"] += approval_blockers(root, variant)
    level = "NONE"
    for lvl in LEVELS[1:]:
        if blockers[lvl]:
            break
        level = lvl
    return {"variant": variant, "level": level, "blockers": blockers,
            "next_level": next((lvl for lvl in LEVELS[1:] if blockers[lvl]), None),
            "manufacturing_release": level == "MANUFACTURING_RELEASE", "orders_placed_by_tooling": False}


def write_report(results: dict[str, dict], reports: Path, date: str) -> None:
    (reports / "release-readiness.json").write_text(json.dumps({"date": date, "variants": results}, indent=1) + "\n",
                                                    encoding="utf-8")
    lines = ["# Release readiness", "", f"Generated by `automation/validation/validate.py` on {date} from the validation "
             "register. No tool places an order; MANUFACTURING_RELEASE also needs bench evidence and a signed approval.", "",
             "| Variant | Level | Next level | Blockers to the next level |", "|---|---|---|---|"]
    for v, r in results.items():
        nxt = r["next_level"]
        lines.append(f"| {v} | **{r['level']}** | {nxt or '-'} | {len(r['blockers'][nxt]) if nxt else 0} |")
    for v, r in results.items():
        lines += ["", f"## {v}", ""]
        for lvl in LEVELS[1:]:
            b = r["blockers"][lvl]
            lines.append(f"- **{lvl}:** " + ("met" if not b else f"{len(b)} blocker(s)"))
            lines += [f"  - {x}" for x in b]
    (reports / "release-readiness.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
