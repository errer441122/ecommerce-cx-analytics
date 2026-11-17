"""The two operational tools: late orders and review triage."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import late_orders as lo  # noqa: E402
import review_triage as rt  # noqa: E402

SHIPMENTS = ROOT / "data" / "shipments_example.csv"
REVIEWS = ROOT / "data" / "reviews_example.csv"


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestLateOrders(unittest.TestCase):
    def test_dates_from_different_platforms(self):
        self.assertEqual(lo.parse_day("2026-05-20"), date(2026, 5, 20))
        self.assertEqual(lo.parse_day("2026-05-20 14:03:00 +0200"), date(2026, 5, 20))
        self.assertEqual(lo.parse_day("2026-05-20T14:03:00Z"), date(2026, 5, 20))
        self.assertEqual(lo.parse_day("25/05/2026"), date(2026, 5, 25))
        self.assertIsNone(lo.parse_day("  "))
        with self.assertRaises(ValueError):
            lo.parse_day("May 20")

    def test_late_lists_on_the_example(self):
        rows = lo.read_shipments(SHIPMENTS, "order_id", "email", "promised_date", "delivered_date", "carrier")
        still_out, arrived_late = lo.late_lists(rows, date(2026, 6, 1), recent=7)
        # longest wait first; #2006 is not due yet, #2007 arrived on the promised day
        self.assertEqual([r["order_id"] for r in still_out], ["#2002", "#2003", "#2008"])
        self.assertEqual([r["days_late"] for r in still_out], [10, 7, 2])
        # #2005 arrived late but 11 days ago, outside the 7-day window
        self.assertEqual([r["order_id"] for r in arrived_late], ["#2004"])

    def test_carrier_late_rate_counts_delivered_orders_only(self):
        rows = lo.read_shipments(SHIPMENTS, "order_id", "email", "promised_date", "delivered_date", "carrier")
        rates = {c["carrier"]: (c["late"], c["delivered"]) for c in lo.carrier_late_rates(rows)}
        self.assertEqual(rates, {"BRT": (0, 2), "GLS": (1, 1), "Poste": (1, 1)})

    def test_files_are_ready_for_klaviyo_and_customer_service(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lo.main(["--shipments", str(SHIPMENTS), "--as-of", "2026-06-01", "--out", tmp]), 0)
            open_rows = _rows(Path(tmp) / "late_open.csv")
            closed_rows = _rows(Path(tmp) / "late_delivered.csv")
        self.assertEqual({r["delivery_issue"] for r in open_rows}, {"open"})
        self.assertEqual(open_rows[0]["email"], "marco@example.com")
        self.assertEqual([r["delivery_issue"] for r in closed_rows], ["closed"])

    def test_a_missing_column_says_which_flag_to_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "s.csv"
            f.write_text("Order,Expected,Delivered\n1,2026-05-01,\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as e:
                lo.read_shipments(f, "order_id", "email", "promised_date", "delivered_date", "carrier")
        self.assertIn("--promised", str(e.exception))


class TestReviewTriage(unittest.TestCase):
    def test_most_urgent_first_and_routed(self):
        queue = rt.triage(rt.read_reviews(REVIEWS, {}), "it", max_rating=2)
        self.assertEqual([r["theme"] for r in queue], ["not_received", "product", "service", "delivery", "other"])
        self.assertEqual(queue[0]["owner"], "logistics + customer service")
        self.assertTrue(all(r["rating"] <= 2 for r in queue))

    def test_an_excerpt_cannot_carry_a_spreadsheet_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "r.csv"
            f.write_text('rating,body\n1,"=HYPERLINK(""http://x"") pacco non è arrivato"\n', encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rt.main(["--reviews", str(f), "--out", tmp])
            row = _rows(Path(tmp) / "triage.csv")[0]
        self.assertTrue(row["excerpt"].startswith("'="))
        self.assertEqual(row["theme"], "not_received")

    def test_reproduces_the_published_themes_on_the_real_olist_comments(self):
        # Same keywords as the analysis: on the 38,814 real comments the theme
        # counts and average ratings must match reports/cx_driver_metrics.json.
        score = {r["review_id"]: r["review_score"] for r in _rows(ROOT / "data" / "olist_reviews.csv")}
        with tempfile.TemporaryDirectory() as tmp:
            joined = Path(tmp) / "olist.csv"
            with joined.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["rating", "comment"])
                for c in _rows(ROOT / "data" / "olist_review_comments.csv"):
                    if c["review_id"] in score:
                        w.writerow([score[c["review_id"]], c["comment"]])
            mine = {s["theme"]: (s["mentions"], round(s["avg_rating"], 2))
                    for s in rt.theme_summary(rt.read_reviews(joined, {}), "pt")}
        published = json.loads((ROOT / "reports" / "cx_driver_metrics.json").read_text(encoding="utf-8"))
        names = {"Produto & qualidade": "product", "Entrega & prazo": "delivery",
                 "Recomendação / satisfação": "praise", "Não recebido / faltou": "not_received",
                 "Atendimento": "service"}
        for t in published["comment_themes"]:
            with self.subTest(t["theme"]):
                self.assertEqual(mine[names[t["theme"]]], (t["mentions"], t["avg_review_score"]))


if __name__ == "__main__":
    unittest.main()
