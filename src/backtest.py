"""Would the hold list have been right? Nine checks on two years of a real wholesaler.

On each date the items are judged with what was known that day. Then only the purchases made
AFTER the check are counted: how many customers sent the item back within 60 days of buying it.

Also: what a plain list by value shows, and whether a customer who sends goods back is leaving.

Writes docs/credit_notes.json (read by the page) and reports/credit_notes.md.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import credit_notes as cn

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "wholesale_lines.csv.gz"
CHECKS = [date(2010, 3, 1) + timedelta(60 * i) for i in range(9)]
AFTER, BESTSELLERS = 60, 20
LEAVING_DATES = [date(2010, 9, 1) + timedelta(30 * i) for i in range(12)]


def after(sales: list, sent_back: list, day: date) -> tuple[dict, dict]:
    """Customers who bought each item in the 60 days after `day`, and those who then sent it back."""
    end = day + timedelta(AFTER)
    bought, back = defaultdict(set), defaultdict(set)
    for s in sales:
        if day < s.day <= end:
            bought[s.item].add(s.account)
    for b in sent_back:
        if day < b.bought <= end and (b.day - b.bought).days <= AFTER:
            back[b.item].add(b.account)
    return bought, back


def total(items, bought: dict, back: dict) -> list[int]:
    return [sum(len(bought[i]) for i in items), sum(len(back[i]) for i in items)]


def checks(book: dict, sent_back: list) -> list[dict]:
    out = []
    for day in CHECKS:
        r = cn.judge(book, sent_back, day)
        held = {x["item"] for x in cn.holds(r)}
        bought, back = after(book["sales"], sent_back, day)
        revenue = Counter()
        for s in book["sales"]:
            if r["since"] < s.day <= day:
                revenue[s.item] += s.value
        best = [i for i, _ in revenue.most_common(BESTSELLERS)]
        out.append({"day": day.isoformat(), "sold": len(r["items"]), "usual": r["usual"], "held": len(held),
                    "held_after": total(held, bought, back),
                    "other_after": total([i for i in bought if i not in held], bought, back),
                    "best_held": sum(i in held for i in best),
                    "best_held_after": total([i for i in best if i in held], bought, back),
                    "best_other_after": total([i for i in best if i not in held], bought, back)})
    return out


def leaving(book: dict, sent_back: list) -> dict:
    """Customers alike in orders so far and days since the last one: do those who have just sent
    goods back order less in the next 90 days?"""
    days, back = defaultdict(set), defaultdict(set)
    for s in book["sales"]:
        days[s.account].add(s.day)
    for b in sent_back:
        back[b.account].add(b.day)
    groups = defaultdict(lambda: [0, 0, 0, 0])
    for now in LEAVING_DATES:
        for account, all_days in days.items():
            past = [d for d in all_days if d <= now]
            if len(past) < 3 or (now - max(past)).days >= 60:
                continue
            group = (min(len(past), 12) // 3, (now - max(past)).days // 20)
            again = any(now < d <= now + timedelta(90) for d in all_days)
            g, at = groups[group], 0 if any(now - timedelta(30) < d <= now for d in back[account]) else 2
            g[at] += 1
            g[at + 1] += again
    compared = [g for g in groups.values() if g[0] >= 20 and g[2] >= 20]
    n = sum(g[0] for g in compared)
    return {"groups": len(compared), "not_lower": sum(g[1] / g[0] >= g[3] / g[2] - 0.005 for g in compared), "cases": n,
            "sent_back_share": sum(g[1] for g in compared) / n,
            "similar_share": sum(g[0] * g[3] / g[2] for g in compared) / n}


def run() -> dict:
    book = cn.load(DATA)
    kinds = cn.sort_credits(book)
    sent_back = kinds["sent_back"]
    each = checks(book, sent_back)
    pool = {k: [sum(c[k][0] for c in each), sum(c[k][1] for c in each)]
            for k in ("held_after", "other_after", "best_held_after", "best_other_after")}
    buyers, back = defaultdict(set), defaultdict(set)
    revenue = Counter()
    for s in book["sales"]:
        buyers[s.item].add(s.account)
        revenue[s.item] += s.value
    for b in sent_back:
        back[b.item].add(b.account)
    rank = {i: n for n, (i, _) in enumerate(revenue.most_common(), 1)}
    item = lambda i: {"item": i, "description": book["items"].get(i, ""), "buyers": len(buyers[i]),  # noqa: E731
                      "back": len(back[i]), "revenue_rank": rank[i]}
    return {
        "data": {"lines": len(book["sales"]) + len(book["credits"]), "customers": len({s.account for s in book["sales"]}),
                 "customers_with_credit": len({c.account for c in book["credits"]}), "currency": "GBP"},
        "credits": {k: {"lines": len(v), "value": round(sum(x.value for x in v))} for k, v in kinds.items()},
        "by_value": [{**item(x["item"]), "value": round(x["value"])} for x in cn.by_value(book, 5)],
        "by_customers": [item(i) for i, _ in sorted(back.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]],
        "checks": each, "pooled": pool, "best_held": sum(c["best_held"] for c in each), "leaving": leaving(book, sent_back),
    }


def rounded(x):
    if isinstance(x, float):
        return round(x, 4)
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    return [rounded(v) for v in x] if isinstance(x, list) else x


def rate(pair: list[int]) -> str:
    return f"{100 * pair[1] / pair[0]:.1f}%"


def markdown(r: dict) -> str:
    p, c = r["pooled"], r["credits"]
    all_value = sum(x["value"] for x in c.values())
    out = [
        "# Two years of credit notes at a real wholesaler", "",
        f"{r['data']['lines']:,} invoice and cancellation lines, {r['data']['customers']:,} customers (UCI *Online Retail II*, "
        f"a UK gift wholesaler, December 2009 to December 2011). {r['data']['customers_with_credit']:,} customers have at least "
        "one credit line. My own RFM analysis of this data drops those lines in the first cleaning step.", "",
        "## What the credit lines are", "", "| Kind | Lines | Value |", "| --- | ---: | ---: |",
        f"| Goods sent back, at least a day after the purchase | {c['sent_back']['lines']:,} | GBP {c['sent_back']['value']:,} |",
        f"| Same-day corrections | {c['correction']['lines']:,} | GBP {c['correction']['value']:,} |",
        f"| No earlier purchase in the file | {c['unmatched']['lines']:,} | GBP {c['unmatched']['value']:,} |", "",
        f"{c['correction']['value'] / all_value:.0%} of the credited money was cancelled on the day it was invoiced.", "",
        "## The same two years, two lists", "",
        "| Most credited, by value | Value | Customers who sent it back |", "| --- | ---: | ---: |"]
    out += [f"| {x['description']} | GBP {x['value']:,} | {x['back']} of {x['buyers']:,} |" for x in r["by_value"]]
    out += ["", "| Sent back by most customers | Customers who sent it back | Share | Rank by revenue |", "| --- | ---: | ---: | ---: |"]
    out += [f"| {x['description']} | {x['back']} of {x['buyers']:,} | {x['back'] / x['buyers']:.0%} | {x['revenue_rank']} |"
            for x in r["by_customers"]]
    out += ["", "## Was the hold list right?", "",
            "Nine checks, 60 days apart. Only purchases made after each check are counted.", "",
            "| Check | Items sold | On hold | Sent back after: on hold | Sent back after: the rest | Bestsellers on hold (of 20) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |"]
    out += [f"| {x['day']} | {x['sold']:,} | {x['held']} | {rate(x['held_after'])} | {rate(x['other_after'])} | {x['best_held']} |"
            for x in r["checks"]]
    out += [f"| **All nine** | | | **{rate(p['held_after'])}** ({p['held_after'][1]:,} of {p['held_after'][0]:,}) | "
            f"**{rate(p['other_after'])}** ({p['other_after'][1]:,} of {p['other_after'][0]:,}) | {r['best_held']} of {20 * len(r['checks'])} |",
            "", f"Among the 20 bestsellers of each check, the ones on hold were sent back by {rate(p['best_held_after'])} of the "
            f"customers who bought them afterwards, the others by {rate(p['best_other_after'])}.", "",
            "## Is a customer who sends goods back leaving?", ""]
    v = r["leaving"]
    out += [f"No. In {v['not_lower']} of {v['groups']} groups of similar customers (same number of orders so far, same days since the "
            f"last one), those who had just sent goods back ordered again at least as often: {v['sent_back_share']:.0%} within 90 "
            f"days, against {v['similar_share']:.0%} ({v['cases']:,} cases). So the tool points at items, not at customers to save.", ""]
    return "\n".join(out)


def main() -> None:
    r = rounded(run())
    (ROOT / "docs" / "credit_notes.json").write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "reports" / "credit_notes.md").write_text(markdown(r), encoding="utf-8", newline="\n")
    print(json.dumps({k: r[k] for k in ("credits", "pooled", "best_held", "leaving")}, indent=1))


if __name__ == "__main__":
    main()
