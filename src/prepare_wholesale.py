"""Prepare the wholesale lines from the public UCI workbook.

Source : Chen, D. (2019). Online Retail II. UCI Machine Learning Repository, CC BY 4.0.
         https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip
         Put online_retail_II.xlsx in .cache/ (git-ignored) and run this script.

Writes data/wholesale_lines.csv.gz (every line) and data/wholesale_demo.csv.gz (the five months
before 27 October 2010, what the page loads). Rules: lines with a customer, a product code and a
price; invoices starting with C (cancellations) keep their negative quantity; the two yearly sheets
overlap on 1-9 December 2010, so each invoice is read once.

Needs openpyxl to read the workbook; nothing else in the repository does.
"""

from __future__ import annotations

import gzip
import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache" / "online_retail_II.xlsx"
LINES = ROOT / "data" / "wholesale_lines.csv.gz"
DEMO = ROOT / "data" / "wholesale_demo.csv.gz"
DEMO_DAY = date(2010, 10, 27)
PRODUCT = re.compile(r"^\d{5}[A-Za-z]{0,2}$")  # leaves out postage, fees, manual lines, samples


def read_source() -> list[tuple]:
    import openpyxl

    rows, seen = [], set()
    for sheet in openpyxl.load_workbook(SOURCE, read_only=True).worksheets:
        here = set()
        lines = sheet.iter_rows(values_only=True)
        next(lines)
        for invoice, code, description, quantity, when, price, customer, _country in lines:
            invoice, code = str(invoice).strip(), str(code or "").strip()
            if invoice in seen:
                continue
            here.add(invoice)
            if customer in (None, "") or not PRODUCT.match(code) or not quantity or not price or price <= 0:
                continue
            if invoice.startswith("C") != (quantity < 0):
                continue
            rows.append((str(int(customer)), when.date(), code, str(description or "").strip(), int(quantity), price))
        seen |= here
    return sorted(rows, key=lambda r: r[1])  # stable: the order of the workbook inside each day


def write(path: Path, rows: list[tuple]) -> None:
    out, described = ["customer_id,date,item,description,quantity,price"], set()
    for customer, day, code, description, quantity, price in rows:
        # the name of an item once is enough; repeating it 800,000 times would only make the file bigger
        text = "" if code in described or not description else '"' + description.replace('"', "'") + '"'
        if text:
            described.add(code)
        out.append(f"{customer},{day},{code},{text},{quantity},{price:g}")
    path.write_bytes(gzip.compress(("\n".join(out) + "\n").encode(), 9, mtime=0))
    print(f"{path.name}: {len(rows):,} lines, {path.stat().st_size // 1024:,} KB, "
          f"sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}")


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing {SOURCE}: see the address at the top of this file.")
    rows = read_source()
    write(LINES, rows)
    write(DEMO, [r for r in rows if DEMO_DAY - timedelta(150) < r[1] <= DEMO_DAY])


if __name__ == "__main__":
    main()
