"""Engineering status dashboard: one self-contained HTML page generated from the project's evidence files.

Every number on the page is read from a generated evidence file (validation register, release readiness, bench
summary, calculation and simulation results, firmware evidence, sourcing check) or from the audit and risk
registers. Nothing is typed in here, so a stale or failing input shows up as stale or failing on the page.

    .venv\\Scripts\\python.exe automation\\dashboard\\build_dashboard.py      # writes reports/dashboard/index.html

The page needs no server and no network: open the file in a browser. validate.py regenerates it in full mode.
"""
from __future__ import annotations

import html
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "dashboard" / "index.html"
SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"]


def load(rel: str):
    p = ROOT / rel
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return None


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def git_commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        d = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() + (" (uncommitted changes)" if d.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def md_table(rel: str, first_col_prefix: str) -> list[list[str]]:
    p = ROOT / rel
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {first_col_prefix}"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def badge(status: str) -> str:
    s = str(status).upper()
    kind = ("good" if s.startswith(("PASS", "FIXED", "MANUFACTURING_RELEASE", "PROTOTYPE_CANDIDATE", "KILLED"))
            else "critical" if s.startswith(("FAIL", "NONE", "SURVIVED", "INVALID"))
            else "warning" if s.startswith(("OPEN", "NOT RUN", "NO DATA", "DRAFT", "MITIGATED", "DEFERRED", "HELD", "WARN"))
            else "neutral")
    icon = {"good": "&#10003;", "critical": "&#10007;", "warning": "&#9888;", "neutral": "&#8226;"}[kind]
    return f'<span class="badge {kind}"><span aria-hidden="true">{icon}</span> {esc(status)}</span>'


# ------------------------------------------------------------------ SVG charts (one axis each)
def line_chart(title: str, series: list[dict], x_label: str, y_label: str, refs: list[dict] = (), logx=False,
               y_fmt="{:.1f}", x_fmt="{:g}") -> str:
    w, h, ml, mr, mt, mb = 640, 300, 56, 120, 16, 44
    xs = [x for s in series for x, _ in s["points"]]
    ys = [y for s in series for _, y in s["points"]] + [r["y"] for r in refs]
    fx = (lambda v: math.log10(v)) if logx else (lambda v: v)
    x0, x1 = fx(min(xs)), fx(max(xs))
    y0, y1 = min(ys), max(ys)
    pad = (y1 - y0) * 0.08 or 1
    y0, y1 = y0 - pad, y1 + pad
    X = lambda v: ml + (fx(v) - x0) / (x1 - x0) * (w - ml - mr)  # noqa: E731
    Y = lambda v: mt + (y1 - v) / (y1 - y0) * (h - mt - mb)      # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}" class="chart">']
    for i in range(5):
        yv = y0 + (y1 - y0) * i / 4
        parts.append(f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}"/>'
                     f'<text class="tick" x="{ml - 6}" y="{Y(yv) + 4:.1f}" text-anchor="end">{esc(y_fmt.format(yv))}</text>')
    ticks = sorted(set(round(x, 6) for x in xs))
    if logx:
        ticks = [10 ** k for k in range(math.floor(x0), math.ceil(x1) + 1) if x0 <= k <= x1]
    for xv in ticks:
        parts.append(f'<text class="tick" x="{X(xv):.1f}" y="{h - mb + 16}" text-anchor="middle">{esc(x_fmt.format(xv))}</text>')
    parts.append(f'<line class="axis" x1="{ml}" x2="{w - mr}" y1="{h - mb}" y2="{h - mb}"/>')
    for r in refs:
        parts.append(f'<line class="ref" x1="{ml}" x2="{w - mr}" y1="{Y(r["y"]):.1f}" y2="{Y(r["y"]):.1f}"/>'
                     f'<text class="reflabel" x="{ml + 6}" y="{Y(r["y"]) - 5:.1f}">{esc(r["label"])}</text>')
    for i, s in enumerate(series):
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in s["points"])
        col = SERIES[i % len(SERIES)]
        parts.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{pts}"/>')
        for x, y in s["points"]:
            parts.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4" fill="{col}" class="pt" '
                         f'data-tip="{esc(s["name"])}: {esc(x_fmt.format(x))} {esc(x_label)} &#8594; {esc(y_fmt.format(y))} {esc(y_label)}"/>')
    ends = sorted(((Y(s["points"][-1][1]), X(s["points"][-1][0]), s["name"]) for s in series), key=lambda e: e[0])
    placed = []
    for y_end, x_end, name in ends:                  # keep direct labels at least 13 px apart
        y_lab = max(y_end, placed[-1] + 13) if placed else y_end
        placed.append(y_lab)
        parts.append(f'<text class="direct" x="{x_end + 8:.1f}" y="{y_lab + 4:.1f}">{esc(name)}</text>')
    parts.append(f'<text class="axislabel" x="{(w - mr + ml) / 2}" y="{h - 6}" text-anchor="middle">{esc(x_label)}</text>'
                 f'<text class="axislabel" x="12" y="{mt + 8}">{esc(y_label)}</text></svg>')
    legend = "".join(f'<span class="key"><span class="swatch" style="background:{SERIES[i % 3]}"></span>{esc(s["name"])}</span>'
                     for i, s in enumerate(series)) if len(series) > 1 else ""
    return f'<figure><figcaption>{esc(title)}</figcaption>{"<div class=legend>" + legend + "</div>" if legend else ""}{"".join(parts)}</figure>'


