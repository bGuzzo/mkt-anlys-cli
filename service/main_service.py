import logging
from pathlib import Path
from typing import List
import pandas as pd

from service.yfinance_service import align_and_combine_data
from service.reporting_service import (
    calculate_portfolio_daily_returns,
    calculate_portfolio_yield,
    compute_metrics,
    calculate_correlation,
    generate_csv_report
)
from service.plotting_service import plot_performance

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
            
            # 2. Portfolio Calculations
            portfolio_returns = calculate_portfolio_daily_returns(data_dict, weights)
            portfolio_div_yield = calculate_portfolio_yield(data_dict, weights)
            portfolio_metrics = compute_metrics(portfolio_returns, portfolio_div_yield)
            
            # 3. Benchmark Calculations
            benchmark_data = {benchmark: data_dict[benchmark]}
            benchmark_weights = {benchmark: 1.0}
            benchmark_returns = calculate_portfolio_daily_returns(benchmark_data, benchmark_weights)
            benchmark_div_yield = calculate_portfolio_yield(benchmark_data, benchmark_weights)
            benchmark_metrics = compute_metrics(benchmark_returns, benchmark_div_yield)
            
            # Align dates for plotting (intersection of indexes)
            common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
            port_ret_aligned = portfolio_returns.loc[common_idx]
            bench_ret_aligned = benchmark_returns.loc[common_idx]
            
            # 4. Plot Performance
            plot_performance(
                idx_name=idx_name,
                benchmark=benchmark,
                period=period,
                portfolio_returns=port_ret_aligned,
                benchmark_returns=bench_ret_aligned,
                outdir=outdir
            )
            
            # 5. Calculate Correlation
            correlation = calculate_correlation(port_ret_aligned, bench_ret_aligned)
            
            # Store metrics for report
            results_by_period[period] = {
                'portfolio': portfolio_metrics,
                'benchmark': benchmark_metrics,
                'correlation': correlation
            }
            
        except Exception as e:
            logging.error(f"Error processing period '{period}': {e}")
            
    # 6. Generate Final Report
    if results_by_period:
        generate_csv_report(
            idx_name=idx_name,
            benchmark=benchmark,
            results_by_period=results_by_period,
            outdir=outdir
        )
    else:
        logging.error("No data processed for any period. Report generation skipped.")
