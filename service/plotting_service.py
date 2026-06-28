from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def plot_performance(
    idx_name: str,
    benchmark: str,
    period: str,
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    outdir: Path,
) -> None:
    """
    Generates a comparative performance chart and saves it as a PNG.
    """
    logging.info(
        f"Generating performance chart for '{idx_name}' vs '{benchmark}' for period '{period}'..."
    )
    if portfolio_returns.empty or benchmark_returns.empty:
        logging.warning(f"Aborting plot for period {period}: missing return data.")
        return

    portfolio_cum = (1 + portfolio_returns).cumprod()
    benchmark_cum = (1 + benchmark_returns).cumprod()
    p_end = portfolio_cum.iloc[-1]
    b_end = benchmark_cum.iloc[-1]
    logging.info(
        f"Cumulative returns calculated. Portfolio end value: {p_end:.2f}, "
        f"Benchmark end value: {b_end:.2f}"
    )

    plt.figure(figsize=(10, 6), dpi=300)
    plt.plot(portfolio_cum.index, portfolio_cum, label=idx_name, linewidth=2)
    plt.plot(benchmark_cum.index, benchmark_cum, label=benchmark, linewidth=2, linestyle="--")

    plt.title(
        f"Cumulative Performance: {idx_name} vs {benchmark} ({period})",
        fontsize=14,
        fontweight="bold",
    )
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Cumulative Return (Base 1.0)", fontsize=12)
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(loc="best", fontsize=11)
    plt.gcf().autofmt_xdate()

    out_path = outdir / f"{idx_name}_{period}.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    logging.info(f"Successfully saved high-resolution chart to: {out_path}")


