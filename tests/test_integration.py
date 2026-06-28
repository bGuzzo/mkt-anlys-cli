import importlib
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

# Import the CLI apps dynamically due to dashes in filenames
mkt_cli = importlib.import_module("mkt-anlys-cli")
portfolio_cli = importlib.import_module("portfolio-cli")


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
def test_mkt_anlys_cli_integration(tmp_path: Path, cli_runner: CliRunner) -> None:
    """
    Integration test that runs the full mkt-anlys-cli pipeline using mock data.
    """
    outdir = tmp_path / "results"

    # Define mock price and dividend data
    dates = pd.date_range("2025-01-01", periods=10)
    mock_aapl = pd.DataFrame(
        {"Close": [100.0 + i for i in range(10)], "Dividends": [0.0] * 10}, index=dates
    )
    mock_msft = pd.DataFrame(
        {"Close": [200.0 + i for i in range(10)], "Dividends": [0.0] * 10}, index=dates
    )
    mock_benchmark = pd.DataFrame(
        {"Close": [150.0 + i for i in range(10)], "Dividends": [0.0] * 10}, index=dates
    )
    mock_usdeur = pd.Series([0.9] * 10, index=dates)

    # Patch the yfinance service calls to isolate from external network
    with (
        patch("service.yfinance_service.get_ticker_info") as mock_info,
        patch("service.yfinance_service.get_market_data") as mock_market_data,
        patch("service.yfinance_service.get_historical_exchange_rates") as mock_hist_rates,
    ):
        # Mock ticker info to return standard currency metadata
        def side_effect_info(ticker: str) -> dict[str, Any]:
            if ticker == "AAPL" or ticker == "MSFT" or ticker == "^GSPC":
                return {"currency": "USD"}
            return {}

        mock_info.side_effect = side_effect_info

        # Mock historical market data
        def side_effect_market(ticker: str, period: str) -> pd.DataFrame:
            if ticker == "AAPL":
                return mock_aapl
            elif ticker == "MSFT":
                return mock_msft
            elif ticker == "^GSPC":
                return mock_benchmark
            elif ticker == "USDEUR=X":
                return pd.DataFrame({"Close": mock_usdeur})
            return pd.DataFrame()

        mock_market_data.side_effect = side_effect_market

        # Mock historical exchange rates
        mock_hist_rates.return_value = mock_usdeur

        # Run the command via Typer CliRunner
        result = cli_runner.invoke(
            mkt_cli.app,
            [
                "--weights",
                '{"AAPL": 0.5, "MSFT": 0.5}',
                "--benchmark",
                "^GSPC",
                "--outdir",
                str(outdir),
                "--period",
                "1y",
                "--idx_name",
                "test_index",
            ],
        )

        assert result.exit_code == 0, f"CLI execution failed: {result.output}"

        # Verify output files were created
        summary_csv = outdir / "test_index_summary.csv"
        chart_png = outdir / "test_index_1y.png"
        ef_chart_png = outdir / "test_index_efficient_frontier_1y.png"

        assert summary_csv.exists(), f"Summary CSV not found at {summary_csv}"
        assert chart_png.exists(), f"Chart PNG not found at {chart_png}"
        assert ef_chart_png.exists(), f"Efficient Frontier Chart PNG not found at {ef_chart_png}"

        # Verify content of the CSV summary
        df_summary = pd.read_csv(summary_csv)
        assert "Metric" in df_summary.columns
        assert "1y" in df_summary.columns
        assert df_summary["Metric"].str.contains("test_index").any()


@pytest.mark.integration
def test_portfolio_cli_integration(tmp_path: Path, cli_runner: CliRunner) -> None:
    """
    Integration test that runs the full portfolio-cli pipeline using mock data.
    """
    input_file = tmp_path / "tickers.json"
    outfile = tmp_path / "allocations.csv"

    # Write a test tickers list
    tickers_list = ["AAPL", "MSFT"]
    with open(input_file, "w") as f:
        json.dump(tickers_list, f)

    # Patch yfinance_service helper functions
    with (
        patch("service.yfinance_service.get_ticker_info") as mock_info,
        patch("service.yfinance_service.get_exchange_rate") as mock_rate,
    ):
        # Mock ticker info with market caps
        def side_effect_info(ticker: str) -> dict[str, Any]:
            if ticker == "AAPL":
                return {"marketCap": 2000000000000, "currency": "USD"}
            elif ticker == "MSFT":
                return {"marketCap": 1800000000000, "currency": "USD"}
            return {}

        mock_info.side_effect = side_effect_info

        # Mock exchange rate (1 USD = 0.9 EUR, and 1 EUR = 1.1 USD)
        def side_effect_rate(from_curr: str, to_curr: str) -> float:
            if from_curr == "USD" and to_curr == "EUR":
                return 0.9
            if from_curr == "EUR" and to_curr == "USD":
                return 1.1
            return 1.0

        mock_rate.side_effect = side_effect_rate

        # Run the command via Typer CliRunner
        result = cli_runner.invoke(
            portfolio_cli.app,
            [
                "--input",
                str(input_file),
                "--amount",
                "10000",
                "--outfile",
                str(outfile),
            ],
        )

        assert result.exit_code == 0, f"CLI execution failed: {result.output}"

        # Verify outfile exists and read results
        assert outfile.exists(), f"Allocations CSV not found at {outfile}"
        df_allocations = pd.read_csv(outfile)

        # Expected sorted columns/tickers: AAPL (2.0T USD -> 1.8T EUR), MSFT (1.8T USD -> 1.62T EUR)
        # AAPL Weight = 2.0 / 3.8 = 52.63%
        # MSFT Weight = 1.8 / 3.8 = 47.37%
        assert len(df_allocations) == 2
        assert df_allocations.iloc[0]["Ticker"] == "AAPL"
        assert df_allocations.iloc[1]["Ticker"] == "MSFT"

        # Check total allocated amount is equal to 10000 Euros
        total_euros = df_allocations["Euros to Allocate"].sum()
        np.testing.assert_almost_equal(total_euros, 10000.0, decimal=1)
