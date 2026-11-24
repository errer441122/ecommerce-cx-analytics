"""What the browser page (docs/index.html) calls.

The page runs this repository's Python in the browser (Pyodide), so it uses the same
functions, and the same tests cover it, as the command line. A file that cannot be used
comes back as {"error": "..."} with the reason. Nothing here opens a network connection.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from pathlib import Path

import credit_notes as cn
from erp_export import FileProblem, parse_day

BESTSELLERS = 20


def _guarded(fn):
    def run(*args):
        try:
            return json.dumps(fn(*args), default=str)
        except FileProblem as e:
            return json.dumps({"error": str(e)})
    return run


def _page(r: dict) -> dict:
    """The lists can be long: the page shows the beginning, the files hold everything."""
    return {**r, "hold": r["hold"][:12], "held": len(r["hold"]), "customers": len(r["customers"]),
            "to_ask": len({c[2] for c in r["customers"] if c[5].startswith("ask")})}


@_guarded
def check(lines_path: str, codes: str = "", as_of: str = "", days: int = cn.DAYS, min_buyers: int = cn.MIN_BUYERS,
          min_back: int = cn.MIN_BACK, times: float = cn.TIMES) -> dict:
    """`codes` are the items of the campaign, as typed or pasted: one per line, or separated by , ; or spaces."""
    items = [c for c in re.split(r"[\s,;]+", codes) if c]
    with tempfile.TemporaryDirectory() as tmp:
        campaign = None
        if items:
            campaign = Path(tmp) / "campaign.csv"
            campaign.write_text("item\n" + "\n".join(items) + "\n", encoding="utf-8")
        return _page(cn.run(Path(lines_path), campaign, parse_day(as_of), int(days), int(min_buyers), int(min_back),
                            float(times)))


@_guarded
def demo(lines_path: str) -> dict:
    """A newsletter with the 20 bestsellers of the last 60 days, on the public wholesale data."""
    book = cn.load(Path(lines_path))
    end = max(s.day for s in book["sales"])
    r = cn.run(Path(lines_path))
    result = cn.judge(book, cn.sort_credits(book)["sent_back"], end)
    revenue = Counter()
    for s in book["sales"]:
        if result["since"] < s.day <= end:
            revenue[s.item] += s.value
    r["campaign"] = cn.check_campaign([i for i, _ in revenue.most_common(BESTSELLERS)], book, result)
    r["files"]["campaign.csv"] = cn.to_csv(cn.CAMPAIGN_HEADER, cn.campaign_rows(r["campaign"]))
    return _page(r)
