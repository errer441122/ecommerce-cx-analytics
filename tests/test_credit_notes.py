"""The three rules, on small files written by hand and on the real wholesale data."""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import credit_notes as cn  # noqa: E402
import erp_export as erp  # noqa: E402
import web_app  # noqa: E402

DEMO = ROOT / "data" / "wholesale_demo.csv.gz"
AS_OF = date(2026, 3, 31)


def write(text: str, name: str = "lines.csv", encoding: str = "utf-8") -> Path:
    path = Path(tempfile.mkdtemp()) / name
    path.write_bytes(text.encode(encoding))
    return path


def lines(*rows: str) -> Path:
    return write("customer,date,item,quantity,price\n" + "\n".join(rows) + "\n")


def shop(back: int, buyers: int = 40) -> Path:
    """`buyers` customers buy items A and B on 1 March; `back` of them return one A on 20 March."""
    rows = [f"C{i:02d},2026-03-01,{item},10,5" for i in range(buyers) for item in ("A", "B")]
    rows += [f"C{i:02d},2026-03-20,A,-1,5" for i in range(back)]
    rows += ["C00,2026-03-21,B,-1,5"]
    return lines(*rows)


def kinds(path: Path) -> dict[str, int]:
    return {k: len(v) for k, v in cn.sort_credits(cn.load(path)).items()}


class ReadsWhatAnErpWrites(unittest.TestCase):
    def test_numbers(self):
        for text, value in (("49,90", 49.9), ("1.234,56", 1234.56), ("1,234.56", 1234.56), ("3-", -3), ("-3", -3), ("", 0)):
            self.assertAlmostEqual(erp.parse_number(text), value, msg=text)

    def test_italian_export_with_credit_note_type_and_old_excel_encoding(self):
        path = write("Codice cliente;Ragione sociale;Agente;Data documento;Tipo documento;Codice articolo;Descrizione;Quantità;Importo;Causale\r\n"
                     "10;Rossi Srl;Bianchi;01/03/2026;TD01;X1;Valvola;4;400,00;\r\n"
                     "10;Rossi Srl;Bianchi;15/03/2026;TD04;X1;Valvola;1;100,00;Danneggiato\r\n", encoding="cp1252")
        book = cn.load(path)
        self.assertEqual((book["names"]["10"], book["reps"]["10"], book["items"]["X1"]), ("Rossi Srl", "Bianchi", "Valvola"))
        (back,) = cn.sort_credits(book)["sent_back"]  # a positive quantity on a TD04 document is a credit
        self.assertEqual((back.bought, back.day, back.value, back.reason), (date(2026, 3, 1), date(2026, 3, 15), 100.0, "Danneggiato"))

    def test_gzip(self):
        path = Path(tempfile.mkdtemp()) / "l.csv.gz"
        path.write_bytes(gzip.compress(b"customer,date,item,quantity\nA,2026-03-01,X,1\n"))
        self.assertEqual(len(cn.load(path)["sales"]), 1)

    def test_problems_are_explained(self):
        for text, says in (("colore,prezzo\nrosso,1\n", "column not found"), ("customer,date,item,quantity\nA,1/13/2026,X,1\n", "line 2"),
                           ("customer,date,item,quantity\nA,2026-03-01,X,-1\n", "no sales lines")):
            with self.assertRaisesRegex(erp.FileProblem, says):
                cn.load(write(text))


class Rule1WhatCountsAsSentBack(unittest.TestCase):
    def test_same_day_is_a_correction_not_a_return(self):
        self.assertEqual(kinds(lines("A,2026-03-01,X,80995,2", "A,2026-03-01,X,-80995,2")),
                         {"sent_back": 0, "correction": 1, "unmatched": 0})

    def test_next_day_is_a_return(self):
        self.assertEqual(kinds(lines("A,2026-03-01,X,10,2", "A,2026-03-02,X,-3,2"))["sent_back"], 1)

    def test_nobody_returns_what_they_did_not_buy(self):
        self.assertEqual(kinds(lines("A,2026-03-01,X,10,2", "B,2026-03-05,X,-1,2", "A,2026-03-05,Y,-1,2", "A,2026-03-05,X,-11,2")),
                         {"sent_back": 0, "correction": 0, "unmatched": 3})

    def test_price_corrections_without_quantity_are_left_out(self):
        book = cn.load(write("customer,date,item,quantity,amount\nA,2026-03-01,X,1,9\nA,2026-03-05,X,0,-2\n"))
        self.assertEqual((book["no_quantity"], book["credits"]), (1, []))


