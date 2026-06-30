import logging
from typing import TYPE_CHECKING

from service.plotting_service import plot_performance
from service.reporting_service import (
    calculate_correlation,
    calculate_portfolio_daily_returns,
    calculate_portfolio_yield,
    compute_metrics,
    generate_csv_report,
)
from service.yfinance_service import (
    align_and_combine_data,
    get_historical_exchange_rates,
    get_ticker_info,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def normalize_data_to_eur(
    data_dict: dict[str, pd.DataFrame], period: str
) -> dict[str, pd.DataFrame]:
    """
    Normalizes all price and dividend data in the data_dict to EUR.
    """
    normalized_dict = {}
    for ticker, df in data_dict.items():
        if df.empty:
            normalized_dict[ticker] = df
            continue

        info = get_ticker_info(ticker)
        currency = info.get("currency", "USD")

        if currency == "EUR":
            logging.info(f"Ticker '{ticker}' is already in EUR. No normalization needed.")
            normalized_dict[ticker] = df
            continue

        logging.info(f"Normalizing '{ticker}' from {currency} to EUR for period '{period}'...")
        rates = get_historical_exchange_rates(currency, "EUR", period)

        if rates.empty:
            logging.warning(
                f"Could not fetch exchange rates for {currency}/EUR. Using raw data for '{ticker}'."
            )
            normalized_dict[ticker] = df
            continue

        # Align rates with the ticker data index
        # We use reindex with ffill to handle different trading calendars
        rates_aligned = rates.reindex(df.index, method="ffill")

        # If still some NaNs at the beginning, use the first valid rate
        rates_aligned = rates_aligned.ffill().bfill()

        df_norm = df.copy()
        df_norm["Close"] = df["Close"] * rates_aligned
        if "Dividends" in df.columns:
            df_norm["Dividends"] = df["Dividends"] * rates_aligned

        normalized_dict[ticker] = df_norm
        logging.info(f"Successfully normalized '{ticker}' to EUR.")

    return normalized_dict


def normalize_data_to_usd(
    data_dict: dict[str, pd.DataFrame], period: str
) -> dict[str, pd.DataFrame]:
    """
    Normalizes all price and dividend data in the data_dict to USD.
    """
    normalized_dict = {}
    for ticker, df in data_dict.items():
        if df.empty:
            normalized_dict[ticker] = df
            continue

        info = get_ticker_info(ticker)
        currency = info.get("currency", "USD")

        if currency == "USD":
            logging.info(f"Ticker '{ticker}' is already in USD. No normalization needed.")
            normalized_dict[ticker] = df
            continue

        logging.info(f"Normalizing '{ticker}' from {currency} to USD for period '{period}'...")
        rates = get_historical_exchange_rates(currency, "USD", period)

        if rates.empty:
            logging.warning(
                f"Could not fetch exchange rates for {currency}/USD. Using raw data for '{ticker}'."
            )
            normalized_dict[ticker] = df
            continue

        # Align rates with the ticker data index
        # We use reindex with ffill to handle different trading calendars
        rates_aligned = rates.reindex(df.index, method="ffill")

        # If still some NaNs at the beginning, use the first valid rate
        rates_aligned = rates_aligned.ffill().bfill()

        df_norm = df.copy()
        df_norm["Close"] = df["Close"] * rates_aligned
        if "Dividends" in df.columns:
            df_norm["Dividends"] = df["Dividends"] * rates_aligned

        normalized_dict[ticker] = df_norm
        logging.info(f"Successfully normalized '{ticker}' to USD.")

    return normalized_dict



def run_analysis(
    weights: dict[str, float], benchmark: str, outdir: Path, periods: list[str], idx_name: str
) -> None:
    """
    Main orchestration function for the market analysis CLI.
    """
    tickers_to_fetch = [*list(weights.keys()), benchmark]
    results_by_period = {}

    for period in periods:
        logging.info(f"--- Processing Period: {period} ---")
        try:
            # 1. Fetch Data
            data_dict = align_and_combine_data(tickers_to_fetch, period)

            # 2. Normalize Data to EUR
            normalized_data = normalize_data_to_eur(data_dict, period)

            # 3. Portfolio Calculations
            portfolio_returns = calculate_portfolio_daily_returns(normalized_data, weights)
            portfolio_div_yield = calculate_portfolio_yield(normalized_data, weights)
            portfolio_metrics = compute_metrics(portfolio_returns, portfolio_div_yield)

            # 4. Benchmark Calculations
            benchmark_data = {benchmark: normalized_data[benchmark]}
            benchmark_weights = {benchmark: 1.0}
            benchmark_returns = calculate_portfolio_daily_returns(benchmark_data, benchmark_weights)
            benchmark_div_yield = calculate_portfolio_yield(benchmark_data, benchmark_weights)
            benchmark_metrics = compute_metrics(benchmark_returns, benchmark_div_yield)

            # Align dates for plotting (intersection of indexes)
            common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
            port_ret_aligned = portfolio_returns.loc[common_idx]
            bench_ret_aligned = benchmark_returns.loc[common_idx]

            # 5. Plot Performance
            plot_performance(
                idx_name=idx_name,
                benchmark=benchmark,
                period=period,
                portfolio_returns=port_ret_aligned,
                benchmark_returns=bench_ret_aligned,
                outdir=outdir,
            )

            # 5b. Generate and Plot Efficient Frontier
            try:
                import pandas as pd

                from service.bl_optimization_service import (
                    calculate_historical_statistics,
                    compute_black_litterman_posterior,
                    compute_efficient_frontier_analytical,
                )
                from service.plotting_service import plot_efficient_frontier

                # Extract daily returns for all assets in the portfolio
                returns_df = pd.DataFrame()
                for ticker in weights.keys():
                    if ticker in normalized_data and "Close" in normalized_data[ticker].columns:
                        returns_df[ticker] = normalized_data[ticker]["Close"].pct_change()
                returns_df = returns_df.dropna()

                if not returns_df.empty:
                    ann_returns, ann_cov = calculate_historical_statistics(returns_df)
                    mkt_weights = pd.Series(weights)

                    # Compute BL posterior (no custom views, defaults to implied returns)
                    mu_bl, sigma_bl = compute_black_litterman_posterior(
                        ann_returns=ann_returns,
                        ann_cov=ann_cov,
                        mkt_weights=mkt_weights,
                        risk_aversion=3.0,
                        tau=0.05,
                    )

                    # Compute analytical unconstrained frontier
                    frontier_vols, frontier_returns, _, tangency_vol, tangency_return = (
                        compute_efficient_frontier_analytical(
                            mu=mu_bl,
                            cov=sigma_bl,
                            rf_rate=0.02,
                        )
                    )

                    # Plot the efficient frontier
                    plot_efficient_frontier(
                        idx_name=idx_name,
                        period=period,
                        mu=mu_bl,
                        cov=sigma_bl,
                        frontier_vols=frontier_vols,
                        frontier_returns=frontier_returns,
                        tangency_vol=tangency_vol,
                        tangency_return=tangency_return,
                        rf_rate=0.02,
                        outdir=outdir,
                    )
                else:
                    logging.warning("Cannot plot efficient frontier: returns dataframe is empty.")
            except Exception as ef_err:
                logging.error(
                    f"Failed to generate efficient frontier plot: {ef_err}",
                    exc_info=True,
                )

            # 6. Calculate Correlation
            correlation = calculate_correlation(port_ret_aligned, bench_ret_aligned)

            # Store metrics for report
            results_by_period[period] = {
                "portfolio": portfolio_metrics,
                "benchmark": benchmark_metrics,
                "correlation": correlation,
            }

        except Exception as e:
            logging.error(f"Error processing period '{period}': {e}", exc_info=True)

    # 7. Generate Final Report
    if results_by_period:
        generate_csv_report(
            idx_name=idx_name,
            benchmark=benchmark,
            results_by_period=results_by_period,
            outdir=outdir,
        )
    else:
        logging.error("No data processed for any period. Report generation skipped.")
