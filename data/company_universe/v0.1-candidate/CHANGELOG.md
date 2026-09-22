# Company Universe v0.1-candidate

## Purpose

Create a small, reviewable observation universe before scaling company research. This is a research queue, not a portfolio or an index replica.

## Selection

- 50 S&P 500 companies;
- 10 research themes with 5 companies per theme;
- 25 companies in five technology-core themes;
- five additional themes provide payment, industrial, healthcare, consumer, and energy comparisons;
- Nasdaq-100 membership is stored as a point-in-time label;
- no holding status is inferred: every company starts as `unknown`.

## Product behavior

- search by company, ticker, sector, theme, or topic tag;
- filter by S&P 500 / Nasdaq-100;
- filter by research attention;
- filter by holding state;
- filter by research theme;
- render companies as one flat list without grouped sections;
- paginate filtered results with 10, 20, or 50 rows per page;
- Alphabet links to the existing reviewed business map; other companies remain `not started`.

## Known limitations

- The list and attention labels remain candidate decisions until user review.
- Index membership changes over time and must produce a new snapshot version.
- Holdings require explicit user input or a separately authorized portfolio integration.
