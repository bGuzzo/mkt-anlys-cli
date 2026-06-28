import logging
from typing import Any

import numpy as np
import pandas as pd

from service.yfinance_service import (
    get_historical_exchange_rates,
    get_market_data,
    get_ticker_info,
)


def fetch_and_normalize_asset(ticker: str, period: str) -> pd.DataFrame:
    """
    Fetches historical daily data for a ticker and normalizes it to EUR.
    """
    logging.info(f"Fetching data for '{ticker}' for period '{period}'...")
    df = get_market_data(ticker, period)
    if df.empty:
        logging.warning(f"No data returned for '{ticker}' ({period}).")
        return pd.DataFrame()

    info = get_ticker_info(ticker)
    currency = info.get("currency", "USD")

    if currency == "EUR":
        logging.info(f"Ticker '{ticker}' is already in EUR. No normalization needed.")
        return df

    logging.info(f"Normalizing '{ticker}' from {currency} to EUR...")
    rates = get_historical_exchange_rates(currency, "EUR", period)

    if rates.empty:
        logging.warning(f"Could not fetch exchange rates for {currency}/EUR. Using raw data.")
        return df

    # Align rates with the ticker data index using ffill/bfill to handle different calendars
    rates_aligned = rates.reindex(df.index, method="ffill").ffill().bfill()

    df_norm = df.copy()
    df_norm["Close"] = df["Close"] * rates_aligned
    if "Dividends" in df.columns:
        df_norm["Dividends"] = df["Dividends"] * rates_aligned

    logging.info(f"Successfully normalized '{ticker}' to EUR.")
    return df_norm


def calculate_annualized_return(returns: pd.Series) -> float:
    """
    Calculates the annualized expected return from daily returns.
    """
    n_days = len(returns)
    if n_days == 0:
        logging.warning("Empty series passed. Annualized return is 0.0.")
        return 0.0
    cumulative_return = (1 + returns).prod()
    if pd.isna(cumulative_return) or cumulative_return <= 0:
        return 0.0
    return float((cumulative_return ** (252 / n_days)) - 1)


def calculate_tangency_portfolio_returns(
    normalized_data: dict[str, pd.DataFrame], weights: dict[str, float]
) -> pd.Series:
    """
    Computes daily returns for constituents and reconstructs the daily returns
    of the tangency portfolio using weights.
    """
    logging.info("Reconstructing tangency portfolio daily returns from weights...")
    returns_df = pd.DataFrame()
    for ticker, df in normalized_data.items():
        if ticker not in weights:
            continue
        if "Close" not in df.columns:
            logging.warning(f"Ticker '{ticker}' is missing 'Close' column. Skipping.")
            continue
        returns_df[ticker] = df["Close"].pct_change()

    returns_df = returns_df.dropna()

    if returns_df.empty:
        logging.warning("No overlapping returns data for portfolio constituents.")
        return pd.Series(dtype=float)

    portfolio_returns = pd.Series(0.0, index=returns_df.index)
    for ticker, weight in weights.items():
        if ticker in returns_df:
            portfolio_returns += returns_df[ticker] * weight

    return portfolio_returns