def plot_efficient_frontier(
    idx_name: str,
    period: str,
    mu: pd.Series,
    cov: pd.DataFrame,
    frontier_vols: np.ndarray,
    frontier_returns: np.ndarray,
    tangency_vol: float,
    tangency_return: float,
    rf_rate: float,
    outdir: Path,
) -> None:
    """
    Generates an Efficient Frontier comparison plot showing:
    - The Minimum-Variance Frontier hyperbola
    - The Capital Allocation Line (CAL) from risk-free rate through the Tangency portfolio
    - Individual asset risk-return dots
    - Clear highlights and labels for the Tangency portfolio
    """
    logging.info(f"Generating Efficient Frontier plot for '{idx_name}' for period '{period}'...")

    # Set premium dark-theme inspired palette or extremely clean modern style
    plt.figure(figsize=(11, 7), dpi=300)

    # 1. Plot the Efficient Frontier hyperbola
    # We plot the upper half as a solid line and lower half as a dotted line
    # Find the global minimum variance portfolio index/point
    min_vol_idx = np.argmin(frontier_vols)

    plt.plot(
        frontier_vols[min_vol_idx:],
        frontier_returns[min_vol_idx:],
        color="#7C4DFF",  # Modern purple
        linewidth=3,
        label="Efficient Frontier (Upper)",
    )
    plt.plot(
        frontier_vols[: min_vol_idx + 1],
        frontier_returns[: min_vol_idx + 1],
        color="#7C4DFF",
        linewidth=1.5,
        linestyle=":",
        alpha=0.6,
        label="Minimum Variance Frontier (Lower)",
    )

    # 2. Plot Capital Allocation Line (CAL)
    # The line starts at (0, rf) and goes through (tangency_vol, tangency_return)
    # Let's extend it to 1.5 times the tangency volatility
    max_cal_vol = float(max(tangency_vol * 1.5, float(frontier_vols.max())))
    cal_vols = np.linspace(0.0, max_cal_vol, 100)
    cal_returns = rf_rate + ((tangency_return - rf_rate) / tangency_vol) * cal_vols

    plt.plot(
        cal_vols,
        cal_returns,
        color="#FF9100",  # Energetic amber/gold
        linewidth=2,
        linestyle="--",
        label=(
            f"Capital Allocation Line (CAL, SR={((tangency_return - rf_rate) / tangency_vol):.2f})"
        ),
    )

    # 3. Plot individual asset risk-return dots
    assets = list(mu.index)
    asset_vols = []
    asset_returns = []

    for asset in assets:
        vol = np.sqrt(cov.loc[asset, asset])
        ret = mu.loc[asset]
        asset_vols.append(vol)
        asset_returns.append(ret)

        # Draw dot
        plt.scatter(
            vol,
            ret,
            color="#00E5FF",  # Vibrant cyan
            edgecolor="#006064",
            s=80,
            zorder=5,
        )
        # Label asset with offset
        plt.annotate(
            asset,
            (vol, ret),
            textcoords="offset points",
            xytext=(10, -5),
            ha="left",
            fontsize=9,
            fontweight="bold",
            color="#37474F",
        )

    # 4. Plot and highlight the Tangency portfolio point
    plt.scatter(
        tangency_vol,
        tangency_return,
        color="#FF1744",  # High-contrast hot pink/red
        edgecolor="#880E4F",
        marker="*",
        s=300,
        zorder=10,
        label=f"Tangency Portfolio (Max SR, Vol={tangency_vol:.2%}, Ret={tangency_return:.2%})",
    )

    # Plot risk-free rate on Y-axis
    plt.scatter(
        0,
        rf_rate,
        color="#2979FF",  # Bright blue
        marker="o",
        s=100,
        zorder=6,
        label=f"Risk-free Rate (r_f = {rf_rate:.1%})",
    )

    # Styling and formatting
    plt.title(
        f"Black-Litterman Efficient Frontier: {idx_name} ({period})",
        fontsize=15,
        fontweight="bold",
        pad=15,
    )
    plt.xlabel("Annualized Volatility (Risk)", fontsize=12, labelpad=10)
    plt.ylabel("Annualized Expected Return", fontsize=12, labelpad=10)

    # Display percentages on axes
    plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0%}"))

    plt.xlim(0, max_cal_vol * 1.1)
    y_min = min(rf_rate - 0.02, min(asset_returns) - 0.05)
    y_max = max(frontier_returns.max() * 1.1, max(asset_returns) * 1.1)
    plt.ylim(y_min, y_max)

    plt.grid(True, linestyle=":", alpha=0.5, color="#B0BEC5")
    plt.legend(
        loc="upper left",
        fontsize=10,
        frameon=True,
        facecolor="#ECEFF1",
        edgecolor="#CFD8DC",
    )

    # Add prominent text box for the Sharpe Ratio (CAL slope)
    sharpe_ratio = (tangency_return - rf_rate) / tangency_vol
    stats_text = (
        f"Tangency Portfolio Metrics:\n"
        f"  Expected Return: {tangency_return:.2%}\n"
        f"  Volatility (Risk): {tangency_vol:.2%}\n"
        f"  Sharpe Ratio: {sharpe_ratio:.3f}"
    )
    plt.gca().text(
        0.95,
        0.05,
        stats_text,
        transform=plt.gca().transAxes,
        fontsize=10,
        fontweight="bold",
        verticalalignment="bottom",
        horizontalalignment="right",
        bbox={
            "boxstyle": "round,pad=0.6",
            "facecolor": "#FFF9C4",  # premium bright soft yellow
            "edgecolor": "#FBC02D",  # gold amber border
            "alpha": 0.95,
            "linewidth": 1.5,
        },
    )

    out_path = outdir / f"{idx_name}_efficient_frontier_{period}.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    logging.info(f"Successfully saved Efficient Frontier chart to: {out_path}")


