import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from pathlib import Path


def calculate_portfolio_daily_returns(
    data_dict: dict[str, pd.DataFrame], weights: dict[str, float]
) -> pd.Series:
    """Calculates the weighted daily returns of the portfolio."""
    logging.info(f"Calculating weighted daily returns for {len(weights)} assets...")
    returns_df = pd.DataFrame()
    for ticker, df in data_dict.items():
        if "Close" not in df.columns:
            logging.warning(f"Ticker '{ticker}' is missing 'Close' column. Skipping.")
            continue
        returns_df[ticker] = df["Close"].pct_change()

    returns_df = returns_df.dropna()
    logging.info(
        f"Aligned returns across assets. Computed {len(returns_df)} days of common returns."
    )

    portfolio_returns = pd.Series(0.0, index=returns_df.index)
    for ticker, weight in weights.items():
        if ticker in returns_df:
            logging.info(f"Applying weight {weight:.2f} to '{ticker}' returns.")
            portfolio_returns += returns_df[ticker] * weight

    return portfolio_returns


def calculate_portfolio_yield(
    data_dict: dict[str, pd.DataFrame], weights: dict[str, float]
) -> float:
    """Calculates the weighted annualized dividend yield of the portfolio."""
    logging.info("Calculating weighted annualized dividend yield...")
    total_yield = 0.0
    for ticker, weight in weights.items():
        df = data_dict.get(ticker)
        if df is not None and not df.empty and "Dividends" in df.columns:
            initial_price = df["Close"].iloc[0]
            total_dividends = df["Dividends"].sum()
            n_days = len(df)
            if initial_price > 0 and n_days > 0:
                asset_yield = (total_dividends / initial_price) * (252 / n_days)
                logging.info(
                    f"Asset '{ticker}': Total Dividends={total_dividends:.2f}, "
                    f"Annualized Yield={asset_yield:.2%}"
                )
                total_yield += asset_yield * weight
    logging.info(f"Total weighted portfolio yield: {total_yield:.2%}")
    return total_yield


def compute_metrics(returns: pd.Series, div_yield: float) -> dict[str, float]:
    """Computes annualized return and volatility from daily returns."""
    n_days = len(returns)
    if n_days == 0:
        logging.warning("No returns data available to compute metrics.")
        return {"Return": 0.0, "Volatility": 0.0, "Yield": div_yield}

    cumulative_return = (1 + returns).prod()
    annualized_return = (cumulative_return ** (252 / n_days)) - 1
    annualized_volatility = returns.std() * np.sqrt(252)

    logging.info(
        f"Computed Metrics: Ann. Return={annualized_return:.2%}, "
        f"Ann. Volatility={annualized_volatility:.2%}, Ann. Yield={div_yield:.2%}"
    )

    return {"Return": annualized_return, "Volatility": annualized_volatility, "Yield": div_yield}


def calculate_correlation(s1: pd.Series, s2: pd.Series) -> float:
    """Calculates the correlation between two series of returns."""
    if s1.empty or s2.empty:
        logging.warning("One or both series are empty. Correlation cannot be calculated.")
        return 0.0
    correlation = s1.corr(s2)
    logging.info(f"Calculated Correlation: {correlation:.4f}")
    return float(correlation)


def generate_csv_report(
    idx_name: str, benchmark: str, results_by_period: dict[str, dict[str, Any]], outdir: Path
) -> None:
    """
    Generates a consolidated CSV report with a Metric-Pivot structure.
    Rows: Metric_Asset
    Columns: Periods
    """
    rows = []

    metrics = ["Return", "Volatility", "Yield"]

    for metric in metrics:
        idx_row = {"Metric": f"{metric} ({idx_name})"}
        bm_row = {"Metric": f"{metric} ({benchmark})"}
        diff_row = {"Metric": f"{metric} (Difference)"}

        for period, res in results_by_period.items():
            idx_val = res["portfolio"].get(metric, 0.0)
            bm_val = res["benchmark"].get(metric, 0.0)
            diff_val = idx_val - bm_val

            # Formatting as percentages
            idx_row[period] = f"{idx_val:.2%}"
            bm_row[period] = f"{bm_val:.2%}"
            diff_row[period] = f"{diff_val:.2%}"

        rows.extend([idx_row, bm_row, diff_row])

    # Add Correlation row
    corr_row = {"Metric": f"Correlation ({idx_name} vs {benchmark})"}
    for period, res in results_by_period.items():
        corr_val = res.get("correlation", 0.0)
        corr_row[period] = f"{corr_val:.4f}"
    rows.append(corr_row)

    df_report = pd.DataFrame(rows)
    csv_path = outdir / f"{idx_name}_summary.csv"
    df_report.to_csv(csv_path, index=False)
    logging.info(f"Saved statistics report to {csv_path}")