def calculate_beta(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Calculates the beta of asset returns relative to benchmark returns.
    """
    if asset_returns.empty or benchmark_returns.empty:
        return 0.0
    common_idx = asset_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < 2:
        return 0.0
    r_a = asset_returns.loc[common_idx]
    r_m = benchmark_returns.loc[common_idx]

    covariance = r_a.cov(r_m)
    variance = r_m.var()
    if pd.isna(variance) or variance == 0:
        return 0.0
    return float(covariance / variance)


def calculate_betas(
    normalized_data: dict[str, pd.DataFrame],
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    weights: dict[str, float],
) -> dict[str, float]:
    """
    Calculates betas for the portfolio and individual assets relative to benchmark.
    Returns a dictionary of betas: {"portfolio": beta_p, "Asset1": beta_1, ...}
    """
    betas = {}

    # Portfolio Beta
    betas["portfolio"] = calculate_beta(portfolio_returns, benchmark_returns)

    # Asset Betas
    for ticker, df in normalized_data.items():
        if ticker not in weights:
            continue
        if "Close" not in df.columns:
            continue
        asset_returns = df["Close"].pct_change().dropna()
        betas[ticker] = calculate_beta(asset_returns, benchmark_returns)

    return betas


def calculate_alpha(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
    beta: float,
    rf_rate: float,
) -> float:
    """
    Calculates the annualized alpha of asset returns relative to benchmark returns.
    """
    if asset_returns.empty or benchmark_returns.empty:
        return 0.0
    common_idx = asset_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) == 0:
        return 0.0
    r_a = asset_returns.loc[common_idx]
    r_m = benchmark_returns.loc[common_idx]

    ann_asset_return = calculate_annualized_return(r_a)
    ann_benchmark_return = calculate_annualized_return(r_m)

    alpha = ann_asset_return - (rf_rate + beta * (ann_benchmark_return - rf_rate))
    return float(alpha)


def calculate_alphas(
    normalized_data: dict[str, pd.DataFrame],
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    betas: dict[str, float],
    weights: dict[str, float],
    rf_rate: float,
) -> dict[str, float]:
    """
    Calculates annualized alphas for the portfolio and individual assets relative to benchmark.
    Returns a dictionary of alphas: {"portfolio": alpha_p, "Asset1": alpha_1, ...}
    """
    alphas = {}

    # Portfolio Alpha
    portfolio_beta = betas.get("portfolio", 0.0)
    alphas["portfolio"] = calculate_alpha(
        portfolio_returns, benchmark_returns, portfolio_beta, rf_rate
    )

    # Asset Alphas
    for ticker, df in normalized_data.items():
        if ticker not in weights:
            continue
        if "Close" not in df.columns:
            continue
        asset_returns = df["Close"].pct_change().dropna()
        asset_beta = betas.get(ticker, 0.0)
        alphas[ticker] = calculate_alpha(
            asset_returns, benchmark_returns, asset_beta, rf_rate
        )

    return alphas


def analyze_capm(
    normalized_data: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    weights: dict[str, float],
    rf_rate: float,
) -> dict[str, Any]:
    """
    Performs full CAPM analysis for the portfolio and individual assets relative to the benchmark.
    """
    if benchmark_df.empty:
        logging.error("Benchmark dataframe is empty.")
        return {}

    benchmark_returns = benchmark_df["Close"].pct_change().dropna()
    portfolio_returns = calculate_tangency_portfolio_returns(normalized_data, weights)

    if portfolio_returns.empty or benchmark_returns.empty:
        logging.error("Could not construct daily returns for portfolio or benchmark.")
        return {}

    betas = calculate_betas(normalized_data, portfolio_returns, benchmark_returns, weights)
    alphas = calculate_alphas(
        normalized_data,
        portfolio_returns,
        benchmark_returns,
        betas,
        weights,
        rf_rate,
    )

    ann_benchmark_ret = calculate_annualized_return(benchmark_returns)
    ann_portfolio_ret = calculate_annualized_return(portfolio_returns)

    return {
        "benchmark_expected_return": ann_benchmark_ret,
        "portfolio_expected_return": ann_portfolio_ret,
        "betas": betas,
        "alphas": alphas,
        "rf_rate": rf_rate,
    }


def compute_capm_stats(
    prices_df: pd.DataFrame,
    benchmark_series: pd.Series,
    rf_annual: float,
    weights_dict: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Computes CAPM statistics for individual assets and optionally a weighted portfolio.
    All return inputs are daily close price series.
    """
    logging.info("Computing CAPM statistics...")

    # Align assets and benchmark
    common_idx = prices_df.index.intersection(benchmark_series.index)
    prices_df = prices_df.loc[common_idx]
    bench_prices = benchmark_series.loc[common_idx]

    # Calculate daily returns
    assets_returns = prices_df.pct_change().dropna()
    bench_returns = bench_prices.pct_change().dropna()

    # Align again after pct_change
    common_returns_idx = assets_returns.index.intersection(bench_returns.index)
    assets_returns = assets_returns.loc[common_returns_idx]
    bench_returns = bench_returns.loc[common_returns_idx]

    n_days = len(bench_returns)
    if n_days == 0:
        raise ValueError("No historical returns available after alignment.")

    # Calculate benchmark stats
    bench_cum = (1 + bench_returns).prod()
    bench_ann_return = float((bench_cum ** (252 / n_days)) - 1)
    bench_ann_vol = float(bench_returns.std() * np.sqrt(252))

    rf_daily = rf_annual / 252.0

    # Compute individual asset stats
    assets_stats = {}
    bench_var = float(bench_returns.var())

    for ticker in assets_returns.columns:
        asset_ret_series = assets_returns[ticker]
        asset_cum = (1 + asset_ret_series).prod()
        asset_ann_return = float((asset_cum ** (252 / n_days)) - 1)
        asset_ann_vol = float(asset_ret_series.std() * np.sqrt(252))

        # Linear regression of excess returns
        cov_yx = float(np.cov(asset_ret_series - rf_daily, bench_returns - rf_daily)[0, 1])
        beta = cov_yx / bench_var if bench_var > 0 else 1.0

        mean_asset_excess = float((asset_ret_series - rf_daily).mean())
        mean_bench_excess = float((bench_returns - rf_daily).mean())
        alpha_daily = mean_asset_excess - beta * mean_bench_excess
        alpha_annual = float(alpha_daily * 252.0)

        assets_stats[ticker] = {
            "expected_return": asset_ann_return,
            "volatility": asset_ann_vol,
            "beta": beta,
            "alpha": alpha_annual,
        }

    results: dict[str, Any] = {
        "benchmark": {
            "expected_return": bench_ann_return,
            "volatility": bench_ann_vol,
        },
        "assets": assets_stats,
    }

    # Compute portfolio stats if weights provided
    if weights_dict is not None:
        port_returns = pd.Series(0.0, index=assets_returns.index)
        for ticker, weight in weights_dict.items():
            if ticker in assets_returns.columns:
                port_returns += assets_returns[ticker] * weight

        port_cum = (1 + port_returns).prod()
        port_ann_return = float((port_cum ** (252 / n_days)) - 1)
        port_ann_vol = float(port_returns.std() * np.sqrt(252))

        cov_port_bench = float(np.cov(port_returns - rf_daily, bench_returns - rf_daily)[0, 1])
        port_beta = cov_port_bench / bench_var if bench_var > 0 else 1.0

        mean_port_excess = float((port_returns - rf_daily).mean())
        port_alpha_daily = mean_port_excess - port_beta * mean_bench_excess
        port_alpha_annual = float(port_alpha_daily * 252.0)

        results["portfolio"] = {
            "expected_return": port_ann_return,
            "volatility": port_ann_vol,
            "beta": port_beta,
            "alpha": port_alpha_annual,
        }

    return results
