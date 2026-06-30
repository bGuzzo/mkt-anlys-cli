import datetime
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import typer

from service.bl_optim_service import (
    get_risk_free_rate,
    parse_horizon,
    run_black_litterman_optimization,
)
from service.main_service import normalize_data_to_usd
from service.plotting_service import plot_efficient_frontier
from service.yfinance_service import align_and_combine_data

# Setup refined logging format (no tabulation/heavy padding)
LOG_FORMAT = (
    "%(asctime)s.%(msecs)03d %(levelname)s [%(filename)s:%(lineno)d] %(funcName)s: %(message)s"
)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = typer.Typer(help="Black-Litterman Portfolio Optimization & Efficient Frontier CLI.")


def validate_tickers_file(tickers_file: Path) -> list[str]:
    """Validates and parses the tickers file."""
    if not tickers_file.exists():
        raise typer.BadParameter(f"Tickers file '{tickers_file}' does not exist.")
    try:
        with open(tickers_file) as f:
            tickers = json.load(f)
    except json.JSONDecodeError as err:
        raise typer.BadParameter(f"Tickers file '{tickers_file}' must be a valid JSON.") from err

    if not isinstance(tickers, list):
        raise typer.BadParameter("Tickers file must contain a JSON list of tickers.")

    for ticker in tickers:
        if not isinstance(ticker, str):
            raise typer.BadParameter(f"Ticker '{ticker}' must be a string.")

    return tickers


