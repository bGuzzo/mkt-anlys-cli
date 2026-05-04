# Market Analysis CLI
---
> **✨ Vibe coded with Gemini-CLI, yet extensively tested ✨**
---
![Market Analysis CLI Cover](pics/sp20_eq_weight_3y.png)
---

A simple and lightweight Python CLI tool to perform **market analysis** and **evaluate stock portfolio strategies** against historical data. 
It allows you to define a **personal financial index** for your portfolio and evaluate its performance using historical data. 
The tool leverages data from `yfinance` to produce clear performance charts and comprehensive statistics.

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
The CLI tool accepts five arguments:
1. `weights`: A JSON dictionary that maps a `yfinance` ticker to a weight (0 to 1). Example: `--weights '{"AAPL": 0.4, "MSFT": 0.4, "AMZN": 0.2}'`.
2. `benchmark`: A `yfinance` ticker used as a reference in plots and statistics. Example: `--benchmark '^GSPC'` (S&P 500).
3. `outdir`: The target directory to store the output artifacts (charts and CSV statistics). Example: `--outdir "./index_output"`.
4. `period`: The timeframe(s) for which you want to evaluate your strategy. Example: `--period '6mo, 1y, 3y, 5y'`. Supported periods: `3mo, 6mo, 1y, 2y, 5y, 10y`.
5. `idx_name`: The name of your custom index (should not contain spaces). Example: `--idx_name 'my_index'`.

## Performance & Caching
- **Local Cache:** Raw market data is cached in `./yfinance_cache/` using the Parquet format to avoid redundant network requests.
- **Efficient Processing:** Uses `pandas` and `pyarrow` for internal data handling to ensure speed and type safety.

## Outputs & Interpretation
The tool generates a comparative set of artifacts in the specified `--outdir`.

### 1. Cumulative Performance Charts (PNG)
- **What it shows:** The "Growth of a Dollar." It tracks how a $1 investment at the start of the `period` would have evolved over time.
- **Interpretation:** 
    - If your portfolio's line is above the benchmark line, your strategy **outperformed** the market during that specific timeframe.
    - **Volatility Visualization:** Sharp peaks and valleys indicate higher risk/volatility, while smoother lines suggest more stable assets.
- **Details:** High-resolution (300 DPI) charts with daily granularity ensure an accurate representation of trends.

### 2. Consolidated Statistics Summary (CSV)
The summary file `{idx_name}_summary.csv` uses a **Metric-Pivot** structure for easy side-by-side comparison across all requested periods.

| Metric | Description |
| :--- | :--- |
| **Return** | The **Compound Annual Growth Rate (CAGR)**. It represents the geometric mean return that would provide the same total return as the actual variable returns, assuming annual compounding. |
| **Volatility** | The **Annualized Standard Deviation** of daily returns. This is the primary measure of market risk; higher values indicate larger price swings. |
| **Yield** | The **Annualized Dividend Yield**. It is calculated by summing all dividends received during the period relative to the starting price and then annualizing the result. |
| **Difference** | The "Alpha" or "Spread," calculated as `Portfolio Metric - Benchmark Metric`. A positive Return Difference indicates that your portfolio outperformed the market. |

### Interpretation Example
If the CSV shows:
- `Return (Difference)` for 5y: `+2.97%`
- `Volatility (Difference)` for 5y: `+7.54%`

This indicates that your portfolio earned **2.97% more per year** than the benchmark over 5 years, but it was **significantly riskier** (7.54% more volatile) to achieve those returns.

