"""Perché una nota di credito da sola non ferma un cliente.

Due anni di righe vere di un grossista (UCI Online Retail II, CC BY 4.0). A dodici date si confrontano
clienti simili, per numero di ordini fatti e giorni dall'ultimo: chi ha appena reso merce riordina
meno degli altri nei 90 giorni dopo?

    python prove/nota_di_credito.py      riscrive prove/nota-di-credito.md
"""

import csv
import gzip
import io
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

QUI = Path(__file__).parent
giorno = date.fromisoformat
comprato, ordini, resi = defaultdict(list), defaultdict(set), defaultdict(set)
righe = [(r["customer_id"], giorno(r["date"]), r["item"], int(r["quantity"]))
         for r in csv.DictReader(io.StringIO(gzip.decompress((QUI / "wholesale_lines.csv.gz").read_bytes()).decode()))]
for cliente, quando, articolo, pezzi in righe:
    if pezzi > 0:
        comprato[cliente, articolo].append((quando, pezzi))
        ordini[cliente].add(quando)
for cliente, quando, articolo, pezzi in righe:
    if pezzi < 0:  # merce resa: lo stesso cliente l'aveva comprata in un giorno precedente
        prima = [g for g, p in comprato[cliente, articolo] if g <= quando and p >= -pezzi]
        if prima and max(prima) < quando:
            resi[cliente].add(quando)

gruppi = defaultdict(lambda: [0, 0, 0, 0])
for oggi in (date(2010, 9, 1) + timedelta(30 * i) for i in range(12)):
    for cliente, giorni in ordini.items():
        fatti = [g for g in giorni if g <= oggi]
        if len(fatti) < 3 or (oggi - max(fatti)).days >= 60:
            continue
        riordina = any(oggi < g <= oggi + timedelta(90) for g in giorni)
        g = gruppi[min(len(fatti), 12) // 3, (oggi - max(fatti)).days // 20]
        lato = 0 if any(oggi - timedelta(30) < r <= oggi for r in resi[cliente]) else 2
        g[lato] += 1
        g[lato + 1] += riordina

usati = {k: g for k, g in sorted(gruppi.items()) if g[0] >= 20 and g[2] >= 20}
casi = sum(g[0] for g in usati.values())
con, senza = sum(g[1] for g in usati.values()) / casi, sum(g[0] * g[3] / g[2] for g in usati.values()) / casi
uguali = sum(round(g[1] / g[0], 2) >= round(g[3] / g[2], 2) for g in usati.values())
num = lambda x: f"{x:,}".replace(",", ".")  # noqa: E731
nomi = {1: "3-5", 2: "6-8", 3: "9-11", 4: "12 o più"}
testo = [
    "# Una nota di credito da sola non ferma un cliente", "",
    f"{num(len(righe))} righe vere di vendita e di annullamento, {num(len(ordini))} clienti di un grossista inglese, dicembre 2009 - dicembre 2011.", "",
    f"**{num(casi)} casi di clienti che avevano appena reso merce: il {con:.0%} ha riordinato entro 90 giorni. Tra i clienti simili che non avevano reso nulla, il {senza:.0%}.** "
    f"In {uguali} gruppi su {len(usati)} chi ha reso ha riordinato almeno quanto gli altri.", "",
    "| Ordini già fatti | Giorni dall'ultimo | Ha reso merce: riordina | Clienti simili: riordina |", "| --- | --- | ---: | ---: |",
]
testo += [f"| {nomi[o]} | {d * 20}-{d * 20 + 19} | {g[1] / g[0]:.0%} ({g[0]} casi) | {g[3] / g[2]:.0%} ({g[2]} casi) |" for (o, d), g in usati.items()]
testo += ["", "Limiti: un annullamento datato dopo l'acquisto è letto come merce resa, ma i dati non dicono il motivo. È un confronto tra clienti simili, non un esperimento.",
          "Fonte: Chen, D. (2019), *Online Retail II*, UCI Machine Learning Repository, CC BY 4.0.", ""]
(QUI / "nota-di-credito.md").write_text("\n".join(testo), encoding="utf-8", newline="\n")
print("\n".join(testo))
