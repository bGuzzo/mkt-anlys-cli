import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
import logging

def plot_performance(
    idx_name: str, 
    benchmark: str, 
    period: str, 
    portfolio_returns: pd.Series, 
    benchmark_returns: pd.Series, 
    outdir: Path
):
    """
    Generates a comparative performance chart and saves it as a PNG.
    """
    logging.info(f"Generating performance chart for '{idx_name}' vs '{benchmark}' for period '{period}'...")
    if portfolio_returns.empty or benchmark_returns.empty:
        logging.warning(f"Aborting plot for period {period}: missing return data.")
        return
        
    portfolio_cum = (1 + portfolio_returns).cumprod()
    benchmark_cum = (1 + benchmark_returns).cumprod()
    logging.info(f"Cumulative returns calculated. Portfolio end value: {portfolio_cum.iloc[-1]:.2f}, Benchmark end value: {benchmark_cum.iloc[-1]:.2f}")
    
    plt.figure(figsize=(10, 6), dpi=300)
    plt.plot(portfolio_cum.index, portfolio_cum, label=idx_name, linewidth=2)
    plt.plot(benchmark_cum.index, benchmark_cum, label=benchmark, linewidth=2, linestyle='--')
    
    plt.title(f"Cumulative Performance: {idx_name} vs {benchmark} ({period})", fontsize=14, fontweight='bold')
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Cumulative Return (Base 1.0)", fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.legend(loc="best", fontsize=11)
    plt.gcf().autofmt_xdate()
    
    out_path = outdir / f"{idx_name}_{period}.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    logging.info(f"Successfully saved high-resolution chart to: {out_path}")