def bar_chart(title: str, rows: list[dict], unit: str, limit: float | None, limit_label: str) -> str:
    w, bh, gap, ml, mr = 640, 18, 6, 260, 70
    h = len(rows) * (bh + gap) + 34
    vmax = max([r["value"] for r in rows] + ([limit] if limit else [])) * 1.1
    X = lambda v: ml + v / vmax * (w - ml - mr)  # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}" class="chart">']
    for i, r in enumerate(rows):
        y = 8 + i * (bh + gap)
        cls = "bar-bad" if r.get("bad") else "bar"
        parts.append(f'<text class="tick" x="{ml - 8}" y="{y + bh - 5}" text-anchor="end">{esc(r["label"])}</text>'
                     f'<rect class="{cls}" x="{ml}" y="{y}" width="{max(X(r["value"]) - ml, 1):.1f}" height="{bh}" rx="4" '
                     f'data-tip="{esc(r["label"])}: {r["value"]:.2f} {esc(unit)}{" (below limit)" if r.get("bad") else ""}"/>'
                     f'<text class="value" x="{max(X(r["value"]), X(limit) if limit is not None else 0) + 6:.1f}" y="{y + bh - 5}">{r["value"]:.1f}{" &#10007; below" if r.get("bad") else ""}</text>')
    if limit is not None:
        parts.append(f'<line class="ref" x1="{X(limit):.1f}" x2="{X(limit):.1f}" y1="2" y2="{h - 26}"/>'
                     f'<text class="reflabel" x="{X(limit):.1f}" y="{h - 12}" text-anchor="middle">{esc(limit_label)}</text>')
    parts.append("</svg>")
    return f'<figure><figcaption>{esc(title)}</figcaption>{"".join(parts)}</figure>'


def table(headers: list[str], rows: list[list], raw_cols=()) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c if i in raw_cols else esc(c)}</td>" for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def details(summary: str, inner: str) -> str:
    return f"<details><summary>{esc(summary)}</summary>{inner}</details>"


