import logging
from pathlib import Path
from typing import List
import pandas as pd

from service.yfinance_service import (
    align_and_combine_data, 
    get_ticker_info, 
    get_historical_exchange_rates
)
from service.reporting_service import (
    calculate_portfolio_daily_returns,
    calculate_portfolio_yield,
    compute_metrics,
    calculate_correlation,
    generate_csv_report
)
from service.plotting_service import plot_performance

def normalize_data_to_eur(data_dict: dict[str, pd.DataFrame], period: str) -> dict[str, pd.DataFrame]:
    """
    Normalizes all price and dividend data in the data_dict to EUR.
    """
    normalized_dict = {}
    for ticker, df in data_dict.items():
        if df.empty:
            normalized_dict[ticker] = df
            continue
            
        info = get_ticker_info(ticker)
        currency = info.get('currency', 'USD')
        
        if currency == 'EUR':
            logging.info(f"Ticker '{ticker}' is already in EUR. No normalization needed.")
            normalized_dict[ticker] = df
            continue
            
        logging.info(f"Normalizing '{ticker}' from {currency} to EUR for period '{period}'...")
        rates = get_historical_exchange_rates(currency, 'EUR', period)
        
        if rates.empty:
            logging.warning(f"Could not fetch exchange rates for {currency}/EUR. Using raw data for '{ticker}'.")
            normalized_dict[ticker] = df
            continue
            
        # Align rates with the ticker data index
        # We use reindex with ffill to handle different trading calendars
        rates_aligned = rates.reindex(df.index, method='ffill')
        
        # If still some NaNs at the beginning, use the first valid rate
        rates_aligned = rates_aligned.ffill().bfill()
        
        df_norm = df.copy()
        df_norm['Close'] = df['Close'] * rates_aligned
        if 'Dividends' in df.columns:
            df_norm['Dividends'] = df['Dividends'] * rates_aligned
            
        normalized_dict[ticker] = df_norm
        logging.info(f"Successfully normalized '{ticker}' to EUR.")
        
    return normalized_dict

def run_analysis(
    weights: dict[str, float], 
    benchmark: str, 
    outdir: Path, 
    periods: List[str], 
    idx_name: str
):
    """
    Main orchestration function for the market analysis CLI.
    """
    tickers_to_fetch = list(weights.keys()) + [benchmark]
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
                outdir=outdir
            )
            
            # 6. Calculate Correlation
            correlation = calculate_correlation(port_ret_aligned, bench_ret_aligned)
            
            # Store metrics for report
            results_by_period[period] = {
                'portfolio': portfolio_metrics,
                'benchmark': benchmark_metrics,
                'correlation': correlation
            }
            
        except Exception as e:
            logging.error(f"Error processing period '{period}': {e}", exc_info=True)
            
    # 7. Generate Final Report
    if results_by_period:
        generate_csv_report(
            idx_name=idx_name,
            benchmark=benchmark,
            results_by_period=results_by_period,
            outdir=outdir
        )
    else:
        logging.error("No data processed for any period. Report generation skipped.")