class Rules2And3TheVerdict(unittest.TestCase):
    def verdict(self, path, item="A", **kw):
        book = cn.load(path)
        return cn.judge(book, cn.sort_credits(book)["sent_back"], AS_OF, **kw)["items"][item]

    def test_customers_are_counted_not_pieces(self):
        rows = [f"C{i:02d},2026-03-01,A,10,5" for i in range(40)] + [f"C{i:02d},2026-03-01,B,10,5" for i in range(40)]
        rows += ["C00,2026-03-20,A,-10,5", "C00,2026-03-21,A,-9,5", "C01,2026-03-21,B,-1,5"]
        self.assertEqual(self.verdict(lines(*rows))["back"], 1)

    def test_hold(self):
        x = self.verdict(shop(back=8), times=1.5)
        self.assertEqual((x["verdict"], x["back"], x["buyers"]), ("hold", 8, 40))
        self.assertEqual(x["times"], 8.0)  # 8 of 40 against 1 of 40 for the other item

    def test_the_only_item_sent_back_has_nothing_to_compare_with(self):
        rows = [f"C{i:02d},2026-03-01,{item},10,5" for i in range(40) for item in "AB"]
        x = self.verdict(lines(*rows, *[f"C{i:02d},2026-03-20,A,-1,5" for i in range(3)]))
        self.assertEqual((x["verdict"], x["times"]), ("hold", None))

    def test_each_threshold_matters(self):
        self.assertEqual(self.verdict(shop(back=2), times=1.5)["verdict"], "ok")              # fewer than 3 customers
        self.assertEqual(self.verdict(shop(back=8), times=9)["verdict"], "ok")                # not enough times the others
        self.assertEqual(self.verdict(shop(back=8, buyers=19), times=1.5)["verdict"], "few")  # fewer than 20 buyers

    def test_a_return_older_than_the_window_no_longer_counts(self):
        rows = [f"C{i:02d},2026-06-01,A,10,5" for i in range(40)]
        path = lines(*shop(back=8).read_text().splitlines()[1:], *rows)
        book = cn.load(path)
        r = cn.judge(book, cn.sort_credits(book)["sent_back"], date(2026, 6, 10), days=30)
        self.assertEqual((r["items"]["A"]["buyers"], r["items"]["A"]["back"]), (40, 0))

    def test_a_window_without_sales_is_explained(self):
        with self.assertRaisesRegex(erp.FileProblem, "no sales in the 30 days"):
            cn.judge(cn.load(shop(back=8)), [], date(2026, 6, 1), days=30)

    def test_customers_to_ask_exclude_those_who_already_sent_it_back(self):
        book = cn.load(shop(back=8))
        back = cn.sort_credits(book)["sent_back"]
        people = cn.customers(book, back, cn.judge(book, back, date(2026, 3, 30), times=1.5))
        sent = {p[2] for p in people if p[5] == "sent it back"}
        ask = {p[2] for p in people if p[5].startswith("ask")}
        self.assertEqual((len(sent), len(ask), sent & ask), (8, 32, set()))

    def test_campaign_check(self):
        book = cn.load(shop(back=8))
        back = cn.sort_credits(book)["sent_back"]
        r = cn.judge(book, back, AS_OF, times=1.5)
        self.assertEqual([x["verdict"] for x in cn.check_campaign(["A", "B", "Z", "A"], book, r)], ["hold", "ok", "unknown"])


class RealDataAndPage(unittest.TestCase):
    def test_demo_holds_the_bestseller(self):
        r = json.loads(web_app.demo(str(DEMO)))
        best = r["campaign"][0]
        self.assertEqual((best["item"], best["verdict"]), ("22423", "hold"))  # Regency cakestand, first by revenue
        self.assertEqual(len(r["campaign"]), 20)
        self.assertGreater(r["credits"]["correction"]["lines"], 0)
        self.assertIn("22423", r["files"]["campaign.csv"])

    def test_typed_codes(self):
        r = json.loads(web_app.check(str(DEMO), "22423, 85123A;\n99999X"))
        self.assertEqual([x["verdict"] for x in r["campaign"]], ["hold", "ok", "unknown"])

    def test_errors_come_back_as_text(self):
        self.assertIn("column not found", json.loads(web_app.check(str(write("a,b\n1,2\n"))))["error"])

    def test_command_line(self):
        out = io.StringIO()
        campaign = write("Codice articolo\n22423\n85123A\n", "campaign.csv")
        with contextlib.redirect_stdout(out):
            cn.main(["--lines", str(DEMO), "--campaign", str(campaign), "--out", str(campaign.parent / "a")])
        self.assertIn("Campaign: 1 on hold, 1 ok", out.getvalue())
        self.assertTrue((campaign.parent / "a" / "customers.csv").exists())

    def test_the_page_shows_the_published_numbers(self):
        r = json.loads((ROOT / "docs" / "credit_notes.json").read_text(encoding="utf-8"))
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        p, top, best = r["pooled"], r["by_value"][0], r["by_customers"][0]
        rate = lambda x: f"{100 * x[1] / x[0]:.1f}%"  # noqa: E731
        for shown in (rate(p["held_after"]), rate(p["other_after"]), rate(p["best_held_after"]), rate(p["best_other_after"]),
                      f"£{top['value']:,}", f"{best['back']} of {best['buyers']:,}", f"{r['best_held']} of {20 * len(r['checks'])}",
                      f"{r['leaving']['not_lower']} of {r['leaving']['groups']}", f"£{r['credits']['correction']['value']:,}"):
            self.assertIn(shown, page)


if __name__ == "__main__":
    unittest.main()
