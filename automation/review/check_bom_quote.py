"""Read a legacy PCBWay XLS without changing project dependencies.

Run with system Python -I and --reader-path pointing to an external xlrd install.
The workbook is data only; this program never evaluates formulas or macros.
"""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader-path", type=Path, required=True)
    parser.add_argument("--quote", type=Path, required=True)
    parser.add_argument("--bom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    reader = args.reader_path.resolve()
    if not sys.flags.isolated:
        parser.error("Use python -I when parsing the untrusted workbook")
    if reader.is_relative_to(root):
        parser.error("Install the XLS reader outside the repository")
    sys.path.insert(0, str(reader))
    import xlrd  # type: ignore[import-not-found]  # external, deliberately unpinned here

    reader_file = Path(xlrd.__file__).resolve()
    if not reader_file.is_relative_to(reader):
        parser.error("xlrd did not load from the explicit reader directory")
    book = xlrd.open_workbook(str(args.quote), formatting_info=True)
    sheet = book.sheet_by_index(0)
    headers = [str(c.value).strip() for c in sheet.row(1)]
    match = re.search(r"\((\d+)\s*units\)", " ".join(headers), re.I)
    if not match:
        parser.error("Could not derive assembly quantity from workbook headers")
    boards = int(match.group(1))
    with args.bom.open(encoding="utf-8-sig", newline="") as handle:
        expected = list(csv.reader(handle))
    errors: list[str] = []
    rows: list[dict] = []
    seen: set[int] = set()
    refs: set[str] = set()
    total = Decimal(0)
    tolerance = Decimal("0.000000001")
    for index in range(2, sheet.nrows):
        if sheet.cell_type(index, 0) != xlrd.XL_CELL_NUMBER:
            continue
        item = int(sheet.cell_value(index, 0))
        if item in seen:
            errors.append(f"duplicate item {item}")
        seen.add(item)
        cells = [sheet.cell_value(index, col) for col in range(15)]
        if item < 1 or item >= len(expected):
            errors.append(f"extra item {item}")
            continue
        actual = [str(int(v)) if col in (0, 2) else str(v).strip()
                  for col, v in enumerate(cells[:9])]
        for col, value in enumerate(actual):
            if value != expected[item][col].strip():
                errors.append(f"item {item} field {expected[0][col]}: {value!r} != {expected[item][col]!r}")
        designators = [v.strip() for v in actual[1].split(",")]
        qty = int(actual[2])
        if qty != len(designators):
            errors.append(f"item {item} quantity differs from designator count")
        for ref in designators:
            if ref in refs:
                errors.append(f"duplicate designator {ref}")
            refs.add(ref)
        dns = actual[7].upper() == "DNS"
        unit = None if cells[9] == "" else Decimal(str(cells[9]))
        extended = None if cells[10] == "" else Decimal(str(cells[10]))
        if dns:
            if unit is not None or extended is not None:
                errors.append(f"DNS item {item} has a price")
            if "DNP" not in str(cells[12]).upper():
                errors.append(f"DNS item {item} lacks PCBWay DNP acknowledgement")
        elif unit is None or extended is None:
            errors.append(f"unpriced populated item {item}")
        else:
            if abs(unit * qty * boards - extended) > tolerance:
                errors.append(f"item {item} line arithmetic mismatch")
            total += extended
        fmt = book.format_map[book.xf_list[sheet.cell_xf_index(index, 10)].format_key].format_str
        rows.append({"item": item, "excel_row": index + 1, "designators": actual[1],
                     "qty_per_board": qty, "manufacturer": actual[3], "mpn": actual[4],
                     "description": actual[5], "footprint": actual[6], "type": actual[7],
                     "unit_price": str(unit) if unit is not None else "UNKNOWN",
                     "line_total": str(extended) if extended is not None else "UNKNOWN",
                     "dns": dns, "delivery_time": str(cells[11]) or "UNKNOWN",
                     "pcbway_note": str(cells[12]), "number_format": fmt})
    for item in range(1, len(expected)):
        if item not in seen:
            errors.append(f"missing item {item}")
    summaries: dict[str, str] = {}
    summary_formats: dict[str, str] = {}
    for index in range(sheet.nrows):
        label = " ".join(str(sheet.cell_value(index, c)) for c in range(10)).lower()
        val = sheet.cell_value(index, 10)
        if sheet.cell_type(index, 10) != xlrd.XL_CELL_NUMBER:
            continue
        key = next((key for text, key in (("component cost", "components"),
                    ("assembly cost", "assembly"), ("pcb cost", "pcb"),
                    ("all total", "grand_total")) if text in label), None)
        if key:
            summaries[key] = str(Decimal(str(val)))
            summary_formats[key] = book.format_map[book.xf_list[sheet.cell_xf_index(index, 10)].format_key].format_str
    for key in ("components", "assembly", "pcb", "grand_total"):
        if key not in summaries:
            errors.append(f"missing {key} summary")
    if len(summaries) == 4:
        if abs(total - Decimal(summaries["components"])) > tolerance:
            errors.append("component subtotal mismatch")
        if abs(sum((Decimal(summaries[k]) for k in ("components", "assembly", "pcb")), Decimal(0))
               - Decimal(summaries["grand_total"])) > tolerance:
            errors.append("grand total mismatch")
    visible = " ".join(str(c.value) for row in sheet.get_rows() for c in row if c.ctype == xlrd.XL_CELL_TEXT)
    codes = sorted(set(re.findall(r"\b(?:USD|GBP|CNY|RMB|EUR|HKD|AUD|CAD|NZD|SGD)\b", visible, re.I)))
    result = {"quote": args.quote.as_posix(), "quote_sha256": hashlib.sha256(args.quote.read_bytes()).hexdigest(),
              "bom": args.bom.as_posix(), "bom_sha256": hashlib.sha256(args.bom.read_bytes()).hexdigest(),
              "reader": {"version": xlrd.__version__, "file": str(reader_file), "isolated": True},
              "sheet": sheet.name, "boards": boards, "rows": rows, "totals": summaries,
              "summary_number_formats": summary_formats, "currency_codes_in_cell_text": codes,
              "currency": "UNKNOWN", "errors": errors,
              "counts": {"bom_lines": len(rows), "priced_lines": sum(not r["dns"] for r in rows),
                         "smd_per_board": sum(r["qty_per_board"] for r in rows if not r["dns"]),
                         "including_dns_per_board": sum(r["qty_per_board"] for r in rows)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows",)}, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
