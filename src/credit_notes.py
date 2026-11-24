"""What B2B customers say by sending goods back.

B2B customers do not write reviews. The unhappy one asks for a credit note, and the credit
note stays in the ERP, where the people who prepare the next campaign never see it.

    python src/credit_notes.py --lines lines.csv                          what to hold, whom to ask
    python src/credit_notes.py --lines lines.csv --campaign catalogue.csv  check the items you want to push

The lines file is one export with invoices and credit notes: customer, date, item, quantity.
Three rules, no AI:

1. A credit line is goods sent back only if the same customer bought the same item on an
   earlier day. Same day = a typing correction. No earlier purchase = not counted.
2. Customers are counted, not pieces: one customer who returns 1,000 pieces is one problem.
3. An item is on hold when at least 3 customers sent it back in the last 60 days, at least 20
   bought it, and the share is at least 3 times the one of all the other items in the file.

Pure standard library.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

from erp_export import FileProblem, parse_day, parse_number, read_rows, to_csv

DAYS, MIN_BUYERS, MIN_BACK, TIMES, ASK_DAYS = 60, 20, 3, 3, 30
CREDIT_WORDS = ("credit", "credito", "td04", "reso", "return")  # TD04: credit note in Italian e-invoicing

ITEM_HEADER = ["item", "description", "customers_who_bought", "customers_who_sent_it_back", "share", "times_the_others",
               "value_sent_back", "main_reason"]
CUSTOMER_HEADER = ["item", "description", "customer", "name", "rep", "what", "bought_on", "sent_back_on", "reason"]
CAMPAIGN_HEADER = ["item", "description", "verdict", "customers_who_bought", "customers_who_sent_it_back", "share",
                   "times_the_others"]


class Line(NamedTuple):
    account: str
    item: str
    day: date
    quantity: float
    value: float
    reason: str = ""


class Back(NamedTuple):
    """Goods sent back: the credit line and the day the customer had bought them."""
    account: str
    item: str
    bought: date
    day: date
    value: float
    reason: str


def load(path: Path) -> dict:
    rows, fields = read_rows(path, ("account", "date", "item", "quantity"))
    book = {"sales": [], "credits": [], "names": {}, "reps": {}, "items": {}, "no_quantity": 0}
    for n, r in enumerate(rows, start=2):
        if not r["account"] or not r["item"]:
            continue
        try:
            day, quantity = parse_day(r["date"]), parse_number(r["quantity"])
            value = parse_number(r["amount"]) if r.get("amount") else quantity * parse_number(r.get("price", ""))
        except FileProblem as e:
            raise FileProblem(f"line {n}: {e}") from None
        if day is None:
            continue
        for field, key, book_key in (("name", "account", "names"), ("rep", "account", "reps"), ("description", "item", "items")):
            if r.get(field):
                book[book_key][r[key]] = r[field]
        if not quantity:  # a price correction or a discount: money moved, no goods did
            book["no_quantity"] += 1
            continue
        credit = quantity < 0 or any(w in r.get("type", "").lower() for w in CREDIT_WORDS)
        book["credits" if credit else "sales"].append(
            Line(r["account"], r["item"], day, abs(quantity), abs(value), r.get("reason", "")))
    if not book["sales"]:
        raise FileProblem("no sales lines in the file")
    return book


def sort_credits(book: dict) -> dict[str, list]:
    """Split the credit lines into goods sent back, same-day corrections and unmatched lines (rule 1)."""
    bought = defaultdict(list)
    for s in book["sales"]:
        bought[s.account, s.item].append((s.day, s.quantity))
    for b in bought.values():
        b.sort()
    out = {"sent_back": [], "correction": [], "unmatched": []}
    for c in book["credits"]:
        days = [d for d, q in bought.get((c.account, c.item), ()) if d <= c.day and q >= c.quantity]
        if not days:
            out["unmatched"].append(c)
        elif days[-1] == c.day:
            out["correction"].append(c)
        else:
            out["sent_back"].append(Back(c.account, c.item, days[-1], c.day, c.value, c.reason))
    return out


def judge(book: dict, sent_back: list[Back], as_of: date, days: int = DAYS, min_buyers: int = MIN_BUYERS,
          min_back: int = MIN_BACK, times: float = TIMES) -> dict:
    """For every item sold in the window: who bought it, who sent it back, and the verdict (rules 2 and 3)."""
    since = as_of - timedelta(days)
    buyers, back, value, reasons = defaultdict(set), defaultdict(set), Counter(), defaultdict(Counter)
    for s in book["sales"]:
        if since < s.day <= as_of:
            buyers[s.item].add(s.account)
    for b in sent_back:
        if since < b.day <= as_of:
            back[b.item].add(b.account)
            value[b.item] += b.value
            reasons[b.item][b.reason] += bool(b.reason)
    if not buyers:
        raise FileProblem(f"no sales in the {days} days before {as_of}")
    all_buyers, all_back = sum(len(a) for a in buyers.values()), sum(len(back[i]) for i in buyers)
    items = {}
    for i, a in buyers.items():
        n, k = len(a), len(back[i])
        share = k / n
        others = (all_back - k) / (all_buyers - n) if all_buyers > n else 0.0
        verdict = "few" if n < min_buyers else "hold" if k >= min_back and share >= times * others else "ok"
        items[i] = {"item": i, "description": book["items"].get(i, ""), "buyers": n, "back": k, "share": share,
                    "times": round(share / others, 1) if others else None, "value": round(value[i], 2),
                    "reason": next((r for r, c in reasons[i].most_common(1) if c), ""), "verdict": verdict}
    return {"as_of": as_of, "since": since, "usual": all_back / all_buyers, "items": items}


def holds(result: dict) -> list[dict]:
    return sorted((x for x in result["items"].values() if x["verdict"] == "hold"), key=lambda x: (-x["back"], x["item"]))


def customers(book: dict, sent_back: list[Back], result: dict, ask_days: int = ASK_DAYS) -> list[list]:
    """For the items on hold: who sent them back, and who bought them lately and has not complained yet."""
    held, out, done = {x["item"] for x in holds(result)}, [], set()
    who = lambda a: [a, book["names"].get(a, ""), book["reps"].get(a, "")]  # noqa: E731
    for b in sorted(sent_back, key=lambda b: (b.item, b.day, b.account)):
        if b.item in held and result["since"] < b.day <= result["as_of"]:
            done.add((b.account, b.item))
            out.append([b.item, book["items"].get(b.item, ""), *who(b.account), "sent it back",
                        b.bought.isoformat(), b.day.isoformat(), b.reason])
    last = {}
    for s in book["sales"]:
        if s.item in held and result["as_of"] - timedelta(ask_days) < s.day <= result["as_of"]:
            last[s.item, s.account] = max(s.day, last.get((s.item, s.account), s.day))
    for (item, account), day in sorted(last.items()):
        if (account, item) not in done:
            out.append([item, book["items"].get(item, ""), *who(account), "ask before it comes back", day.isoformat(), "", ""])
    return out


def check_campaign(codes: list[str], book: dict, result: dict) -> list[dict]:
    known = {s.item for s in book["sales"]}
    blank = {"buyers": 0, "back": 0, "share": 0.0, "times": None}
    return [result["items"].get(c) or {"item": c, "description": book["items"].get(c, ""), **blank,
                                       "verdict": "few" if c in known else "unknown"} for c in dict.fromkeys(codes)]


def by_value(book: dict, top: int = 5) -> list[dict]:
    """What a plain "most returned items" list shows: credited value, corrections included."""
    total = Counter()
    for c in book["credits"]:
        total[c.item] += c.value
    return [{"item": i, "description": book["items"].get(i, ""), "value": round(v, 2)} for i, v in total.most_common(top)]


def item_rows(items: list[dict]) -> list[list]:
    return [[x["item"], x["description"], x["buyers"], x["back"], f"{x['share']:.1%}", x["times"], x["value"], x["reason"]]
            for x in items]


def campaign_rows(checked: list[dict]) -> list[list]:
    return [[x["item"], x["description"], x["verdict"], x["buyers"], x["back"], f"{x['share']:.1%}", x["times"]]
            for x in checked]


def run(lines: Path, campaign: Path | None = None, as_of: date | None = None, days: int = DAYS,
        min_buyers: int = MIN_BUYERS, min_back: int = MIN_BACK, times: float = TIMES) -> dict:
    book = load(lines)
    kinds = sort_credits(book)
    end = as_of or max(x.day for x in book["sales"] + book["credits"])
    result = judge(book, kinds["sent_back"], end, days, min_buyers, min_back, times)
    people = customers(book, kinds["sent_back"], result)
    checked = None
    if campaign:
        codes = [r["item"] for r in read_rows(campaign, ("item",))[0] if r["item"]]
        checked = check_campaign(codes, book, result)
    files = {"items_on_hold.csv": to_csv(ITEM_HEADER, item_rows(holds(result))),
             "customers.csv": to_csv(CUSTOMER_HEADER, people)}
    if checked is not None:
        files["campaign.csv"] = to_csv(CAMPAIGN_HEADER, campaign_rows(checked))
    return {"as_of": end, "days": days, "usual": result["usual"], "sold": len(result["items"]), "hold": holds(result),
            "customers": people, "campaign": checked, "by_value": by_value(book), "files": files,
            "credits": {k: {"lines": len(v), "value": round(sum(x.value for x in v), 2)} for k, v in kinds.items()},
            "no_quantity": book["no_quantity"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lines", type=Path, required=True, help="invoice and credit note lines (CSV, also gzipped)")
    p.add_argument("--campaign", type=Path, help="CSV with the items you want to promote")
    p.add_argument("--as-of", default="", help="day of the check (default: the last date in the file)")
    p.add_argument("--days", type=int, default=DAYS)
    p.add_argument("--min-buyers", type=int, default=MIN_BUYERS)
    p.add_argument("--min-back", type=int, default=MIN_BACK)
    p.add_argument("--times", type=float, default=TIMES, help="how many times the share of the other items")
    p.add_argument("--out", type=Path, default=Path("actions"))
    args = p.parse_args(argv)
    try:
        r = run(args.lines, args.campaign, parse_day(args.as_of), args.days, args.min_buyers, args.min_back, args.times)
    except FileProblem as e:
        raise SystemExit(f"Cannot use the file: {e}") from None
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in r["files"].items():
        (args.out / name).write_text(text, encoding="utf-8", newline="\n")
    c = r["credits"]
    print(f"Credit lines: {c['sent_back']['lines']:,} goods sent back, {c['correction']['lines']:,} same-day corrections "
          f"(left out, {c['correction']['value']:,.0f}), {c['unmatched']['lines']:,} without a purchase in the file.")
    print(f"Usual share of customers who send an item back in {r['days']} days: {r['usual']:.1%}. "
          f"{len(r['hold'])} of {r['sold']:,} items on hold:")
    for x in r["hold"][:10]:
        print(f"  {x['item']:<8} {x['description'][:34]:<34} {x['back']} of {x['buyers']} customers"
              + (f", {x['times']} times the other items" if x["times"] else "")
              + (f", {x['reason']}" if x["reason"] else ""))
    if r["campaign"] is not None:
        n = Counter(x["verdict"] for x in r["campaign"])
        print(f"Campaign: {n['hold']} on hold, {n['ok']} ok, {n['few']} sold too little to say, {n['unknown']} not in the file.")
    print(f"-> {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
