# Market Analysis CLI
---
> **✨ Vibe coded with Gemini-CLI, yet extensively tested ✨**
---
![Market Analysis CLI Cover](pics/sp20_eq_weight_3y.png)
---

A simple and lightweight Python CLI tool to perform **market analysis** and **evaluate your stock portfolio strategy** against historical data. 
It allows you to define your **personal financial index** (for your portfolio?) and evaluate your strategy using historical data. 
It uses data from yfinance and produces simple charts and statistics.

## Installation
Requires [uv](https://github.com/astral-sh/uv):
```bash
uv sync
```

## Usage
```bash
uv run mkt-anlys-cli.py \
  --weights '{"AAPL": 0.4, "MSFT": 0.4, "AMZN": 0.2}' \
  --benchmark '^GSPC' \
  --outdir "./results" \
  --period "1y, 5y" \
  --idx_name "my_portfolio"
```

## Inputs
The CLI tool takes 5 arguments:
1. `weights`: A dict which maps a ticker (yfinance) to a weight (0 to 1). Example: `--weights '{"AAPL": 0.4, "MSFT": 0.4, "AMZN": 0.2}'`.
2. `benchmark`: A ticker (yfinance) used as reference in the plots and statistics. Example: `--benchmark '^GSPC'` (S&P500).
3. `outdir`: The target directory to store the output computations (charts + CSV stats). Example: `--outdir "./index_output"`.
4. `period`: The timeframe for which you want to evaluate your strategy. Example: `--period '6mo, 1y, 3y, 5y'`. Supported: `3mo, 6mo, 1y, 2y, 5y, 10y`
5. `idx_name`: The name of your index (should not contain spaces). Example: `--idx_name 'my_index'`.

## Performance & Caching
- **Local Cache:** Raw market data is cached in `./yfinance_cache/` using Parquet to avoid redundant network requests.
- **Fast Processing:** Uses Parquet for all internal data handling to ensure speed and type safety.

## Outputs & Interpretation
The tool generates a comparative set of artifacts in the `--outdir` directory.

### 1. Cumulative Performance Charts (PNG)
- **What it shows:** The "Growth of a Dollar". It tracks how a $1 investment at the start of the `period` would have evolved.
- **Interpretation:** 
    - If your portfolio line is above the benchmark line, your strategy **outperformed** the market for that specific timeframe.
    - **Volatility Visualization:** Sharp peaks and valleys indicate higher risk/volatility. Smoother lines suggest more stable assets.
- **Details:** High-resolution (300 DPI) with daily granularity to ensure accurate trend representation.

### 2. Consolidated Statistics Summary (CSV)
The summary file `{idx_name}_summary.csv` uses a **Metric-Pivot** structure for easy side-by-side comparison across all requested periods.

| Metric | Description |
| :--- | :--- |
| **Return** | The **Compound Annual Growth Rate (CAGR)**. It represents the geometric mean return that provides the same total return as the actual variable returns over the period, assuming annual compounding. |
| **Volatility** | **Annualized Standard Deviation** of daily returns. This is the primary measure of market risk. Higher values indicate higher price swings. |
| **Yield** | The **Annualized Dividend Yield**. Calculated by summing all dividends received during the period relative to the starting price, then annualized based on the number of days in the period. |
| **Difference** | The "Alpha" or "Spread". Calculated as `Portfolio Metric - Benchmark Metric`. A positive Return Difference means you beat the market. |

### Interpretation Example
If the CSV shows:
- `Return (Difference)` for 5y: `+2.97%`
- `Volatility (Difference)` for 5y: `+7.54%`

This means your portfolio earned **2.97% more per year** than the benchmark over 5 years, but it was **significantly riskier** (7.54% more volatile) to achieve those returns.

