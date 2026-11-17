"""What the browser page (docs/index.html) calls.

The page runs this repository's Python in the browser (Pyodide), so it uses
the same functions as the command line and the same tests cover both. Each
function takes the path of the file the user picked and returns JSON with
everything the page shows and lets the user download. A file the tools cannot
read comes back as {"error": "..."} with the reason, not as a crash. Nothing
here opens a network connection.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import late_orders as lo
import review_triage as rt


def _guarded(fn):
    def run(*args):
        try:
            return json.dumps(fn(*args), default=str)
        except (SystemExit, ValueError, KeyError) as e:
            return json.dumps({"error": str(e) or e.__class__.__name__})
    return run


@_guarded
def late(path: str, as_of: str = "", recent: int = 7, order: str = "order_id", email: str = "email",
         promised: str = "promised_date", delivered: str = "delivered_date", carrier: str = "carrier") -> dict:
    day = date.fromisoformat(as_of) if as_of else date.today()
    rows = lo.read_shipments(Path(path), order or "order_id", email or "email", promised or "promised_date",
                             delivered or "delivered_date", carrier or "carrier")
    still_out, arrived_late = lo.late_lists(rows, day, int(recent))
    open_rows, delivered_rows = lo.open_rows(still_out), lo.delivered_rows(arrived_late)
    return {
        "as_of": day.isoformat(),
        "shipments": len(rows),
        "open_header": lo.OPEN_HEADER, "open": open_rows,
        "delivered_header": lo.DELIVERED_HEADER, "delivered": delivered_rows,
        "carriers": lo.carrier_late_rates(rows), "min_carrier_orders": lo.MIN_CARRIER_ORDERS,
        "open_csv": lo.to_csv(lo.OPEN_HEADER, open_rows),
        "delivered_csv": lo.to_csv(lo.DELIVERED_HEADER, delivered_rows),
    }


def _triage(reviews: list[dict], lang: str, max_rating: float) -> dict:
    if not reviews:
        raise ValueError("No reviews with a rating in this file.")
    queue = rt.triage(reviews, lang, float(max_rating))
    summary = rt.theme_summary(reviews, lang)
    rows = rt.triage_rows(queue)
    by_theme: dict[str, int] = {}
    for r in queue:
        by_theme[r["theme"]] = by_theme.get(r["theme"], 0) + 1
    return {
        "reviews": len(reviews),
        "queued": len(queue),
        "by_theme": by_theme,
        "header": rt.TRIAGE_HEADER, "queue": rows,
        "themes_header": rt.THEMES_HEADER, "themes": rt.theme_rows(summary),
        "triage_csv": rt.to_csv(rt.TRIAGE_HEADER, rows),
        "themes_csv": rt.to_csv(rt.THEMES_HEADER, rt.theme_rows(summary)),
    }


@_guarded
def triage(path: str, lang: str = "it", max_rating: float = 2, columns: str = "{}") -> dict:
    chosen = {k: v for k, v in json.loads(columns or "{}").items() if v}
    return _triage(rt.read_reviews(Path(path), chosen), lang, max_rating)


@_guarded
def olist_demo(reviews_path: str, comments_path: str) -> dict:
    """The real Olist data comes as two files (scores, comment texts): join them
    the way the analysis does, then run the same triage in Portuguese."""
    score = {r["review_id"]: r["review_score"] for r in lo.read_csv(Path(reviews_path))}
    reviews = [{"rating": float(score[c["review_id"]]), "text": c["comment"].strip(), "date": "",
                "order_id": c["review_id"], "email": ""}
               for c in lo.read_csv(Path(comments_path)) if c["review_id"] in score]
    return _triage(reviews, "pt", 2)
