# Market Analysis CLI
---
> **✨ Vibe coded with Gemini-CLI, yet extensively tested ✨**
---
![Market Analysis CLI Cover](pics/sp20_eq_weight_3y.png)
---

A suite of lightweight Python CLI tools to perform **market analysis**, **evaluate stock portfolio strategies**, and **construct market-cap weighted portfolios**.

The project consists of two main tools:
1. **Performance Evaluator (`mkt-anlys-cli.py`)**: Define a personal financial index and evaluate its historical performance against benchmarks.
2. **Portfolio Constructor (`portfolio-cli.py`)**: Generate a market-cap weighted allocation (S&P 500 style) for a list of tickers.

### Unified EUR Perspective
Both tools normalize ALL financial data to **EUR**. This means if you have a portfolio with Apple (USD), Samsung (KRW), and Toyota (JPY), the tools will automatically:
- Fetch historical exchange rates for every day in the analysis period.
- Convert all prices, dividends, and market caps to Euros.
- Provide a consistent view of returns and allocations from an Euro-based investor's perspective.

## Installation
Requires [uv](https://github.com/astral-sh/uv):
```bash
uv sync
```

---

## 1. Performance Evaluator (`mkt-anlys-cli.py`)
Evaluate your stock portfolio strategy against historical data.

### Usage
```bash
uv run mkt-anlys-cli.py \
  --weights '{"AAPL": 0.4, "005930.KS": 0.4, "SAP.DE": 0.2}' \
  --benchmark '^GSPC' \
  --outdir "./results" \
  --period "1y, 5y" \
  --idx_name "global_portfolio"
```

### Inputs
- `weights`: JSON dictionary mapping ticker to weight (0 to 1). Supports global tickers (e.g., `005930.KS` for Samsung).
- `benchmark`: Reference ticker (e.g., `^GSPC`).
- `outdir`: Target directory for charts and stats.
- `period`: Timeframe(s) (e.g., `1y, 5y`). Supported: `3mo, 6mo, 1y, 2y, 5y, 10y`.
- `idx_name`: Name for your index (no spaces).

---

## 2. Portfolio Constructor (`portfolio-cli.py`)
Compute market-cap weighted allocations for a list of stocks to determine how much to invest in each.

### Usage
```bash
uv run portfolio-cli.py \
  --input tickers.json \
  --amount 10000 \
  --outfile allocation.csv
```

### Inputs
- `input`: Path to a JSON file containing a list of global yfinance tickers.
- `amount`: Total amount in **Euros** you are willing to invest.
- `outfile`: Path to the generated CSV allocation report.

---

## Performance & Caching
- **Local Cache:** Raw market data and ticker metadata are cached in `./yfinance_cache/` using Parquet and JSON formats to avoid redundant network requests.
- **Exchange Rate Caching:** Currency conversion rates are fetched once per day and cached locally.

## Outputs & Interpretation

### Performance Analysis (mkt-anlys-cli.py)
Generates high-resolution PNG charts and a `{idx_name}_summary.csv` file. All metrics (Return, Volatility, Yield) are calculated **after currency conversion to EUR**.

### Portfolio Allocation (portfolio-cli.py)
Generates a CSV with the following columns:
- **Ticker**: The stock symbol.
- **Euros to Allocate**: How much to spend in EUR.
- **Dollars to Allocate**: Equivalent value in USD.
- **Percentage**: The stock's weight in the total portfolio (calculated based on EUR-normalized market caps).

---

## Logging & Troubleshooting
The tools utilize verbose, high-signal logging to help you track data fetching, currency normalization, cache hits/misses, and calculation steps.
Example: `2026-05-10 07:30:31.858 INFO [main_service.py:35] normalize_data_to_eur: Normalizing 'AAPL' from USD to EUR...`
