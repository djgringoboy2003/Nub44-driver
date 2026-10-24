"""Load engineering/design/connectivity.yaml and resolve it for one PCB variant.

Per-part keys honoured:
  variants: [..]                      part exists only in the listed variants (default: all)
  footprint_eval / mpn_eval / mfr_eval  overrides used by the evaluation-board variant
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "engineering/design/connectivity.yaml"
VARIANTS = ("compact-22mm", "evaluation-board")
EVAL_OVERRIDES = {"footprint": "footprint_eval", "mpn": "mpn_eval", "mfr": "mfr_eval"}


@lru_cache(maxsize=None)
def load() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def parts_for(variant: str) -> list[dict]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant}")
    out = []
    for p in load()["parts"]:
        if variant not in p.get("variants", VARIANTS):
            continue
        q = dict(p)
        if variant == "evaluation-board":
            for key, ov in EVAL_OVERRIDES.items():
                if ov in p:
                    q[key] = p[ov]
        out.append(q)
    return out
