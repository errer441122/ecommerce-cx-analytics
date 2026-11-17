"""Late orders, every morning: who to contact first and who to keep out of promotions.

    python src/late_orders.py --shipments shipments.csv

The Olist analysis in this repository found that late delivery is the main
driver of a bad review: 27% of late orders get 4-5 stars, against 83% of
on-time ones. This tool finds the late orders while they can still be handled.
It reads a shipments export (from the shipping platform or the carrier) with,
for each order, the promised delivery date and the delivery date once it has
arrived, and writes into --out (default cx_actions/):

- late_open.csv       past the promised date and not delivered yet, longest
                      wait first: contact these customers first, and import
                      the file into Klaviyo to set delivery_issue=open so
                      promotional emails skip them
- late_delivered.csv  delivered late in the last --recent days (default 7):
                      a follow-up or apology, then delivery_issue=closed

It also prints the late rate by carrier, so a carrier that is failing shows
up before the reviews do.

Column names differ by platform; pass yours with --order, --email, --promised,
--delivered and --carrier. Dates can be YYYY-MM-DD (with or without a time)
or DD/MM/YYYY. The files hold customer emails, so cx_actions/ is gitignored.

Pure standard library.
"""

from __future__ import annotations

import argparse
import csv
import io
from datetime import date, datetime
from pathlib import Path

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")
MIN_CARRIER_ORDERS = 20  # below this a late rate is a handful of parcels, not a trend
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def parse_day(text: str | None) -> date | None:
    """Date from 'YYYY-MM-DD[ time]' or 'DD/MM/YYYY[ time]'; None if empty."""
    text = (text or "").strip()
    if not text:
        return None
    head = text.split()[0].split("T")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date {text!r} is neither YYYY-MM-DD nor DD/MM/YYYY")


OPEN_HEADER = ["email", "order_id", "carrier", "promised_date", "days_late", "delivery_issue"]
DELIVERED_HEADER = ["email", "order_id", "carrier", "promised_date", "delivered_date", "days_late", "delivery_issue"]


def read_csv(path: Path) -> csv.DictReader:
    """Rows of a CSV as real tools save it: comma, semicolon (Italian Excel) or
    tab as separator, with or without the byte-order mark Excel adds."""
    text = path.read_text(encoding="utf-8-sig")
    header = text.split("\n", 1)[0]
    return csv.DictReader(io.StringIO(text, newline=""), delimiter=max(",;\t", key=header.count))


def to_csv(header: list[str], rows: list[list[object]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _safe(text: str) -> str:
    return "'" + text if text.startswith(FORMULA_START) else text


def read_shipments(path: Path, order: str, email: str, promised: str, delivered: str,
                   carrier: str) -> list[dict]:
    reader = read_csv(path)
    missing = [c for c in (order, promised, delivered) if c not in (reader.fieldnames or ())]
    if missing:
        raise SystemExit(f"Column(s) not in the file: {', '.join(missing)}. "
                         f"Pass your column names with --order, --promised and --delivered.")
    rows = []
    for line, r in enumerate(reader, start=2):
        try:
            due, arrived = parse_day(r[promised]), parse_day(r[delivered])
        except ValueError as e:
            raise SystemExit(f"Line {line}: {e}") from None
        if due is None:
            continue  # no promise, nothing to be late against
        rows.append({
            "order_id": (r.get(order) or "").strip(),
            "email": (r.get(email) or "").strip().lower(),
            "carrier": (r.get(carrier) or "").strip() or "unknown",
            "promised": due,
            "delivered": arrived,
        })
    return rows


def late_lists(rows: list[dict], as_of: date, recent: int) -> tuple[list[dict], list[dict]]:
    """(late and not delivered, delivered late within `recent` days), worst first."""
    still_out = [dict(r, days_late=(as_of - r["promised"]).days)
                 for r in rows if r["delivered"] is None and r["promised"] < as_of]
    arrived_late = [dict(r, days_late=(r["delivered"] - r["promised"]).days)
                    for r in rows if r["delivered"] and r["delivered"] > r["promised"]
                    and 0 <= (as_of - r["delivered"]).days <= recent]
    key = lambda r: (-r["days_late"], r["order_id"])  # noqa: E731
    return sorted(still_out, key=key), sorted(arrived_late, key=key)


def carrier_late_rates(rows: list[dict]) -> list[dict]:
    """Share of delivered orders that arrived after the promised date, by carrier."""
    stats: dict[str, dict] = {}
    for r in rows:
        if r["delivered"] is None:
            continue
        s = stats.setdefault(r["carrier"], {"carrier": r["carrier"], "delivered": 0, "late": 0})
        s["delivered"] += 1
        s["late"] += r["delivered"] > r["promised"]
    out = [dict(s, late_rate=s["late"] / s["delivered"]) for s in stats.values()]
    return sorted(out, key=lambda s: (s["delivered"] < MIN_CARRIER_ORDERS, -s["late_rate"], s["carrier"]))


def open_rows(still_out: list[dict]) -> list[list[object]]:
    """late_open.csv: to contact first, and to set delivery_issue=open in Klaviyo."""
    return [[_safe(r["email"]), _safe(r["order_id"]), _safe(r["carrier"]), r["promised"].isoformat(),
             r["days_late"], "open"] for r in still_out]


def delivered_rows(arrived_late: list[dict]) -> list[list[object]]:
    """late_delivered.csv: a follow-up, then delivery_issue=closed."""
    return [[_safe(r["email"]), _safe(r["order_id"]), _safe(r["carrier"]), r["promised"].isoformat(),
             r["delivered"].isoformat(), r["days_late"], "closed"] for r in arrived_late]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--shipments", type=Path, required=True)
    p.add_argument("--as-of", default="", help="YYYY-MM-DD to replay a past day (default: today)")
    p.add_argument("--recent", type=int, default=7, help="days back for orders delivered late")
    p.add_argument("--out", type=Path, default=Path("cx_actions"))
    p.add_argument("--order", default="order_id")
    p.add_argument("--email", default="email")
    p.add_argument("--promised", default="promised_date")
    p.add_argument("--delivered", default="delivered_date")
    p.add_argument("--carrier", default="carrier")
    args = p.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    rows = read_shipments(args.shipments, args.order, args.email, args.promised, args.delivered, args.carrier)
    still_out, arrived_late = late_lists(rows, as_of, args.recent)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "late_open.csv").write_text(to_csv(OPEN_HEADER, open_rows(still_out)), encoding="utf-8", newline="\n")
    (args.out / "late_delivered.csv").write_text(to_csv(DELIVERED_HEADER, delivered_rows(arrived_late)),
                                                 encoding="utf-8", newline="\n")

    print(f"As of {as_of}: {len(still_out)} late and not delivered yet, "
          f"{len(arrived_late)} delivered late in the last {args.recent} days -> {args.out}/")
    print("\nLate rate by carrier (delivered orders):")
    for c in carrier_late_rates(rows):
        note = "  few orders, not a trend" if c["delivered"] < MIN_CARRIER_ORDERS else ""
        print(f"  {c['carrier']:<16} {c['late']:>5} of {c['delivered']:<6} {c['late_rate']:6.1%}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
