"""Negative reviews, sorted by what to handle first and who should handle it.

    python src/review_triage.py --reviews reviews.csv --lang it

Reads a reviews export (rating 1-5 and the review text, plus date, order and
email when the file has them), tags every review with themes from a keyword
list the team can read and edit, and writes into --out (default cx_actions/):

- triage.csv   reviews with --max-rating stars or fewer (default 2), most
               urgent first: not received, then product problems, then
               delivery and service. Each row says who it goes to.
- themes.csv   every theme: how many reviews mention it and their average
               rating. The monthly voice-of-customer summary.

The themes are keywords, not a language model: every match can be checked by
reading the review, and the lists below are there to extend. On the 38,814
real Olist comments (Portuguese) they reproduce the theme counts of
reports/cx_driver_analysis.md exactly.

Common column names are recognised (rating, review_score, stars; body,
comment, text; ...); pass others with --rating, --text, --title, --date,
--order and --email. The files hold customer emails, so cx_actions/ is
gitignored.

Pure standard library.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

# theme: (urgency, owner, keywords by language). Lower urgency is handled first;
# "praise" never routes a review. Portuguese lists are the ones of the Olist
# analysis (cx_driver_analysis.THEME_LEXICON).
THEMES: dict[str, tuple[int | None, str | None, dict[str, list[str]]]] = {
    "not_received": (1, "logistics + customer service", {
        "pt": ["nao recebi", "não recebi", "nao chegou", "não chegou", "faltou", "faltando"],
        "it": ["non ricevuto", "non ho ricevuto", "mai arrivato", "non è arrivato", "non e arrivato",
               "mancava", "mancante"],
        "en": ["not received", "never arrived", "never received", "didn't arrive", "missing item"],
    }),
    "product": (2, "product / quality", {
        "pt": ["produto", "qualidade", "defeit", "quebrad", "danific", "origin"],
        "it": ["rotto", "danneggiat", "difett", "qualità", "qualita", "non funziona", "originale"],
        "en": ["broken", "damaged", "defect", "quality", "doesn't work", "not working", "fake"],
    }),
    "delivery": (3, "logistics", {
        "pt": ["entrega", "prazo", "atras", "chegou", "demor", "antes do prazo", "rapid"],
        "it": ["consegna", "ritardo", "spedizione", "corriere", "tempi"],
        "en": ["delivery", "late", "delay", "shipping", "courier"],
    }),
    "service": (3, "customer service", {
        "pt": ["atendimento", "contato", "resposta", "suporte", "reembolso", "troca"],
        "it": ["assistenza", "risposta", "rimborso", "reso", "cambio", "servizio clienti"],
        "en": ["customer service", "support", "refund", "reply", "response", "exchange"],
    }),
    "praise": (None, None, {
        "pt": ["recomend", "satisfeit", "gostei", "otimo", "ótimo", "excelente"],
        "it": ["consiglio", "soddisfatt", "ottimo", "perfett", "bellissim"],
        "en": ["recommend", "satisfied", "great", "excellent", "love"],
    }),
}
OTHER = (4, "customer service")
COLUMNS = {  # role: names recognised without a flag, first match wins
    "rating": ("rating", "review_score", "stars", "score", "Review Stars"),
    "text": ("body", "comment", "review", "text", "content", "Review Content"),
    "title": ("title", "Review Title"),
    "date": ("review_date", "date", "created_at", "Review Created (UTC)"),
    "order": ("order_id", "order", "Reference Id"),
    "email": ("email", "reviewer_email"),
}
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _safe(text: str) -> str:
    return "'" + text if text.startswith(FORMULA_START) else text


def themes_of(text: str, lang: str) -> list[str]:
    low = text.lower()
    return [t for t, (_u, _o, words) in THEMES.items() if any(w in low for w in words[lang])]


def read_reviews(path: Path, chosen: dict[str, str | None]) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:  # -sig: Excel adds a BOM
        reader = csv.DictReader(fh)
        names = set(reader.fieldnames or ())
        col = {role: chosen.get(role) or next((c for c in COLUMNS[role] if c in names), None) for role in COLUMNS}
        for role in ("rating", "text"):
            if not col[role] or col[role] not in names:
                raise SystemExit(f"No {role} column found; pass its name with --{role}.")
        reviews = []
        for line, r in enumerate(reader, start=2):
            raw = (r.get(col["rating"]) or "").strip()
            if not raw:
                continue
            try:
                rating = float(raw.replace(",", "."))
            except ValueError:
                raise SystemExit(f"Line {line}: rating {raw!r} is not a number.") from None
            text = " ".join(filter(None, (r.get(col["title"]) if col["title"] else "", r.get(col["text"]) or "")))
            reviews.append({
                "rating": rating,
                "text": text.strip(),
                "date": (r.get(col["date"]) or "").strip() if col["date"] else "",
                "order_id": (r.get(col["order"]) or "").strip() if col["order"] else "",
                "email": (r.get(col["email"]) or "").strip().lower() if col["email"] else "",
            })
    return reviews


def theme_summary(reviews: list[dict], lang: str) -> list[dict]:
    """Mentions and average rating per theme, over the reviews that have text."""
    with_text = [r for r in reviews if r["text"]]
    out = []
    for t in THEMES:
        hit = [r["rating"] for r in with_text if t in themes_of(r["text"], lang)]
        if hit:
            out.append({"theme": t, "mentions": len(hit), "share": len(hit) / len(with_text),
                        "avg_rating": sum(hit) / len(hit)})
    return sorted(out, key=lambda s: -s["mentions"])


def triage(reviews: list[dict], lang: str, max_rating: float) -> list[dict]:
    rows = []
    for r in reviews:
        if r["rating"] > max_rating:
            continue
        problems = [t for t in themes_of(r["text"], lang) if THEMES[t][0] is not None]
        theme = min(problems, key=lambda t: THEMES[t][0]) if problems else "other"
        urgency, owner = THEMES[theme][:2] if problems else OTHER
        rows.append(dict(r, theme=theme, urgency=urgency, owner=owner))
    # most urgent theme, then lowest rating, then newest
    rows.sort(key=lambda r: r["date"], reverse=True)
    return sorted(rows, key=lambda r: (r["urgency"], r["rating"]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--reviews", type=Path, required=True)
    p.add_argument("--lang", choices=("it", "en", "pt"), default="it", help="language of the keyword lists")
    p.add_argument("--max-rating", type=float, default=2, help="triage reviews at or below this rating")
    p.add_argument("--out", type=Path, default=Path("cx_actions"))
    for role in COLUMNS:
        p.add_argument(f"--{role}", help=f"name of the {role} column, if not a common one")
    args = p.parse_args(argv)

    reviews = read_reviews(args.reviews, {role: getattr(args, role) for role in COLUMNS})
    if not reviews:
        print("No reviews with a rating in this file.")
        return 1
    queue = triage(reviews, args.lang, args.max_rating)
    summary = theme_summary(reviews, args.lang)

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "triage.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["urgency", "theme", "owner", "rating", "date", "order_id", "email", "excerpt"])
        for r in queue:
            excerpt = r["text"][:160] + ("..." if len(r["text"]) > 160 else "")
            w.writerow([r["urgency"], r["theme"], r["owner"], f"{r['rating']:g}", _safe(r["date"]),
                        _safe(r["order_id"]), _safe(r["email"]), _safe(excerpt)])
    with (args.out / "themes.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["theme", "mentions", "share_of_reviews_with_text", "avg_rating"])
        for s in summary:
            w.writerow([s["theme"], s["mentions"], f"{s['share']:.4f}", f"{s['avg_rating']:.2f}"])

    print(f"{len(reviews):,} reviews, {len(queue):,} at {args.max_rating:g} stars or fewer -> {args.out}/triage.csv")
    by_theme: dict[str, int] = {}
    for r in queue:
        by_theme[r["theme"]] = by_theme.get(r["theme"], 0) + 1
    for theme, n in sorted(by_theme.items(), key=lambda kv: (THEMES.get(kv[0], OTHER)[0] or 9, -kv[1])):
        print(f"  {theme:<13} {n:>5}  -> {THEMES[theme][1] if theme in THEMES else OTHER[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
