"""KiCad-side entry point for the budget board: the shared A/B builder (automation/placement/pcb_builder.py),
unchanged, with one KiCad 10.0.6 workaround applied in this process only (AGENTS.md: the A/B builders are
not edited for budget work).

pcb_builder.strip_silkscreen removes footprint silkscreen items. On the budget board, once the Python proxies
of the removed items are garbage-collected after SetFPID, KiCad 10.0.6's SWIG type table breaks (Reference()
returns a bare SwigPyObject and later FootprintLoad calls fail). Holding the proxies until the process exits
avoids it; geometry is unaffected.

  usage: <KiCad python> automation/budget/pcb_builder_budget.py <job.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "placement"))

import pcbnew  # noqa: E402
import pcb_builder  # noqa: E402

_REMOVED_ITEMS = []  # keeps the SWIG proxies of removed silkscreen items alive


def strip_silkscreen(fp):
    """Same result as pcb_builder.strip_silkscreen; the removed items' proxies are kept (see module doc)."""
    removed = [item for item in fp.GraphicalItems() if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
    for item in removed:
        fp.Remove(item)
    _REMOVED_ITEMS.extend(removed)


pcb_builder.strip_silkscreen = strip_silkscreen

if __name__ == "__main__":
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    {"place": pcb_builder.mode_place, "finish": pcb_builder.mode_finish, "cleanup": pcb_builder.mode_cleanup,
     "geometry": pcb_builder.mode_geometry}[job["mode"]](job)
