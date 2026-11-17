# E-commerce CX Analytics: what makes customers unhappy?

A practice project on a public dataset. The question is one a Customer
Experience team asks every month: **why do some customers leave a bad review,
and where should we act first?**

The data is about 95,000 real customer reviews from Olist, a Brazilian online
marketplace (2016 to 2018), joined with the delivery details of each order. It
is not client work.

## Use it on your own store

The analysis below found that late delivery is the main reason for a bad
review. Two tools turn that into a daily routine on a store's own exports:

| Tool | Command | What you get |
| --- | --- | --- |
| Late orders | `python src/late_orders.py --shipments shipments.csv` | `late_open.csv`: orders past the promised date and not delivered yet, longest wait first, to contact before the customer complains and to import into Klaviyo (`delivery_issue=open`) so promotions skip them. `late_delivered.csv`: orders that arrived late this week, for a follow-up. The late rate by carrier, to spot the one that is failing |
| Review triage | `python src/review_triage.py --reviews reviews.csv --lang it` | `triage.csv`: 1-2 star reviews, most urgent first (not received, then product problems, then delivery and service), each with the team it goes to. `themes.csv`: how often each theme comes up and its average rating |

The shipments file comes from the shipping platform or the carrier and needs
an order number, the promised delivery date and the delivery date (empty while
in transit); dates can be `YYYY-MM-DD` or `DD/MM/YYYY`. The reviews file can be
any export with a rating and the text. Column names differ by platform, so
both tools take them as flags (`--promised`, `--delivered`, `--rating`,
`--text`, ...). The themes are a keyword list in Italian, English and
Portuguese that the team can read and extend, not a language model: every tag
can be checked by reading the review.

**How I know it is right:** on the 38,814 real Olist comments the triage
reproduces the theme counts and average ratings of the analysis below exactly.
On those reviews it puts 9,191 at 1-2 stars in the queue, and 2,080 of them
say the order never arrived. The late-orders tool is tested on a handwritten
file ([`data/shipments_example.csv`](data/shipments_example.csv)), because the
public dataset does not include orders still in transit.

Nothing leaves the machine. The output folder `cx_actions/` is gitignored
because the lists hold customer emails.

## What the data says

- **79% of customers are satisfied** (4 or 5 stars out of 5).
- **Late delivery is the main problem.** When the order arrives on time, 83% of
  customers are satisfied. When it arrives after the promised date, only 27%
  are. Late orders are just 6.7% of the total, but they account for 23% of all
  unsatisfied reviews.
- **Speed helps too.** Orders delivered within 7 days: 86% satisfied. Orders
  that take 15 days or more: 65%.
- **Some regions are much worse than others.** In the state of Maranhão 17% of
  orders arrive late and satisfaction drops to 70%. Rio de Janeiro matters most
  in volume: 12,000 reviews, 12% late, 73.5% satisfied.
- **The worst reviews are about orders that never arrived or arrived
  incomplete.** Comments on this topic have an average score of 1.6 out of 5.

Reports: [satisfaction brief](reports/customer_satisfaction_brief.md) ·
[full analysis](reports/cx_driver_analysis.md).

## The metrics I used

| Metric | In plain words |
| --- | --- |
| **Satisfaction rate (CSAT)** | Share of reviews with 4 or 5 stars |
| **Late-delivery rate** | Share of orders delivered after the date promised at checkout |
| **Delivery time** | Days between the purchase and the delivery |
| **Promoters and detractors** | An NPS-style score built from the stars: 5 = promoter, 4 = neutral, 3 or less = detractor. Olist has no real NPS question, so this is an approximation |
| **Review topics** | Reviews grouped by keyword: delivery, product quality, not received, customer service |

Each metric is split by state and by product category, so the team can see
where the problem is concentrated.

The full analysis also contains some more advanced statistical checks that the
AI assistant added to confirm the numbers above. They are not the point of the
project: the comparisons in this README are the ones I use to explain it.

## Real-World Business Application (Next Steps)

What a CX or CRM team could do with these findings. These are recommendations:
the dataset shows what happened, it does not prove what caused it, and nothing
here has been tested.

1. **Fix the promise before the product.** Customers are judging the delivery
   date they were promised. In the regions with the most late orders, showing a
   more realistic delivery date at checkout is cheaper than making the
   logistics faster, and it attacks the same problem.
2. **Write to the customer before they write the review.** A late order is
   known before the customer complains. An automatic email or SMS when the
   order passes its promised date ("we are sorry, here is the new date") costs
   very little and reaches the customer at the moment the bad review is formed.
3. **Ask for reviews at the right time.** Send the review request after the
   delivery is confirmed, not a fixed number of days after the purchase.
4. **Give "order not received" its own fast lane in customer service.** It is
   a small group with the lowest scores, so a quick refund or reshipment there
   protects the rating more than any other single action.
5. **Report late-delivery rate next to satisfaction.** Looking at the two
   numbers together, region by region, shows whether a drop in reviews
   is a product problem or a delivery problem.

## What is in here

| Path | What it does |
| --- | --- |
| `reports/` | The satisfaction brief and the full analysis |
| `data/` | The prepared review data and where it comes from |
| `src/` | The Python scripts that prepare the data, build the reports and run the two tools |
| `notebooks/` | A second calculation of the main numbers, to catch mistakes |
| `tests/` | Automatic checks that run on every change |

## Run it

The prepared data is already in the repository, so no download is needed:

```bash
python src/validate_cx_data.py
python src/build_cx_summary.py
python src/cx_driver_analysis.py
python -m unittest discover -s tests
```

## Data and limits

Olist Brazilian E-Commerce dataset (Kaggle, CC BY-NC-SA 4.0), used for a
non-commercial portfolio. Source and cleaning rules are in
[`data/REAL_DATA_PROVENANCE.md`](data/REAL_DATA_PROVENANCE.md).

- This is a public dataset that many people practise on.
- It covers one Brazilian marketplace between 2016 and 2018. The numbers do
  not transfer to other shops.
- Only delivered orders with a review are included.

## How I built this

I am a Digital Marketing student, not a developer. I built this with AI coding
assistants: they wrote most of the code. My part was choosing the business
question and the data, deciding which metrics to compare, checking the results
against the source data and deciding what to report.