@app.command()
def main(
    tickers_file: Path = typer.Option(
        ..., "--tickers", help="Path to a JSON file containing a list of yfinance tickers."
    ),
    horizon: str = typer.Option(
        "2mo", "--horizon", help="Investment horizon (e.g. '2mo' -> 42 days, '40' -> 40 days)."
    ),
    risk_free: str = typer.Option(
        "0.04",
        "--risk-free",
        help="Risk-free asset (ticker like '^IRX', '^TNX', or numeric value like '0.035').",
    ),
    benchmark: str = typer.Option(
        "VT",
        "--benchmark",
        "--rm",
        help="Benchmark asset (ticker like 'VT' or '^GSPC').",
    ),
    period: str = typer.Option(
        "2y",
        "--period",
        help="Historical data period to estimate covariance (e.g., '1y', '2y', '5y').",
    ),
    outdir: Path = typer.Option(
        None,
        "--outdir",
        help="Target directory for output. Defaults to results/bl-ef-<timestamp>.",
    ),
    usd_buy: float = typer.Option(
        None,
        "--usd-buy",
        help=(
            "Amount of money in US Dollars (USD) to invest and allocate "
            "across optimized tangency portfolio constituents."
        ),
    ),
) -> None:
    """
    Perform Black-Litterman portfolio optimization & compute the efficient frontier.
    All metrics and valuations are normalized to US Dollars (USD).
    """

    logging.info("Starting Black-Litterman & Efficient Frontier Optimization Pipeline")

    # 1. Parse and validate tickers
    try:
        tickers = validate_tickers_file(tickers_file)
    except Exception as e:
        logging.error(f"Tickers file validation failed: {e}")
        raise typer.Exit(code=1) from e

    # 2. Parse investment horizon
    try:
        horizon_days = parse_horizon(horizon)
        logging.info(f"Parsed investment horizon: '{horizon}' -> {horizon_days} trading days")
    except Exception as e:
        logging.error(f"Horizon parsing failed: {e}")
        raise typer.Exit(code=1) from e

    # 3. Get risk-free rate
    try:
        rf_annual = get_risk_free_rate(risk_free)
        logging.info(f"Retrieved annualized risk-free rate: {rf_annual:.6%}")
    except Exception as e:
        logging.error(f"Risk-free rate retrieval failed: {e}")
        raise typer.Exit(code=1) from e

    # 4. Resolve output directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if outdir is None:
        base_dir = Path(__file__).resolve().parent
        resolved_outdir = base_dir / "results" / f"bl-ef-{timestamp}"
    else:
        resolved_outdir = outdir

    logging.info(f"Output directory resolved to: {resolved_outdir}")

    # 5. Fetch and normalize historical close prices to USD
    try:
        logging.info(f"Fetching daily historical data for period: '{period}'")
        tickers_to_fetch = list(dict.fromkeys([*tickers, benchmark]))
        data_dict = align_and_combine_data(tickers_to_fetch, period)
        normalized_data = normalize_data_to_usd(data_dict, period)

        # Build daily close prices DataFrame
        prices_df = pd.DataFrame()
        for ticker in tickers:
            if ticker in normalized_data and not normalized_data[ticker].empty:
                prices_df[ticker] = normalized_data[ticker]["Close"]

        prices_df = prices_df.dropna()
        if prices_df.empty:
            raise ValueError("Aligned daily adjusted close prices DataFrame is empty.")

        if benchmark in normalized_data and not normalized_data[benchmark].empty:
            benchmark_series = normalized_data[benchmark]["Close"]
        else:
            raise ValueError(f"Benchmark ticker '{benchmark}' data is missing or empty.")

        # Align assets and benchmark indices
        common_idx = prices_df.index.intersection(benchmark_series.index)
        prices_df = prices_df.loc[common_idx]
        benchmark_series = benchmark_series.loc[common_idx]

        logging.info(
            "Successfully collected daily historical close prices for "
            f"{len(tickers)} assets and benchmark '{benchmark}'."
        )
    except Exception as e:
        logging.error(f"Data fetching or normalization failed: {e}")
        raise typer.Exit(code=1) from e

    # 6. Run Optimization math with dynamic Lambda and Tau parameters
    try:
        # Calculate dynamic risk aversion coefficient (Lambda) based on benchmark and risk-free rate
        benchmark_returns = benchmark_series.pct_change().dropna()
        from service.capm_service import calculate_annualized_return
        ann_benchmark_ret = calculate_annualized_return(benchmark_returns)
        # Annualized variance = daily variance * 252
        ann_benchmark_var = float(benchmark_returns.var() * 252.0)

        if ann_benchmark_var > 0:
            # Prevent negative or extremely close-to-zero lambda values
            lambda_dynamic = float(max(0.1, (ann_benchmark_ret - rf_annual) / ann_benchmark_var))
        else:
            lambda_dynamic = 3.0

        # Calculate dynamic Tau as 1 / T (number of historical daily observations)
        tau_dynamic = float(1.0 / len(prices_df) if not prices_df.empty else (1.0 / 30.0))

        logging.info(
            f"Calculated dynamic BL parameters: Lambda (Risk Aversion) = {lambda_dynamic:.4f} "
            f"derived from benchmark '{benchmark}' and Rf={rf_annual:.2%}; "
            f"Tau (Prior uncertainty scale) = {tau_dynamic:.6f} "
            f"derived from T={len(prices_df)} daily observations."
        )

        results = run_black_litterman_optimization(
            tickers=tickers,
            prices_df=prices_df,
            horizon_days=horizon_days,
            rf_annual=rf_annual,
            lambda_coeff=lambda_dynamic,
            tau=tau_dynamic,
        )
    except Exception as e:
        logging.error(f"Optimization computations failed: {e}")
        raise typer.Exit(code=1) from e

    # 6b. Run CAPM calculations
    try:
        from service.capm_service import compute_capm_stats

        tangency_weights = results["tangency_portfolio"]["weights"]
        capm_results = compute_capm_stats(
            prices_df=prices_df,
            benchmark_series=benchmark_series,
            rf_annual=rf_annual,
            weights_dict=tangency_weights,
        )
    except Exception as e:
        logging.error(f"CAPM computations failed: {e}")
        raise typer.Exit(code=1) from e

    # 7. Add CLI config and save JSON output
    results["config"] = {
        "tickers_file": str(tickers_file),
        "horizon_input": horizon,
        "horizon_days": horizon_days,
        "risk_free_input": risk_free,
        "risk_free_rate_annual": rf_annual,
        "benchmark": benchmark,
        "period": period,
        "timestamp": timestamp,
    }

    # Ensure output directory exists
    resolved_outdir.mkdir(parents=True, exist_ok=True)
    outfile = resolved_outdir / "bl_optimization_results.json"

    # 8. Reconstruct variables and plot the Efficient Frontier hyperbola (Annualized Scale)
    try:
        horizon_days = results["horizon_days"]
        scaling_factor = 360.0 / horizon_days
        vol_scaling = np.sqrt(252.0 / horizon_days)

        # Scale expected returns and covariances to annualized terms for the plot
        mu_series = pd.Series(results["expected_total_returns"]) * scaling_factor
        cov_df = pd.DataFrame(results["posterior_covariance"]) * (252.0 / horizon_days)

        frontier_vols = np.array(
            [pt["volatility"] for pt in results["efficient_frontier"]]
        ) * vol_scaling
        frontier_returns = np.array(
            [pt["expected_return"] for pt in results["efficient_frontier"]]
        ) * scaling_factor

        tangency_vol = results["tangency_portfolio"]["volatility"] * vol_scaling
        tangency_return = results["tangency_portfolio"]["expected_return"] * scaling_factor

        plot_efficient_frontier(
            idx_name="Black-Litterman",
            period=period,
            mu=mu_series,
            cov=cov_df,
            frontier_vols=frontier_vols,
            frontier_returns=frontier_returns,
            tangency_vol=tangency_vol,
            tangency_return=tangency_return,
            rf_rate=results["rf_annual"],  # Use True Annualized Risk-free Rate (e.g. 3.75% or 4.0%)
            outdir=resolved_outdir,
        )
    except Exception as e:
        logging.error(f"Plotting Efficient Frontier failed: {e}")
        raise typer.Exit(code=1) from e

    # 8b. Plot the Security Market Line (SML)
    try:
        from service.plotting_service import plot_security_market_line

        plot_security_market_line(
            idx_name="Black-Litterman",
            benchmark=benchmark,
            period=period,
            rf_rate=rf_annual,
            expected_benchmark_return=capm_results["benchmark"]["expected_return"],
            tangency_beta=capm_results["portfolio"]["beta"],
            tangency_return=capm_results["portfolio"]["expected_return"],
            tangency_alpha=capm_results["portfolio"]["alpha"],
            outdir=resolved_outdir,
        )
    except Exception as e:
        logging.error(f"Plotting SML failed: {e}")
        raise typer.Exit(code=1) from e

    # 9. Dump the two separate JSON files
    try:
        tangency_only = {
            "weights": results["tangency_portfolio"]["weights"],
            "expected_return": results["tangency_portfolio"]["expected_return"],
            "volatility": results["tangency_portfolio"]["volatility"],
            "sharpe_ratio": results["tangency_portfolio"]["sharpe_ratio"],
            "beta": capm_results["portfolio"]["beta"],
            "alpha": capm_results["portfolio"]["alpha"],
        }

        if usd_buy is not None:
            from service.portfolio_service import calculate_portfolio_allocation_usd
            allocation_report = calculate_portfolio_allocation_usd(
                weights=results["tangency_portfolio"]["weights"],
                total_usd=usd_buy,
            )
            tangency_only["allocation"] = allocation_report
            results["tangency_portfolio"]["allocation"] = allocation_report

        with open(resolved_outdir / "tangency_portfolio_only.json", "w") as f:
            json.dump(tangency_only, f, indent=4)

        capm_alpha_beta = {
            "tangency_alpha": capm_results["portfolio"]["alpha"],
            "tangency_beta": capm_results["portfolio"]["beta"],
            "benchmark_return": capm_results["benchmark"]["expected_return"],
            "benchmark_volatility": capm_results["benchmark"]["volatility"],
            "individual_assets": {
                ticker: {
                    "alpha": stats["alpha"],
                    "beta": stats["beta"],
                }
                for ticker, stats in capm_results["assets"].items()
            },
        }
        with open(resolved_outdir / "capm_alpha_beta.json", "w") as f:
            json.dump(capm_alpha_beta, f, indent=4)

        logging.info("Successfully dumped separate JSON reports.")
    except Exception as e:
        logging.error(f"Failed to write detailed JSON reports: {e}")
        raise typer.Exit(code=1) from e

    try:
        with open(outfile, "w") as f:
            json.dump(results, f, indent=4)
        logging.info(f"Successfully saved JSON results report to: {outfile}")
    except Exception as e:
        logging.error(f"Failed to write results to JSON: {e}")
        raise typer.Exit(code=1) from e

    logging.info("Black-Litterman optimization pipeline completed successfully.")


if __name__ == "__main__":
    app()