def plot_security_market_line(
    idx_name: str,
    benchmark: str,
    period: str,
    rf_rate: float,
    expected_benchmark_return: float,
    tangency_beta: float,
    tangency_return: float,
    tangency_alpha: float,
    outdir: Path,
) -> None:
    """
    Plots the Security Market Line (SML) from Beta=0 (starting at Rf) to Beta=2.0.
    Highlights the benchmark at Beta=1.0 and the Tangency Portfolio.
    """
    logging.info(f"Generating Security Market Line (SML) plot for '{idx_name}'...")

    plt.figure(figsize=(11, 7), dpi=300)

    # SML line goes from Beta=0 to Beta=2.0
    betas = np.linspace(0.0, 2.0, 100)
    sml_returns = rf_rate + betas * (expected_benchmark_return - rf_rate)

    # Plot SML Line
    plt.plot(
        betas,
        sml_returns,
        color="#7C4DFF",  # Modern purple
        linewidth=3,
        label="Security Market Line (SML)",
    )

    # Highlight Benchmark at (1.0, expected_benchmark_return)
    plt.scatter(
        1.0,
        expected_benchmark_return,
        color="#00E5FF",  # Vibrant cyan
        edgecolor="#006064",
        marker="o",
        s=150,
        zorder=5,
        label=f"Benchmark ({benchmark}) [Beta=1.0]",
    )
    plt.annotate(
        f"{benchmark}\n(Beta=1.00, Ret={expected_benchmark_return:.2%})",
        (1.0, expected_benchmark_return),
        textcoords="offset points",
        xytext=(-15, 15),
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#37474F",
    )

    # Highlight Tangency Portfolio at (tangency_beta, tangency_return)
    plt.scatter(
        tangency_beta,
        tangency_return,
        color="#FF1744",  # High-contrast hot pink/red
        edgecolor="#880E4F",
        marker="*",
        s=300,
        zorder=10,
        label=f"Tangency Portfolio ({idx_name})",
    )
    plt.annotate(
        f"{idx_name}\n(Beta={tangency_beta:.2f}, Ret={tangency_return:.2%})",
        (tangency_beta, tangency_return),
        textcoords="offset points",
        xytext=(15, -15),
        ha="left",
        fontsize=9,
        fontweight="bold",
        color="#37474F",
    )

    # Highlight Risk-free Rate at (0, rf_rate)
    plt.scatter(
        0,
        rf_rate,
        color="#2979FF",  # Bright blue
        marker="o",
        s=100,
        zorder=6,
        label=f"Risk-free Rate (R_f = {rf_rate:.2%})",
    )
    plt.annotate(
        f"Risk-free Rate ({rf_rate:.2%})",
        (0, rf_rate),
        textcoords="offset points",
        xytext=(10, -5),
        ha="left",
        fontsize=9,
        fontweight="bold",
        color="#37474F",
    )

    infobox_text = (
        f"Performance & CAPM Metrics:\n"
        f"  • Risk-Free Rate (Rf): {rf_rate:.2%}\n"
        f"  • Benchmark E(Rm): {expected_benchmark_return:.2%}\n"
        f"  • Portfolio E(Rp): {tangency_return:.2%}\n"
        f"  • Portfolio Beta (β): {tangency_beta:.3f}\n"
        f"  • Portfolio Alpha (α): {tangency_alpha:.2%}"  # noqa: RUF001
    )
    plt.gca().text(
        0.05,
        0.80,
        infobox_text,
        transform=plt.gca().transAxes,
        fontsize=10,
        fontweight="bold",
        verticalalignment="top",
        bbox={
            "boxstyle": "round,pad=0.6",
            "facecolor": "#ECEFF1",
            "edgecolor": "#CFD8DC",
            "alpha": 0.95,
            "linewidth": 1.5,
        },
    )

    # Styling and formatting
    plt.title(
        f"Security Market Line (SML): {idx_name} vs {benchmark} ({period})",
        fontsize=15,
        fontweight="bold",
        pad=15,
    )
    plt.xlabel("Beta (Systematic Risk)", fontsize=12, labelpad=10)
    plt.ylabel("Annualized Expected Return", fontsize=12, labelpad=10)

    # Format y-axis as percentage
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.1%}"))

    plt.xlim(-0.1, 2.1)
    y_min = min(rf_rate - 0.02, expected_benchmark_return - 0.05, tangency_return - 0.05)
    y_max = max(expected_benchmark_return * 1.3, tangency_return * 1.3, rf_rate + 0.05)
    plt.ylim(y_min, y_max)

    plt.grid(True, linestyle=":", alpha=0.5, color="#B0BEC5")
    plt.legend(
        loc="upper left",
        fontsize=10,
        frameon=True,
        facecolor="#ECEFF1",
        edgecolor="#CFD8DC",
    )

    out_path = outdir / f"{idx_name}_sml_{period}.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    logging.info(f"Successfully saved SML plot to: {out_path}")
