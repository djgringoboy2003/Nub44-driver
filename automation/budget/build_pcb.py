"""Build, route and check the budget-2s PCB with the shared KiCad-side builder (pcb_builder.py).

Sources: hardware/budget-2s/placement.yaml and the budget schematic netlist (build_schematic.py).
Stages: rules, place, route (FreeRouting jar), finish (SES import, source pours), drc (kicad-cli with
schematic parity), render, archive (store the accepted router session in hardware/budget-2s/routing/ with
source hashes) and restore (place, re-apply the archived session, finish, drc; no re-routing). KiCad's
Specctra export orders pours by UUID, so every place gives FreeRouting a different order and result: the
archive is what makes the routed board reproducible. The A/B pipeline module is imported for shared helpers
only; its variants, net classes, files and evidence are never touched, and the KiCad-side builder runs
through automation/budget/pcb_builder_budget.py.

Usage: .venv\\Scripts\\python.exe automation\\budget\\build_pcb.py
       [--stage all|rules|place|route|finish|drc|render|archive|restore]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import kicad_lib, netlist, paths  # noqa: E402
from nubm44.variants import BUDGET_VARIANT, sources_for  # noqa: E402

_ab_spec = importlib.util.spec_from_file_location("ab_build_pcb", ROOT / "automation/placement/build_pcb.py")
ab = importlib.util.module_from_spec(_ab_spec)
_ab_spec.loader.exec_module(ab)

SOURCES = sources_for(BUDGET_VARIANT)
PROJECT = "nubm44_budget2s"
VDIR = paths.HARDWARE / BUDGET_VARIANT
BUILD = paths.BUILD / BUDGET_VARIANT
REPORTS = paths.REPORTS / BUDGET_VARIANT
BOARD = VDIR / f"{PROJECT}.kicad_pcb"
ROUTING = VDIR / "routing"
SESSION_FILES = (f"{PROJECT}.dsn", f"{PROJECT}.ses", "routing-evidence.json")
NETLIST = VDIR / f"{PROJECT}.net"

# name, clearance, track, via_d, via_drill, nets. High-current paths are F.Cu pours (placement.yaml);
# these widths apply to router branches only.
NETCLASSES = [
    ("Power", 0.15, 0.3, 0.6, 0.3, ["VBAT_IN", "VBAT_F", "VBAT_P", "PH", "VBUCK", "VSH", "LASER_P"]),
    ("Ground", 0.15, 0.25, 0.6, 0.3, ["GND"]),
    ("Sense", 0.15, 0.15, 0.6, 0.3, ["VSENSE", "COMP", "COMP_RC", "CS_OUT", "OC_LIM", "BOOT", "EN", "SS", "RT", "PWRGD"]),
]


def project_rules(names: dict) -> dict:
    ab.NETCLASSES = NETCLASSES
    return ab.project_rules(names)


def write_rules(names: dict) -> None:
    pro = VDIR / f"{PROJECT}.kicad_pro"
    d = json.loads(pro.read_text(encoding="utf-8"))
    pr = project_rules(names)
    ds = d.setdefault("board", {}).setdefault("design_settings", {})
    ds.setdefault("rules", {}).update(pr["rules"])
    ds["track_widths"], ds["via_dimensions"] = pr["track_widths"], pr["via_dimensions"]
    ds.setdefault("rule_severities", {}).update(pr["rule_severities"])
    d["net_settings"] = pr["net_settings"]
    tmp = pro.with_suffix(".kicad_pro.tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    tmp.replace(pro)


def lib_dir(nickname: str) -> str:
    if nickname == kicad_lib.BUDGET_LIB:
        return str(kicad_lib.BUDGET_LIB_DIR / f"{kicad_lib.BUDGET_LIB}.pretty")
    return ab.lib_dir(nickname)


def make_job(mode: str) -> dict:
    place = yaml.safe_load((VDIR / "placement.yaml").read_text(encoding="utf-8"))
    spec = {p["ref"]: p for p in yaml.safe_load(SOURCES.connectivity.read_text(encoding="utf-8"))["parts"]}
    nl = netlist.read_kicad_netlist(NETLIST)
    names = ab.board_net_names(NETLIST)
    pin_net = {pin: net for net, pins in nl["nets"].items() for pin in pins}
    rename = lambda items: [dict(it, net=names.get(it["net"], it["net"])) if "net" in it else dict(it) for it in items or []]
    manual, auto = [], []
    for ref, comp in sorted(nl["components"].items()):
        cfg = place["parts"].get(ref)
        if cfg is None:
            raise SystemExit(f"{ref} has no entry in hardware/budget-2s/placement.yaml")
        nick, name = comp["footprint"].split(":", 1)
        pad_only = not spec.get(ref, {}).get("in_bom", True)
        item = {"ref": ref, "value": comp["value"], "lib_dir": lib_dir(nick), "lib_nick": nick, "fp_name": name,
                "fields": {k: v for k, v in comp["fields"].items() if k not in ("Footprint", "Reference", "Value")},
                "dnp": False, "in_bom": not pad_only, "in_pos": not pad_only,
                "pad_nets": {p: pin_net[(ref, p)] for (r, p) in pin_net if r == ref},
                "no_courtyard": cfg.get("no_courtyard", False), "both_sides": cfg.get("both_sides", False)}
        if "pos" in cfg:
            item.update(pos=cfg["pos"], side=cfg["side"])
            manual.append(item)
        else:
            a = cfg["auto"]
            item.update(anchor=a["anchor"], side=a["side"], **({"rots": a["rots"]} if "rots" in a else {}))
            auto.append(item)
    order = {r: i for i, r in enumerate(place["parts"])}
    auto.sort(key=lambda it: order[it["ref"]])
    BUILD.mkdir(parents=True, exist_ok=True)
    o = ab.ORIGIN
    return {
        "mode": mode, "origin": o, "outline": place["board"]["outline"],
        "copper_layers": place["board"]["copper_layers"], "thickness": place["board"]["thickness"],
        "placement_radius": 1e9, "courtyard_gap": place.get("courtyard_gap", 0.1),
        "placement_box": place.get("placement_box"),
        "keepouts": {s: [[b[0] + o[0], b[1] + o[1], b[2] + o[0], b[3] + o[1]] for b in boxes]
                     for s, boxes in (place.get("keepouts") or {}).items()},
        "footprints": manual + auto,
        "tracks": rename(place.get("tracks")), "vias": rename(place.get("vias")),
        "grid_tracks": [], "grid_vias": [], "texts": place.get("texts", []),
        "via_fields": rename(place.get("via_fields")),
        "fanout_nets": [names.get(n, n) for n in place.get("fanout_nets", [])],
        "fanout_skip": place.get("fanout_skip", []),
        "vias_post": rename(place.get("vias_post")), "tracks_post": rename(place.get("tracks_post")),
        "remove_vias_post": rename(place.get("remove_vias_post")),
        "remove_tracks_post": rename(place.get("remove_tracks_post")),
        "zones_pre": rename(place.get("zones_pre")), "zones_post": rename(place.get("zones_post")),
        "router_keepouts": rename(place.get("router_keepouts")),
        **project_rules(names), "drc_report": str(REPORTS / "drc.json"),
        "board": str(BOARD), "dsn": str(BUILD / f"{PROJECT}.dsn"), "ses": str(BUILD / f"{PROJECT}.ses"),
        "report": str(BUILD / "placement-report.json"), "geometry": str(BUILD / "fpgeom.json"),
        "project_data": json.loads((VDIR / f"{PROJECT}.kicad_pro").read_text(encoding="utf-8")),
    }


def kicad_py(job: dict) -> None:
    if job["mode"] == "finish":
        manifest_path = BUILD / "routing-evidence.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        for key in ("dsn", "ses"):
            src = Path(job[key])
            if not src.is_file() or manifest.get(f"{key}_sha256") != hashlib.sha256(src.read_bytes()).hexdigest():
                raise RuntimeError(f"budget-2s: missing or stale routing evidence for {key}; rerun routing")
    jf = BUILD / f"job-{job['mode']}.json"
    jf.write_text(json.dumps(job, indent=1), encoding="utf-8")
    r, _ = ab.run([paths.kicad_python(), ROOT / "automation/budget/pcb_builder_budget.py", jf], timeout=900)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit(f"pcb_builder {job['mode']} failed")


def stage_route(passes: int, timeout: int) -> dict:
    dsn, ses, ev = BUILD / f"{PROJECT}.dsn", BUILD / f"{PROJECT}.ses", BUILD / "routing-evidence.json"
    ev.unlink(missing_ok=True)
    ses.unlink(missing_ok=True)
    dsn_hash = hashlib.sha256(dsn.read_bytes()).hexdigest()
    cmd = paths.freerouting_cmd() + ["-de", str(dsn), "-do", str(ses), f"--router.autorouter.max_passes={passes}",
                                     "-mt", "1", "--router.automatic_neckdown=false", "--router.neck_width_um=150",
                                     "--router.fanout.enabled=false", "--router.layers.routable=true,false,true,true",
                                     "--gui.enabled=false"]
    r, dt = ab.run(cmd, timeout=timeout)
    (BUILD / "freerouting.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    summary = [ln for ln in r.stdout.splitlines() if "Auto-routing stage completed" in ln or "unrouted" in ln]
    print(f"FreeRouting rc={r.returncode} in {dt:.0f} s; {summary[-1] if summary else 'no summary line'}")
    if r.returncode != 0 or not ses.is_file() or ses.stat().st_size == 0:
        raise RuntimeError(f"FreeRouting failed ({r.returncode}) or produced no session; see {BUILD / 'freerouting.log'}")
    if hashlib.sha256(dsn.read_bytes()).hexdigest() != dsn_hash:
        raise RuntimeError("DSN changed during routing")
    ev.write_text(json.dumps({"dsn_sha256": dsn_hash, "ses_sha256": hashlib.sha256(ses.read_bytes()).hexdigest(),
                              "command": [str(c) for c in cmd]}, indent=1) + "\n", encoding="utf-8")
    return {"rc": r.returncode, "seconds": round(dt, 1)}


def stage_drc() -> dict:
    out, ev = REPORTS / "drc.json", REPORTS / "drc-evidence.json"
    REPORTS.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    ev.unlink(missing_ok=True)
    sources = [VDIR / "placement.yaml", SOURCES.connectivity, SOURCES.parameters]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    r, _ = ab.run([paths.kicad_cli(), "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity",
                   "--refill-zones", "--save-board", "-o", out, BOARD])
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"KiCad DRC failed ({r.returncode}): {r.stdout}\n{r.stderr}")
    d = json.loads(out.read_text(encoding="utf-8"))
    for key in ("violations", "unconnected_items", "schematic_parity"):
        if not isinstance(d.get(key), list):
            raise ValueError(f"Malformed DRC report: missing {key} array")
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != h for p, h in before.items()):
        raise RuntimeError("Budget design source changed during DRC")
    inputs = [BOARD, BOARD.with_suffix(".kicad_sch"), BOARD.with_suffix(".kicad_pro"), *sources]
    ev.write_text(json.dumps({"report_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                              "inputs": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in inputs},
                              "schematic_parity": True, "severity_all": True}, indent=1) + "\n", encoding="utf-8")
    viol = d["violations"]
    res = {"errors": sum(v["severity"] == "error" for v in viol), "warnings": sum(v["severity"] == "warning" for v in viol),
           "unconnected": len(d["unconnected_items"]), "parity": len(d["schematic_parity"]), "by_type": {}}
    for v in viol:
        res["by_type"][v["type"]] = res["by_type"].get(v["type"], 0) + 1
    print(f"DRC: errors {res['errors']}, warnings {res['warnings']}, unconnected {res['unconnected']}, "
          f"parity issues {res['parity']}; {res['by_type']}")
    return res


def routing_sources() -> dict:
    """Files whose change invalidates an archived router session (geometry, nets, lands, rules)."""
    files = [VDIR / "placement.yaml", SOURCES.connectivity, NETLIST, Path(__file__),
             *sorted((kicad_lib.BUDGET_LIB_DIR / f"{kicad_lib.BUDGET_LIB}.pretty").glob("*.kicad_mod"))]
    # the netlist's export timestamp changes on every schematic build without changing a net
    content = lambda f: re.sub(rb'\(date "[^"]*"\)', b"", f.read_bytes()) if f == NETLIST else f.read_bytes()
    return {f.relative_to(ROOT).as_posix(): hashlib.sha256(content(f)).hexdigest() for f in files}


def stage_archive() -> None:
    """Keep the session behind a clean, current DRC so `restore` can rebuild the board without routing."""
    res = stage_drc()
    if (res["errors"], res["warnings"], res["unconnected"], res["parity"]) != (0, 0, 0, 0):
        raise SystemExit(f"budget-2s: DRC not clean ({res}); refusing to archive this routing")
    ROUTING.mkdir(parents=True, exist_ok=True)
    for name in SESSION_FILES:
        shutil.copyfile(BUILD / name, ROUTING / name)
    (ROUTING / "checkpoint-source.json").write_text(json.dumps(
        {"sources": routing_sources(),
         "session": {n: hashlib.sha256((ROUTING / n).read_bytes()).hexdigest() for n in SESSION_FILES},
         "note": "Re-apply with build_pcb.py --stage restore. A new routing replaces this whole checkpoint."},
        indent=2) + "\n", encoding="utf-8")
    print(f"archived router session in {ROUTING.relative_to(ROOT).as_posix()}")


def stage_restore() -> dict:
    cp = json.loads((ROUTING / "checkpoint-source.json").read_text(encoding="utf-8"))
    changed = [k for k, v in routing_sources().items() if cp["sources"].get(k) != v]
    changed += [k for k in cp["sources"] if k not in routing_sources()]
    if changed:
        raise SystemExit(f"budget-2s: sources changed since the archived routing ({', '.join(changed)}); "
                         "route again (place, route, finish, drc) and archive")
    for n, digest in cp["session"].items():
        if hashlib.sha256((ROUTING / n).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"budget-2s: archived {n} does not match its checkpoint")
    write_rules(ab.board_net_names(NETLIST))
    kicad_py(make_job("place"))
    for name in SESSION_FILES:  # the archived DSN replaces the re-exported one (same geometry, other order)
        shutil.copyfile(ROUTING / name, BUILD / name)
    kicad_py(make_job("finish"))
    return stage_drc()


def stage_render() -> None:
    sets = {"top": ("F.Cu,F.Silkscreen,F.Courtyard,F.Fab,Edge.Cuts", False),
            "bottom": ("B.Cu,B.Silkscreen,Edge.Cuts", True), "in1": ("In1.Cu,Edge.Cuts", False),
            "in2": ("In2.Cu,Edge.Cuts", False)}
    for name, (layers, mirror) in sets.items():
        svg = BUILD / f"{name}.svg"
        cmd = [paths.kicad_cli(), "pcb", "export", "svg", "--mode-single", "--page-size-mode", "2",
               "--exclude-drawing-sheet", "-l", layers, "-o", svg, BOARD]
        if mirror:
            cmd.insert(5, "--mirror")
        ab.run(cmd)
        import pymupdf
        pymupdf.open(str(svg))[0].get_pixmap(dpi=600).save(str(BUILD / f"{name}.png"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["all", "rules", "place", "route", "finish", "drc", "render", "archive", "restore"])
    ap.add_argument("--passes", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()
    if (VDIR / "MANUAL_EDITS").exists() and args.stage in ("all", "place", "finish", "restore"):
        raise SystemExit("budget-2s: MANUAL_EDITS present; refusing to regenerate the board")
    names = ab.board_net_names(NETLIST)
    if args.stage in ("all", "rules", "place"):
        write_rules(names)
    if args.stage in ("all", "place"):
        kicad_py(make_job("place"))
    if args.stage in ("all", "route"):
        stage_route(args.passes, args.timeout)
    if args.stage in ("all", "finish"):
        kicad_py(make_job("finish"))
    if args.stage in ("all", "drc"):
        res = stage_drc()
        if args.stage == "drc" or args.stage == "all":
            return 0 if res["errors"] == 0 and res["unconnected"] == 0 and res["parity"] == 0 else 1
    if args.stage == "render":
        stage_render()
    if args.stage == "archive":
        stage_archive()
    if args.stage == "restore":
        res = stage_restore()
        return 0 if res["errors"] == 0 and res["unconnected"] == 0 and res["parity"] == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