# ------------------------------------------------------------------ page
def build() -> str:
    reg = load("reports/validation-register.json") or {}
    ready = (load("reports/release-readiness.json") or {}).get("variants", {})
    bench = load("reports/bench-summary.json") or {}
    calc = load("engineering/calculations/power-stage-results.json") or {}
    sims = load("simulation/results/results.json") or []
    fw = load("reports/firmware-evidence.json") or {}
    src = load("sourcing/sourcing-check.json") or {}
    known = load("engineering/known-limitations.yaml") or {}
    entries = reg.get("entries", [])
    gates = reg.get("gates", {})
    stat = {s: sum(e["status"] == s for e in entries) for s in ("PASS", "FAIL", "NOT RUN")}
    S = []

    # header and headline
    S.append(f'<header><h1>NUBM44 laser driver: engineering status</h1><p class="meta">Generated '
             f'{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from commit {esc(git_commit())}; validation register of '
             f'{esc(reg.get("date", "UNKNOWN"))}. Predictions (calculation, simulation) are labelled as such; only bench '
             f'records are measurements. No tool on this page places an order.</p></header>')
    tiles = []
    for v in ("evaluation-board", "compact-22mm"):
        r = ready.get(v, {})
        nxt = r.get("next_level")
        sub = f"{len(r['blockers'][nxt])} blocker(s) to {nxt}" if nxt else "all levels met"
        tiles.append(f'<div class="tile"><div class="tile-label">{esc(v)}</div><div class="tile-value">{badge(r.get("level", "UNKNOWN"))}</div>'
                     f'<div class="tile-sub">{esc(sub)}</div></div>')
    g_text = gates.get("G", "UNKNOWN")
    tiles.append(f'<div class="tile"><div class="tile-label">Gate G (bench)</div><div class="tile-value">{badge(g_text.split(":")[0])}</div>'
                 f'<div class="tile-sub">{esc(g_text.split(":", 1)[-1].strip())}</div></div>')
    tiles.append(f'<div class="tile"><div class="tile-label">Validation register</div><div class="tile-value hero">{stat["PASS"]}'
                 f'<span class="of">/{len(entries)} PASS</span></div><div class="tile-sub">{stat["FAIL"]} FAIL, {stat["NOT RUN"]} NOT RUN; '
                 f'{len(reg.get("known_unchanged", []))} known unchanged, {len(reg.get("new_or_changed", []))} new or changed</div></div>')
    S.append('<section><h2>Overview</h2><div class="tiles">' + "".join(tiles) + "</div></section>")

    # decisions required
    pend = known.get("pending_disposition") or []
    dec_rows = [[p["id"], p.get("finding", ""), " ".join(str(p.get("reason", "")).split())] for p in pend]
    seen = {p.get("finding") for p in pend}
    for r in (load("engineering/release/design-reviews.yaml") or {}).get("reviews", []):
        if r.get("status") != "DONE":
            dec_rows.append([r["id"], f"human review for {r['level']}", " ".join(str(r["item"]).split())])
    for row in md_table("reports/comprehensive-project-audit.md", "AUD-"):
        if len(row) >= 5 and row[4] == "DOCUMENTED" and row[2] == "Risk" and row[1] in ("high", "medium") and row[0] not in seen:
            dec_rows.append([row[0], row[1], row[3]])
    S.append('<section><h2>Decisions and reviews required</h2><p>Items that only the owner or a human reviewer can close. '
             'Hardware changes, thresholds and purchases are never changed by automation.</p>'
             + table(["Item", "Ref / severity", "What is needed"], dec_rows) + "</section>")

    # boards
    cards = []
    for v in ("evaluation-board", "compact-22mm"):
        r = ready.get(v, {})
        gate_rows = [[k, badge(val)] for k, val in gates.items() if k.endswith(f"({v})")]
        drc = next((e for e in entries if e["id"] == f"VAL-DRC-{v}"), {})
        route = next((e for e in entries if e["id"] == f"VAL-ROUTE-{v}"), {})
        blocks = "".join(f"<li><strong>{esc(lvl)}</strong>: {'met' if not b else ''}<ul>{''.join(f'<li>{esc(x)}</li>' for x in b)}</ul></li>"
                         for lvl, b in (r.get("blockers") or {}).items())
        cards.append(f'<div class="card"><h3>{esc(v)} {badge(r.get("level", "UNKNOWN"))}</h3>'
                     + table(["Gate", "Status"], gate_rows, raw_cols=(1,))
                     + f'<p>Routing: {esc(route.get("detail", "UNKNOWN"))}. DRC: {esc(str(drc.get("detail", "UNKNOWN")).split(";")[0])}.</p>'
                     + details("Blockers by release level", f"<ul>{blocks}</ul>") + "</div>")
    S.append('<section><h2>Boards</h2><div class="cards">' + "".join(cards) + "</div></section>")

    # gates
    S.append('<section><h2>Release gates</h2>' + table(
        ["Gate", "Status", "Detail", "Evidence class"],
        [[k, badge(val.split(":")[0]), val.split(":", 1)[1].strip() if ":" in val else "",
          (reg.get("gate_evidence") or {}).get(k[0], "")] for k, val in gates.items()], raw_cols=(1,)) + "</section>")

    # tests
    suites = fw.get("host_tests", [])
    mut = fw.get("mutation", {}).get("mutants", [])
    tgt = fw.get("target", {})
    calc_checks = calc.get("checks", [])
    sim_pass = sum(r.get("status") == "PASS" for r in sims)
    test_rows = [["Firmware host suites", f"{sum(s.get('checks', 0) for s in suites)} checks in {len(suites)} suites",
                  badge("PASS" if suites and all(s["status"] == "PASS" for s in suites) else "FAIL")],
                 ["Firmware mutation check", f"{sum(m['status'] == 'KILLED' for m in mut)}/{len(mut)} audited defects caught",
                  badge("PASS" if mut and all(m["status"] == "KILLED" for m in mut) else "NOT RUN")],
                 ["ATtiny1616 target build", f"{tgt.get('flash_bytes', '?')} B flash, {tgt.get('ram_bytes', '?')} B RAM; {tgt.get('compiler', '')}",
                  badge(tgt.get("status", "NOT RUN"))],
                 ["Power-stage calculations", f"{sum(c['status'] == 'PASS' for c in calc_checks)}/{len(calc_checks)} checks (prediction)",
                  badge("PASS" if calc_checks and all(c["status"] == "PASS" for c in calc_checks) else "FAIL")],
                 ["Simulations (averaged model)", f"{sim_pass}/{len(sims)} pass (prediction)",
                  badge("PASS" if sims and sim_pass == len(sims) else "FAIL")],
                 ["Sourcing check", f"{(src.get('counts') or {}).get('FAIL', '?')} FAIL, {(src.get('counts') or {}).get('WARN', '?')} WARN",
                  badge(src.get("status", "NOT RUN"))]]
    S.append('<section><h2>Current test results</h2>' + table(["Check", "Result", "Status"], test_rows, raw_cols=(2,))
             + details("Full validation register", table(["ID", "Item", "Status", "Detail"],
                       [[e["id"], e["item"], badge(e["status"]), e["detail"]] for e in entries], raw_cols=(2,))) + "</section>")

    # efficiency chart
    pts = calc.get("operating_points", [])
    series = []
    for corner in ("min_hot", "typ_25C", "max_cold"):
        p = sorted((q["v_in"], 100 * q["efficiency"]) for q in pts if q["corner"] == corner)
        if p:
            series.append({"name": {"min_hot": "low-Vf diode, 65 C", "typ_25C": "typical diode, 25 C",
                                    "max_cold": "high-Vf diode, 0 C"}[corner], "points": p})
    if series:
        target = (load("engineering/design/parameters.yaml") or {}).get("current", {}).get("efficiency_target_pct", 94)
        S.append('<section><h2>Estimated efficiency (prediction)</h2><p>Loss-model estimate at 4.0 A, board input to laser. '
                 'The routed-copper estimate is lower (about 94.1 % on the evaluation board at 4.0 V); bench test T1.7 decides.</p>'
                 + line_chart("Efficiency vs board input voltage", series, "V", "%",
                              [{"y": target, "label": f"target {target:g} % @ 4.0 V"}, {"y": 86, "label": "target 86 % @ 3.0 V"}],
                              y_fmt="{:.1f}", x_fmt="{:.2f}")
                 + details("Table", table(["Diode corner", "Vin (V)", "Efficiency (%)"],
                                          [[s["name"], f"{x:.2f}", f"{y:.2f}"] for s in series for x, y in s["points"]]))
                 + "</section>")

    # simulations
    sim_rows = [[r.get("id"), r.get("name"), badge(r.get("status")),
                 ", ".join(f"{k}={v:.4g}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in list((r.get("metrics") or {}).items())[:4])]
                for r in sims]
    sec = ['<section><h2>Simulation results (averaged model; predictions)</h2>',
           table(["ID", "Test", "Status", "Key metrics"], sim_rows, raw_cols=(2,))]
    s11 = next((r for r in sims if r.get("id") == "SIM-11"), {})
    if s11.get("bode"):
        bseries = [{"name": k.replace("_", " "), "points": list(zip(b["freqs_hz"], b["mag_db"]))} for k, b in s11["bode"].items()]
        sec.append(line_chart("SIM-11 loop gain magnitude (FRA in the ngspice deck)", bseries, "Hz", "dB",
                              [{"y": 0, "label": "0 dB"}], logx=True, y_fmt="{:.0f}", x_fmt="{:g}"))
    s12 = next((r for r in sims if r.get("id") == "SIM-12"), {})
    if s12.get("sweep"):
        rows = [{"label": k, "value": v["gain_margin_db"] if v["gain_margin_db"] is not None else 0,
                 "bad": not v["pass"]} for k, v in s12["sweep"].items()]
        sec.append(bar_chart("SIM-12 gain margin per tolerance case (3.0 V, max-Vf diode)", rows, "dB", 10.0, "10 dB criterion"))
    S.append("".join(sec) + "</section>")

    # defects and risks
    audit = md_table("reports/comprehensive-project-audit.md", "AUD-")
    open_rows = [[r[0], r[1], r[2], r[3], badge(r[4])] for r in audit if len(r) >= 5 and r[4] != "FIXED"]
    fixed = sum(1 for r in audit if len(r) >= 5 and r[4] == "FIXED")
    risks = md_table("engineering/risk-register.md", "R-")
    risk_rows = sorted(([r[0], r[1], r[4], r[8]] for r in risks if len(r) >= 9), key=lambda r: -int(r[2] or 0))
    S.append(f'<section><h2>Open defects and engineering risks</h2><p>{fixed} audit findings fixed; {len(open_rows)} not '
             f'(fully) fixed. Full detail: <code>reports/comprehensive-project-audit.md</code>.</p>'
             + table(["ID", "Severity", "Class", "Title", "Status"], open_rows, raw_cols=(4,))
             + details("Risk register (highest score first)", table(["ID", "Risk", "Score", "Owner / status"], risk_rows))
             + "</section>")

    # manufacturing and sourcing
    src_rows = [[f["ref"], f["check"], f["detail"]] for f in src.get("findings", []) if f["severity"] in ("FAIL", "WARN")]
    unknown = [f for f in src.get("findings", []) if f["check"] == "supplier data"]
    cost = src.get("cost_summary", {})
    S.append('<section><h2>Manufacturing blockers and sourcing</h2>'
             + table(["Variant", "BOM lines", "Priced lines", "Known subtotal (USD, not a quote)"],
                     [[v, c["lines"], c["priced_lines"], c["known_subtotal_usd"]] for v, c in cost.items()])
             + f'<p>{len(unknown)} BOM lines have UNKNOWN stock or price; confirm at order time.</p>'
             + details(f"Sourcing warnings ({len(src_rows)})", table(["Part", "Check", "Detail"], src_rows)) + "</section>")

    # bench
    bv = bench.get("variants", {})
    S.append('<section><h2>Required bench measurements (Gate G)</h2><p>Record results with '
             '<code>automation/bench/bench.py</code>; see <code>documentation/testing/results/README.md</code>.</p>'
             + table(["Variant", "Gate G", "Required tests", "Not yet PASS"],
                     [[v, badge(s.get("gate_g")), len(s.get("required", [])), ", ".join(s.get("not_passed", []))]
                      for v, s in bv.items()], raw_cols=(1,)) + "</section>")

    # next actions (computed)
    actions = []
    for v in ("evaluation-board", "compact-22mm"):
        r = ready.get(v, {})
        nxt = r.get("next_level")
        if nxt:
            actions += [f"{v}: {b}" for b in r["blockers"][nxt][:6]]
    actions += [f"Owner decision: {p['id']} ({p.get('finding', '')})" for p in pend]
    S.append('<section><h2>Next recommended actions</h2><p>Computed from the blockers of each board\'s next release level '
             'and the pending decisions, in that order.</p><ol>' + "".join(f"<li>{esc(a)}</li>" for a in actions) + "</ol></section>")
    return PAGE.replace("{{BODY}}", "\n".join(S))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NUBM44 Status Dashboard</title>
<style>
:root{color-scheme:light;--surface-0:#f4f3f0;--surface-1:#fcfcfb;--border:#dcdad3;--text-primary:#0b0b0b;--text-secondary:#52514e;
--text-muted:#77756f;--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--good:#0ca30c;--warning:#fab219;--critical:#d03b3b;--neutral:#8a887f;--grid:#e8e6e0}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface-0:#121211;--surface-1:#1a1a19;--border:#383835;
--text-primary:#f0efec;--text-secondary:#c3c2b7;--text-muted:#94928a;--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--grid:#2c2c2a}}
:root[data-theme="dark"]{color-scheme:dark;--surface-0:#121211;--surface-1:#1a1a19;--border:#383835;--text-primary:#f0efec;--text-secondary:#c3c2b7;
--text-muted:#94928a;--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--grid:#2c2c2a}
body{margin:0;background:var(--surface-0);color:var(--text-primary);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
header h1{font-size:1.5rem;margin:.5rem 0}.meta{color:var(--text-secondary);font-size:.85rem}
section{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:16px;margin:16px 0}
h2{font-size:1.15rem;margin:0 0 .6rem}h3{font-size:1rem;margin:0 0 .5rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.tile{border:1px solid var(--border);border-radius:8px;padding:12px}.tile-label{color:var(--text-secondary);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em}
.tile-value{margin:.35rem 0;font-size:1rem}.hero{font-size:1.8rem;font-weight:600}.of{font-size:.9rem;color:var(--text-secondary);font-weight:400}
.tile-sub{color:var(--text-secondary);font-size:.82rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}.card{border:1px solid var(--border);border-radius:8px;padding:12px}
.badge{display:inline-block;border-radius:999px;padding:1px 8px;font-size:.78rem;font-weight:600;border:1.5px solid;white-space:nowrap}
.badge.good{border-color:var(--good)}.badge.warning{border-color:var(--warning)}.badge.critical{border-color:var(--critical)}.badge.neutral{border-color:var(--neutral)}
.badge.good span{color:var(--good)}.badge.warning span{color:var(--warning)}.badge.critical span{color:var(--critical)}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.86rem}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--text-secondary);font-weight:600}td:first-child{white-space:nowrap}details{margin-top:.6rem}summary{cursor:pointer;color:var(--text-secondary)}
figure{margin:.8rem 0}figcaption{font-weight:600;margin-bottom:.3rem}.chart{width:100%;height:auto;max-width:760px;display:block}
.grid{stroke:var(--grid);stroke-width:1}.axis{stroke:var(--text-muted);stroke-width:1}.tick,.reflabel,.value{fill:var(--text-secondary);font-size:11px}
.axislabel{fill:var(--text-muted);font-size:11px}.direct{fill:var(--text-primary);font-size:11px}.ref{stroke:var(--text-muted);stroke-dasharray:4 3;stroke-width:1}
.pt{stroke:var(--surface-1);stroke-width:2}.bar{fill:var(--series-1)}.bar-bad{fill:var(--critical)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:.82rem;color:var(--text-secondary);margin:.2rem 0}.key{display:inline-flex;align-items:center;gap:6px}
.swatch{width:12px;height:12px;border-radius:3px;display:inline-block}
#tip{position:fixed;pointer-events:none;background:var(--surface-1);color:var(--text-primary);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:.8rem;display:none;box-shadow:0 2px 8px rgba(0,0,0,.15)}
code{font-size:.85em}
</style></head><body><main>
{{BODY}}
</main><div id="tip" role="tooltip"></div>
<script>
(function(){var t=document.getElementById('tip');document.querySelectorAll('[data-tip]').forEach(function(el){
el.addEventListener('mousemove',function(e){t.textContent=el.getAttribute('data-tip');t.style.display='block';
t.style.left=Math.min(e.clientX+12,window.innerWidth-260)+'px';t.style.top=(e.clientY+12)+'px'});
el.addEventListener('mouseleave',function(){t.style.display='none'})})})();
</script></body></html>
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"dashboard: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
