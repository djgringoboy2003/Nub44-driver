"""Build, route and check the PCB of one variant.

Pipeline (each stage can be run alone with --stage):
  rules   write design rules and net classes into hardware/<variant>/nubm44_driver.kicad_pro
  place   KiCad Python: board outline, footprints from the schematic netlist, placement,
          pre-routed copper, plane zones, Specctra DSN export
  route   FreeRouting 2.5.0 (jar, Java 25) DSN -> SES
  finish  KiCad Python: import SES, add copper pours, fill zones
  drc     kicad-cli DRC with schematic parity -> reports/drc-<variant>.json
  render  layer plots for review -> build/<variant>/*.png
  geometry footprint geometry cache for the fast floorplan checker (floorplan.py)

The schematic netlist (hardware/<variant>/nubm44_driver.net, produced by build_schematic.py) is the
source of footprints and connectivity, so the PCB always follows the schematic.

Usage: .venv\\Scripts\\python.exe automation\\placement\\build_pcb.py --variant compact-22mm [--stage all]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation"))

from nubm44 import netlist, paths, spec as spec_mod  # noqa: E402

PROJECT = "nubm44_driver"
ORIGIN = (100.0, 100.0)            # board centre on the KiCad page, mm
SPEC = ROOT / "engineering/design/connectivity.yaml"

NETCLASSES = [
    # name, clearance, track, via_d, via_drill, nets (spec names)
    # branch tracks only: high-current paths are pours (placement.yaml), so 0.3 mm is enough here
    ("Power", 0.15, 0.30, 0.6, 0.3, ["VBAT", "VOUT", "LD_P", "BAT_SPRING", "SW1", "SW2"]),
    ("Ground", 0.15, 0.30, 0.6, 0.3, ["GND"]),
    ("Sense", 0.15, 0.15, 0.6, 0.3, ["ISP_K", "ISN_K", "FB", "COMP", "COMP_RC", "CS_OUT"]),
]
RULES = {  # PCBWay standard capability with margin (research/pcbway-requirements.md)
    "min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.6, "min_via_annular_width": 0.15,
    "min_through_hole_diameter": 0.3, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.3,
    "min_copper_edge_clearance": 0.3, "min_connection": 0.15, "min_silk_clearance": 0.0,
    "min_text_height": 0.6, "min_text_thickness": 0.1, "min_resolved_spokes": 1,
}


def run(cmd, timeout=1800, **kw):
    t0 = time.time()
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, **kw)
    return r, time.time() - t0


def board_net_names(net_path: Path) -> dict[str, str]:
    """spec net name -> board net name (local labels carry a leading '/')."""
    nets = netlist.read_kicad_netlist(net_path)["nets"]
    return {n.lstrip("/"): n for n in nets}


# ------------------------------------------------------------------------------------ rules
RULE_SEVERITIES = {
    # footprints intentionally differ from the library: silkscreen stripped for density (DD-20)
    "lib_footprint_mismatch": "ignore",
    "missing_courtyard": "warning",
    "track_not_centered_on_via": "warning",
    "footprint_filters_mismatch": "warning",
    "footprint_type_mismatch": "warning",
}


def project_rules(names: dict) -> dict:
    """Design rules and net classes for the .kicad_pro (applied by pcb_builder after every save)."""
    base = {"bus_width": 12, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
            "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "tuning_profile": "", "wire_width": 6}
    classes = [dict(base, name="Default", clearance=0.15, track_width=0.15, via_diameter=0.6, via_drill=0.3,
                    priority=2147483647)]
    patterns = []
    for i, (name, clr, trk, vd, vdr, nets) in enumerate(NETCLASSES):
        classes.append(dict(base, name=name, clearance=clr, track_width=trk, via_diameter=vd, via_drill=vdr,
                            priority=i))
        patterns += [{"netclass": name, "pattern": names[n]} for n in nets if n in names]
    return {
        "rules": RULES,
        "track_widths": [0.0, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5],
        "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}],
        "net_settings": {"classes": classes, "meta": {"version": 5}, "netclass_patterns": patterns,
                         "netclass_assignments": None},
        "rule_severities": RULE_SEVERITIES,
    }


def write_rules(variant: str, names: dict) -> None:
    pro = paths.HARDWARE / variant / f"{PROJECT}.kicad_pro"
    d = json.loads(pro.read_text(encoding="utf-8"))
    pr = project_rules(names)
    ds = d["board"].setdefault("design_settings", {})
    ds.setdefault("rules", {}).update(pr["rules"])
    ds["track_widths"] = pr["track_widths"]
    ds["via_dimensions"] = pr["via_dimensions"]
    ds.setdefault("rule_severities", {}).update(pr["rule_severities"])
    d["net_settings"] = pr["net_settings"]
    temporary = pro.with_suffix(".kicad_pro.tmp")
    temporary.write_text(json.dumps(d, indent=2), encoding="utf-8")
    temporary.replace(pro)


# ------------------------------------------------------------------------------------ job
def lib_dir(nickname: str) -> str:
    if nickname == "nubm44":
        return str(paths.LIBRARIES / "nubm44.pretty")
    return str(paths.kicad_footprints_dir() / f"{nickname}.pretty")


def make_job(variant: str, mode: str) -> dict:
    vdir = paths.HARDWARE / variant
    place = yaml.safe_load((vdir / "placement.yaml").read_text(encoding="utf-8"))
    spec = {p["ref"]: p for p in spec_mod.parts_for(variant)}
    nl = netlist.read_kicad_netlist(vdir / f"{PROJECT}.net")
    names = board_net_names(vdir / f"{PROJECT}.net")
    pin_net = {pin: net for net, pins in nl["nets"].items() for pin in pins}

    def rename(items):
        out = []
        for it in items or []:
            it = dict(it)
            if "net" in it:
                it["net"] = names.get(it["net"], it["net"])
            out.append(it)
        return out

    manual, auto = [], []
    for ref, comp in sorted(nl["components"].items()):
        cfg = place["parts"].get(ref)
        if cfg is None:
            raise SystemExit(f"{ref} has no entry in {variant}/placement.yaml")
        nick, name = comp["footprint"].split(":", 1)
        sp = spec.get(ref, {})
        is_pad_only = not sp.get("in_bom", True)
        item = {
            "ref": ref, "value": comp["value"], "lib_dir": lib_dir(nick), "lib_nick": nick, "fp_name": name,
            "fields": {k: v for k, v in comp["fields"].items()
                       if k not in ("Footprint", "Reference", "Value")},
            "dnp": bool(sp.get("dnp")), "in_bom": not is_pad_only, "in_pos": not is_pad_only and not sp.get("dnp"),
            "pad_nets": {p: pin_net[(ref, p)] for (r, p) in pin_net if r == ref},
            "no_courtyard": cfg.get("no_courtyard", False), "both_sides": cfg.get("both_sides", False),
        }
        if "pos" in cfg:
            item.update(pos=cfg["pos"], side=cfg["side"])
            manual.append(item)
        else:
            a = cfg["auto"]
            item.update(anchor=a["anchor"], side=a["side"])
            if "rots" in a:
                item["rots"] = a["rots"]
            auto.append(item)
    order = {r: i for i, r in enumerate(place["parts"])}
    auto.sort(key=lambda it: order[it["ref"]])
    build = paths.BUILD / variant
    build.mkdir(parents=True, exist_ok=True)
    return {
        "mode": mode, "origin": ORIGIN, "outline": place["board"]["outline"],
        "copper_layers": place["board"]["copper_layers"], "thickness": place["board"]["thickness"],
        "placement_radius": place.get("placement_radius", 1e9), "courtyard_gap": place.get("courtyard_gap", 0.05),
        "placement_box": place.get("placement_box"),
        "keepouts": {s: [[b[0] + ORIGIN[0], b[1] + ORIGIN[1], b[2] + ORIGIN[0], b[3] + ORIGIN[1]] for b in boxes]
                     for s, boxes in (place.get("keepouts") or {}).items()},
        "footprints": manual + auto,
        "tracks": rename(place.get("tracks")), "vias": rename(place.get("vias")),
        "texts": place.get("texts", []),
        "via_fields": rename(place.get("via_fields")),
        "fanout_nets": [names.get(n, n) for n in place.get("fanout_nets", [])],
        "fanout_skip": place.get("fanout_skip", []),
        "vias_post": rename(place.get("vias_post")),
        "tracks_post": rename(place.get("tracks_post")),
        "remove_vias_post": rename(place.get("remove_vias_post")),
        "remove_tracks_post": rename(place.get("remove_tracks_post")),
        "zones_pre": rename(place.get("zones_pre")), "zones_post": rename(place.get("zones_post")),
        **project_rules(names), "drc_report": str(paths.REPORTS / f"drc-{variant}.json"),
        "board": str(vdir / f"{PROJECT}.kicad_pcb"), "dsn": str(build / f"{PROJECT}.dsn"),
        "ses": str(build / f"{PROJECT}.ses"), "report": str(build / "placement-report.json"),
        "geometry": str(build / "fpgeom.json"),
        "project_data": json.loads((vdir / f"{PROJECT}.kicad_pro").read_text(encoding="utf-8")),
    }


def kicad_py(job: dict, variant: str) -> None:
    if job["mode"] == "finish":
        manifest_path = paths.BUILD / variant / "routing-evidence.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        for key in ("dsn", "ses"):
            source = Path(job[key])
            if not source.is_file() or manifest.get(f"{key}_sha256") != hashlib.sha256(source.read_bytes()).hexdigest():
                raise RuntimeError(f"{variant}: missing or stale routing evidence for {key}; rerun routing")
    jf = paths.BUILD / variant / f"job-{job['mode']}.json"
    jf.write_text(json.dumps(job, indent=1), encoding="utf-8")
    r, dt = run([paths.kicad_python(), ROOT / "automation/placement/pcb_builder.py", jf], timeout=900)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit(f"pcb_builder {job['mode']} failed")


# ------------------------------------------------------------------------------------ stages
def stage_route(variant: str, passes: int, timeout: int) -> dict:
    build = paths.BUILD / variant
    dsn, ses = build / f"{PROJECT}.dsn", build / f"{PROJECT}.ses"
    evidence = build / "routing-evidence.json"
    evidence.unlink(missing_ok=True)
    dsn_hash = hashlib.sha256(dsn.read_bytes()).hexdigest()
    if ses.exists():
        ses.unlink()
    cmd = paths.freerouting_cmd() + ["-de", str(dsn), "-do", str(ses),
                                     f"--router.autorouter.max_passes={passes}", "-mt", "1",
                                     "--router.automatic_neckdown=false", "--router.neck_width_um=150",
                                     "--router.fanout.enabled=false",
                                     "--router.layers.routable=true,false,true,true",
                                     "--gui.enabled=false"]
    log = build / "freerouting.log"
    try:
        r, dt = run(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
        log.write_text(decode(exc.stdout) + "\n" + decode(exc.stderr), encoding="utf-8")
        raise RuntimeError(f"FreeRouting timed out after {timeout} s; see {log}") from exc
    log.write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    summary = [ln for ln in r.stdout.splitlines() if "Auto-routing stage completed" in ln or "unrouted" in ln]
    print(f"FreeRouting rc={r.returncode} in {dt:.0f} s; {summary[-1] if summary else 'no summary line'}")
    if r.returncode != 0 or not ses.is_file() or ses.stat().st_size == 0:
        raise RuntimeError(f"FreeRouting failed ({r.returncode}) or produced no session; see {log}")
    if hashlib.sha256(dsn.read_bytes()).hexdigest() != dsn_hash:
        raise RuntimeError("DSN changed during routing; rerun routing against the current placement")
    evidence.write_text(json.dumps({
        "dsn_sha256": dsn_hash,
        "ses_sha256": hashlib.sha256(ses.read_bytes()).hexdigest(),
        "command": [str(c) for c in cmd],
    }, indent=1) + "\n", encoding="utf-8")
    return {"rc": r.returncode, "seconds": round(dt, 1), "summary": summary[-1] if summary else ""}


def stage_drc(variant: str) -> dict:
    board = paths.HARDWARE / variant / f"{PROJECT}.kicad_pcb"
    out = paths.REPORTS / f"drc-{variant}.json"
    evidence = paths.REPORTS / f"drc-{variant}-evidence.json"
    # Never accept a previous report after a failed CLI invocation.
    out.unlink(missing_ok=True)
    evidence.unlink(missing_ok=True)
    sources = [board.parent / "placement.yaml", ROOT / "engineering/design/connectivity.yaml",
               ROOT / "engineering/design/parameters.yaml"]
    source_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    cmd = [paths.kicad_cli(), "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity",
           "--refill-zones", "--save-board", "-o", out, board]
    r, _ = run(cmd)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"KiCad DRC failed ({r.returncode}): {r.stdout}\n{r.stderr}")
    d = json.loads(out.read_text(encoding="utf-8"))
    for key in ("violations", "unconnected_items", "schematic_parity"):
        if not isinstance(d.get(key), list):
            raise ValueError(f"Malformed DRC report: missing {key} array")
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest for p, digest in source_hashes.items()):
        raise RuntimeError("Authoritative design source changed during DRC; rebuild and rerun validation")
    inputs = [board, board.with_suffix(".kicad_sch"), board.with_suffix(".kicad_pro"), *sources]
    evidence.write_text(json.dumps({
        "report_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "inputs": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        "schematic_parity": True, "severity_all": True,
    }, indent=1) + "\n", encoding="utf-8")
    viol = d.get("violations", [])
    res = {
        "errors": sum(v["severity"] == "error" for v in viol),
        "warnings": sum(v["severity"] == "warning" for v in viol),
        "unconnected": len(d.get("unconnected_items", [])),
        "parity": len(d.get("schematic_parity", [])),
        "by_type": {},
    }
    for v in viol:
        res["by_type"][v["type"]] = res["by_type"].get(v["type"], 0) + 1
    print(f"DRC: errors {res['errors']}, warnings {res['warnings']}, unconnected {res['unconnected']}, "
          f"parity issues {res['parity']}; {res['by_type']}")
    return res


def stage_render(variant: str) -> None:
    board = paths.HARDWARE / variant / f"{PROJECT}.kicad_pcb"
    out = paths.BUILD / variant
    sets = {"top": ("F.Cu,F.Silkscreen,F.Courtyard,F.Fab,Edge.Cuts", False),
            "bottom": ("B.Cu,B.Silkscreen,B.Courtyard,B.Fab,Edge.Cuts", True),
            "in1": ("In1.Cu,Edge.Cuts", False), "in2": ("In2.Cu,Edge.Cuts", False)}
    for name, (layers, mirror) in sets.items():
        svg = out / f"{name}.svg"
        cmd = [paths.kicad_cli(), "pcb", "export", "svg", "--mode-single", "--page-size-mode", "2",
               "--exclude-drawing-sheet", "-l", layers, "-o", svg, board]
        if mirror:
            cmd.insert(5, "--mirror")
        run(cmd)
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(svg))
            doc[0].get_pixmap(dpi=1600).save(str(out / f"{name}.png"))
        except Exception as e:  # pragma: no cover
            print("render failed:", e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="compact-22mm")
    ap.add_argument("--stage", default="all", choices=["all", "rules", "place", "route", "finish", "cleanup", "drc", "render", "geometry"])
    ap.add_argument("--passes", type=int, default=30)
    ap.add_argument("--route-timeout", type=int, default=1800)
    args = ap.parse_args()
    v = args.variant
    if (paths.HARDWARE / v / "MANUAL_EDITS").exists() and args.stage in ("all", "place", "finish"):
        raise SystemExit(f"{v}: MANUAL_EDITS present; refusing to regenerate the board")
    names = board_net_names(paths.HARDWARE / v / f"{PROJECT}.net")
    if args.stage == "geometry":
        kicad_py(make_job(v, "geometry"), v)
        return 0
    summary_path = paths.REPORTS / f"pcb-{v}.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    if args.stage in ("all", "place"):
        summary = {}
    if args.stage in ("all", "rules", "place"):
        write_rules(v, names)
    if args.stage in ("all", "place"):
        kicad_py(make_job(v, "place"), v)
    if args.stage in ("all", "route"):
        summary["route"] = stage_route(v, args.passes, args.route_timeout)
    if args.stage in ("all", "finish"):
        kicad_py(make_job(v, "finish"), v)
    if args.stage in ("all", "drc"):
        summary["drc"] = stage_drc(v)
    if args.stage in ("all", "cleanup"):
        kicad_py(make_job(v, "cleanup"), v)
        summary["drc"] = stage_drc(v)
    if args.stage in ("all", "render", "place"):
        stage_render(v)
    summary_path.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
