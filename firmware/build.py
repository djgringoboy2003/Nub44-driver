"""Build and test the NUBM44 driver firmware (single build driver; audit AUD-VAL-07, AUD-PROC-01).

1. Host unit tests of the hardware-independent code and of the HAL register model (TinyCC on Windows,
   or the C compiler named by $CC / gcc / cc elsewhere).
2. Target build with avr-gcc (-mmcu=attiny1616, -Werror), producing firmware/build/nubm44_fw.hex.
3. Optional mutation check: re-inject the audited defects and require the tests to fail.

Writes reports/firmware-evidence.json with source hashes, compiler versions and every suite result.
Exit code 0 only when every requested step ran and passed; a missing compiler is NOT RUN, never PASS.

    .venv\\Scripts\\python.exe firmware\\build.py              # host tests + target build
    .venv\\Scripts\\python.exe firmware\\build.py --mutation   # also the mutation check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FW = Path(__file__).resolve().parent
ROOT = FW.parent
EVIDENCE = ROOT / "reports" / "firmware-evidence.json"
OUT = FW / "build"
MMCU = "attiny1616"
TARGET_FLAGS = ["-mmcu=" + MMCU, "-Os", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections"]

# suite name -> (extra flags, sources relative to firmware/)
SUITES = {
    "app": ([], ["tests/test_app.c", "src/app.c", "src/conv.c"]),
    "app_laser_ntc_required": (["-DAPP_LASER_NTC_REQUIRED=1"], ["tests/test_app.c", "src/app.c", "src/conv.c"]),
    "conv": ([], ["tests/test_conv.c", "src/conv.c"]),
    "holdup": ([], ["tests/test_holdup.c", "src/holdup.c"]),
    "fw": ([], ["tests/test_fw.c", "tests/hal_mock.c", "src/fw.c", "src/app.c", "src/conv.c", "src/holdup.c"]),
    "hal_register_model": (["-Itests/mock"], ["tests/test_hal.c", "src/hal_avr.c"]),
}

# Each audited defect, re-injected into a scratch copy; the named suite must then fail.
MUTANTS = [
    ("AUD-FW-01 board NTC failure ignored", "src/app.c",
     "} else if (confirm(&a->sens_board_ms, true, APP_SENSOR_FAULT_MS)) {", "} else if (0) {", "app"),
    ("AUD-FW-02 fitted laser NTC failure ignored", "src/app.c", "&& a->laser_ntc != LASER_NTC_FITTED;", ";", "app"),
    ("AUD-FW-03 watchdog cleared without a tick", "src/fw.c", "    if (n == 0u) {\n        return;",
     "    if (n == 0u) {\n        hal_wdt_clear();\n        return;", "fw"),
    ("AUD-FW-06 no debounce", "src/app.c",
     "        a->sw_raw = closed;\n        a->sw_stable_ms = 0;\n        return false;",
     "        a->sw_raw = closed;\n        return closed;", "app"),
    ("AUD-FW-07 watchdog reset ignored", "src/fw.c",
     "app_force_fault(&app, FAULT_INTERNAL, DETAIL_WATCHDOG_RESET);", ";", "fw"),
    ("AUD-FW-08 sleeps although the supply is back", "src/hal_avr.c",
     "    if (!(AC2.STATUS & AC_STATE_bm)) {\n        sei();", "    if (1) {\n        sei();", "hal_register_model"),
    ("AUD-FW-09 restart on the first return edge", "src/holdup.c",
     "return (now - h->t_return) >= HOLDUP_RETURN_TICKS ? HOLDUP_RESTART : HOLDUP_WAIT;",
     "return HOLDUP_RESTART;", "holdup"),
    ("AUD-FW-10 CC pull-up always on", "src/hal_avr.c",
     "    PORTB.PIN1CTRL = PORT_ISC_INPUT_DISABLE_gc;   /* CC: pull-up only",
     "    PORTB.PIN1CTRL = PORT_PULLUPEN_bm;   /* CC: pull-up only", "hal_register_model"),
    ("AUD-FW-11 no start-voltage re-check", "src/app.c",
     "if (in->vbat_mv < APP_VBAT_START_MIN_MV) {   /* AUD-FW-11", "if (0) {   /* AUD-FW-11", "app"),
    ("AUD-FW-12 tick backlog ignored", "src/fw.c",
     "        app_force_fault(&app, FAULT_INTERNAL, DETAIL_TICK_OVERRUN);", "        ;", "fw"),
    ("AUD-FW-13 fixed 3 s blink period", "src/app.c",
     "a->t_state_ms % (n * APP_BLINK_MS + APP_BLINK_PAUSE_MS)", "a->t_state_ms % 3000u", "app"),
    ("AUD-FW-14 over-voltage only while running", "src/app.c",
     "    if (in->ov_trip) {                                  /* AUD-FW-14",
     "    if (in->ov_trip && a->was_enabled) {   /* AUD-FW-14", "app"),
    ("AUD-FW-15 no output-while-off check", "src/app.c",
     "            fail(a, FAULT_OUTPUT_WHILE_OFF, DETAIL_NONE);", "            ;", "app"),
    ("AUD-FW-19 DAC2 reference written to CTRLC", "src/hal_avr.c",
     "    VREF.CTRLC = VREF_ADC1REFSEL_1V5_gc;\n    VREF.CTRLD = VREF_DAC2REFSEL_1V5_gc;",
     "    VREF.CTRLC = VREF_ADC1REFSEL_1V5_gc | VREF_DAC2REFSEL_1V5_gc;", "hal_register_model"),
    ("AUD-FW-20 DAC2 stops in standby", "src/hal_avr.c",
     "DAC2.CTRLA = DAC_ENABLE_bm | DAC_RUNSTDBY_bm;", "DAC2.CTRLA = DAC_ENABLE_bm;", "hal_register_model"),
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source_files() -> list[Path]:
    files = [p for d in ("src", "tests") for p in (FW / d).rglob("*") if p.is_file() and p.suffix in (".c", ".h", ".py")]
    return sorted(files + [Path(__file__).resolve()], key=lambda p: p.as_posix())


def source_hashes() -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in source_files()}


def host_compiler() -> tuple[str, str] | None:
    """(path, kind) for the host C compiler; kind is 'tcc' or 'gcc'."""
    tcc = next((ROOT / "tools" / "tcc").rglob("tcc.exe"), None) if (ROOT / "tools" / "tcc").is_dir() else None
    if os.environ.get("CC"):
        cc = shutil.which(os.environ["CC"])
        if cc:
            return cc, "tcc" if "tcc" in Path(cc).name else "gcc"
    if tcc:
        return str(tcc), "tcc"
    for name in ("gcc", "cc", "clang"):
        cc = shutil.which(name)
        if cc:
            return cc, "gcc"
    return None


def avr_tool(name: str) -> str | None:
    base = ROOT / "tools" / "avr-gcc"
    local = next(base.rglob(name + ".exe"), None) if base.is_dir() else None
    if os.environ.get("AVR_GCC_BIN"):
        cand = Path(os.environ["AVR_GCC_BIN"]) / (name + (".exe" if os.name == "nt" else ""))
        if cand.is_file():
            return str(cand)
    return str(local) if local else shutil.which(name)


def tool_version(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        text = (r.stdout or r.stderr).strip().splitlines()
        return text[0] if text else "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def host_flags(kind: str) -> list[str]:
    return ["-Wall", "-Werror"] if kind == "tcc" else ["-std=c99", "-Wall", "-Wextra", "-Werror", "-O1"]


def run_suite(cc: tuple[str, str], name: str, workdir: Path, exe_dir: Path) -> dict:
    flags, sources = SUITES[name]
    exe = exe_dir / (f"test_{name}" + (".exe" if os.name == "nt" else ""))
    libs = ["-lm"] if cc[1] == "gcc" else []
    cmd = [cc[0], *host_flags(cc[1]), *flags, "-o", str(exe), *sources, *libs]
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {"suite": name, "status": "FAIL", "stage": "compile", "detail": (r.stdout + r.stderr)[-800:]}
    r = subprocess.run([str(exe)], cwd=workdir, capture_output=True, text=True, timeout=300)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    m = re.fullmatch(r"(\d+) checks, (\d+) failures", last)
    if not m:
        return {"suite": name, "status": "FAIL", "stage": "run", "detail": "no summary line: " + r.stdout[-400:]}
    checks, fails = int(m[1]), int(m[2])
    ok = r.returncode == 0 and fails == 0 and checks > 0
    return {"suite": name, "status": "PASS" if ok else "FAIL", "checks": checks, "failures": fails,
            "detail": "" if ok else r.stdout[-800:]}


def host_tests(exe_dir: Path) -> tuple[list[dict], str]:
    cc = host_compiler()
    if cc is None:
        return [{"suite": s, "status": "NOT RUN", "detail": "no host C compiler (run scripts/setup.ps1)"}
                for s in SUITES], "UNKNOWN"
    exe_dir.mkdir(parents=True, exist_ok=True)
    version = tool_version([cc[0], "-v"]) if cc[1] == "tcc" else tool_version([cc[0], "--version"])
    return [run_suite(cc, s, FW, exe_dir) for s in SUITES], version


def target_build() -> dict:
    gcc, objcopy, size = avr_tool("avr-gcc"), avr_tool("avr-objcopy"), avr_tool("avr-size")
    if not (gcc and objcopy and size):
        return {"status": "NOT RUN", "detail": "avr-gcc toolchain not found (run scripts/setup.ps1)"}
    OUT.mkdir(parents=True, exist_ok=True)
    elf, hexfile = OUT / "nubm44_fw.elf", OUT / "nubm44_fw.hex"
    sources = sorted(str(p.relative_to(FW).as_posix()) for p in (FW / "src").glob("*.c"))
    r = subprocess.run([gcc, *TARGET_FLAGS, "-o", str(elf), *sources], cwd=FW, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {"status": "FAIL", "compiler": tool_version([gcc, "--version"]), "detail": (r.stdout + r.stderr)[-1500:]}
    subprocess.run([objcopy, "-O", "ihex", "-R", ".eeprom", "-R", ".fuse", str(elf), str(hexfile)], check=True, timeout=60)
    sizes = {}
    for line in subprocess.run([size, "-A", str(elf)], capture_output=True, text=True, timeout=60).stdout.splitlines():
        m = re.match(r"^\.(text|rodata|data|bss|noinit)\s+(\d+)", line)
        if m:
            sizes[m[1]] = int(m[2])
    flash, ram = sizes.get("text", 0) + sizes.get("rodata", 0) + sizes.get("data", 0), \
        sizes.get("data", 0) + sizes.get("bss", 0) + sizes.get("noinit", 0)
    ok = flash <= 16384 and ram <= 2048
    return {"status": "PASS" if ok else "FAIL", "compiler": tool_version([gcc, "--version"]), "flags": TARGET_FLAGS,
            "sources": sources, "hex": hexfile.relative_to(ROOT).as_posix(), "hex_sha256": sha256(hexfile),
            "sizes": sizes, "flash_bytes": flash, "ram_bytes": ram, "detail": "" if ok else "exceeds 16 KB flash / 2 KB RAM"}


def mutation_check() -> dict:
    cc = host_compiler()
    if cc is None:
        return {"status": "NOT RUN", "detail": "no host C compiler"}
    results = []
    with tempfile.TemporaryDirectory(prefix="nubm44-mutants-") as tmp:
        for name, rel, old, new, suite in MUTANTS:
            work = Path(tmp) / "fw"
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(FW, work, ignore=shutil.ignore_patterns("build"))
            target = work / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                results.append({"mutant": name, "status": "SETUP-ERROR", "detail": "pattern not found"})
                continue
            target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
            r = run_suite(cc, suite, work, work / "bin")
            results.append({"mutant": name, "suite": suite, "status": "KILLED" if r["status"] == "FAIL" else "SURVIVED"})
    ok = all(r["status"] == "KILLED" for r in results)
    return {"status": "PASS" if ok else "FAIL", "mutants": results}


def fuse_values() -> dict:
    text = (FW / "src" / "fuses.h").read_text(encoding="utf-8")
    return {m[1]: m[2] for m in re.finditer(r"#define\s+FW_FUSE_(\w+)\s+(0x[0-9A-Fa-f]+)u", text)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host-only", action="store_true")
    ap.add_argument("--target-only", action="store_true")
    ap.add_argument("--mutation", action="store_true", help="also run the mutation check")
    ap.add_argument("--no-evidence", action="store_true", help="do not write reports/firmware-evidence.json")
    args = ap.parse_args(argv)

    hashes_before = source_hashes()
    evidence = {"schema": "nubm44-firmware-evidence.v1", "generated_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_class": "SOFTWARE (host tests and a compiler build; not hardware verification)",
                "sources": hashes_before, "fuses_required": fuse_values()}
    if not args.target_only:
        evidence["host_tests"], evidence["host_compiler"] = host_tests(OUT / "host")
    if not args.host_only:
        evidence["target"] = target_build()
    if args.mutation:
        evidence["mutation"] = mutation_check()
    if source_hashes() != hashes_before:
        evidence["problems"] = ["firmware sources changed during the build"]

    statuses = [s["status"] for s in evidence.get("host_tests", [])]
    statuses += [evidence[k]["status"] for k in ("target", "mutation") if k in evidence]
    evidence["status"] = "PASS" if statuses and all(s == "PASS" for s in statuses) and not evidence.get("problems") \
        else ("NOT RUN" if any(s == "NOT RUN" for s in statuses) else "FAIL")
    if not args.no_evidence and not args.host_only and not args.target_only:
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(evidence, indent=1) + "\n", encoding="utf-8")

    for s in evidence.get("host_tests", []):
        print(f"  host {s['suite']:24s} {s['status']:8s} {s.get('checks', '')} {s.get('detail', '')[:200]}")
    if "target" in evidence:
        t = evidence["target"]
        print(f"  target {MMCU:22s} {t['status']:8s} flash {t.get('flash_bytes', '-')} B, RAM {t.get('ram_bytes', '-')} B "
              f"{t.get('detail', '')[:300]}")
    if "mutation" in evidence:
        for m in evidence["mutation"].get("mutants", []):
            print(f"  mutant {m['status']:9s} {m['mutant']}")
    print(f"firmware: {evidence['status']}")
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
