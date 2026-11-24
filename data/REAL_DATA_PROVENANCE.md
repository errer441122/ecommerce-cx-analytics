# Real Data Provenance

Two public datasets: Olist (reviews, used by the analysis in `reports/`) and UCI Online Retail II
(wholesale lines, used by the credit-note check).

# 1. Olist reviews

## Source

- **Dataset:** Olist Brazilian E-Commerce Public Dataset
- **Origin:** Kaggle — `olistbr/brazilian-ecommerce`
- **License:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0
  International (**CC BY-NC-SA 4.0**). This portfolio is **non-commercial**;
  the dataset is attributed and not redistributed beyond the prepared,
  transformed extract used for analysis.
- **Source archive SHA256:** `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`
- **Status:** REAL public e-commerce data (Brazil, 2016-2018). Not simulated.
- **Currency:** Brazilian Real (BRL), reported as such (not EUR).

## Cleaning rules

1. Keep reviews whose order status is `delivered` with valid purchase and
   customer-delivery dates (so delivery metrics are well defined).
2. One row per `review_id`.
3. Order-level price and freight summed across order items; product
   category from the order's first item, English-translated.
4. NPS band is a **disclosed proxy** from the 1-5 review score
   (5 = promoter, 4 = passive, ≤ 3 = detractor) — Olist has no 0-10
   likelihood-to-recommend question.

## Prepared sample

- `data/olist_reviews.csv` — 95,639 reviews, 27 states,
  74 product categories, satisfied rate 79.0%.
- `data/olist_review_comments.csv` — 38,813 Portuguese review
  comments (review_id keyed).
- Raw review rows scanned: 99,224.

SHA256 of the committed files (LF line endings):

- olist_reviews.csv: `73820831e61abebd856426840c8a9c76ac8ee73447fb7fd03f79628a7c29c3d0`
- olist_review_comments.csv: `9d989eec99758bb6501c38b0bebcfb4e8f3390f36fccbd42b9fd3f46aa7c671d`

Re-running `python src/prepare_real_data.py` reproduces both files
byte-for-byte from the SHA256-pinned source.

## Note

This CX lab is now **fully real** — there is no synthetic data. The only
disclosed approximation is the NPS *band* proxy above (a relabelling of the
real review score, not invented data).

# 2. Wholesale lines

- **Dataset:** Online Retail II, UCI Machine Learning Repository (ID 502). Chen, D. (2019),
  https://doi.org/10.24432/C5CG6D
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
- **What it is:** invoices and cancellations of a UK gift company, December 2009 to December 2011.
  The dataset page says that many of its customers are wholesalers.
- **Source archive SHA256:** `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`

Cleaning rules (`src/prepare_wholesale.py`):

1. Keep lines with a customer, a five-digit product code and a positive price. Postage, fees,
   manual lines and samples are left out.
2. Invoices whose number starts with C are cancellations and keep their negative quantity.
3. The two yearly sheets overlap on 1-9 December 2010: each invoice is read once.
4. The description of an item is written once, on its first line, to keep the files small.

A cancellation dated after the purchase is read as goods sent back. That reading is mine: the
dataset does not say why an invoice was cancelled.

SHA256 of the committed files:

- wholesale_lines.csv.gz: `76432ff006ed9977aa7cbab3e201e6e787ca28888a77ca8f2ae451fa57cb8421` (805,828 lines)
- wholesale_demo.csv.gz: `65abe97126aae408025458b17df5ce6df6e37421fa434f198c93e398f0f49042` (166,581 lines, the 150 days to 27 October 2010)
