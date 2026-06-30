import importlib
import json
from pathlib import Path  # noqa: TC003
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

# Import the CLI app dynamically due to dashes in the filename
bl_ef_cli = importlib.import_module("bl-ef-optim")


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.mark.integration
def test_bl_ef_optim_cli_integration(tmp_path: Path, cli_runner: CliRunner) -> None:
    """
    Integration test that runs the full bl-ef-optim CLI pipeline using mock data.
    """
    tickers_file = tmp_path / "tickers.json"
    outdir = tmp_path / "results"

    # Write a test tickers list
    tickers_list = ["AAPL", "MSFT"]
    with open(tickers_file, "w") as f:
        json.dump(tickers_list, f)

    # Define mock daily price data
    dates = pd.date_range("2025-01-01", periods=10)
    mock_aapl = pd.DataFrame({"Close": [150.0 + i * 1.5 for i in range(10)]}, index=dates)
    mock_msft = pd.DataFrame({"Close": [250.0 + i * 2.0 for i in range(10)]}, index=dates)
    mock_vt = pd.DataFrame({"Close": [100.0 + i * 1.0 for i in range(10)]}, index=dates)
    # Risk free rate ticker yield (e.g. 4.25%)
    mock_rf_yield = pd.DataFrame({"Close": [4.25] * 10}, index=dates)

    with (
        patch("service.bl_optim_service.get_ticker_info") as mock_info,
        patch("service.bl_optim_service.get_market_data") as mock_market_data,
        patch("service.bl_optim_service.get_exchange_rate") as mock_rate,
        patch("service.main_service.align_and_combine_data") as mock_align,
        patch("service.main_service.normalize_data_to_usd") as mock_norm,
    ):
        # Mock ticker info with market caps
        def side_effect_info(ticker: str) -> dict[str, Any]:
            if ticker == "AAPL":
                return {"marketCap": 2000000000000, "currency": "USD"}
            elif ticker == "MSFT":
                return {"marketCap": 1800000000000, "currency": "USD"}
            elif ticker == "VT":
                return {"marketCap": 1500000000000, "currency": "USD"}
            return {}

        mock_info.side_effect = side_effect_info

        # Mock market data downloading and caching
        def side_effect_market(ticker: str, period: str) -> pd.DataFrame:
            if ticker == "AAPL":
                return mock_aapl
            elif ticker == "MSFT":
                return mock_msft
            elif ticker == "VT":
                return mock_vt
            elif ticker in ("^ZT=F", "^YT=F"):
                return mock_rf_yield
            return pd.DataFrame()

        mock_market_data.side_effect = side_effect_market

        # Mock exchange rate
        mock_rate.return_value = 1.0  # 1 USD = 1.0 USD

        # Mock align and normalize
        mock_align.return_value = {"AAPL": mock_aapl, "MSFT": mock_msft, "VT": mock_vt}
        mock_norm.return_value = {"AAPL": mock_aapl, "MSFT": mock_msft, "VT": mock_vt}

        # Run the command via Typer CliRunner
        result = cli_runner.invoke(
            bl_ef_cli.app,
            [
                "--tickers",
                str(tickers_file),
                "--horizon",
                "2mo",
                "--risk-free",
                "^ZT=F",
                "--benchmark",
                "VT",
                "--period",
                "1y",
                "--outdir",
                str(outdir),
            ],
        )

        assert result.exit_code == 0, f"CLI execution failed: {result.output}"

        # Verify output files were created
        output_json = outdir / "bl_optimization_results.json"
        assert output_json.exists(), f"Output JSON not found at {output_json}"

        # Verify separate report files exist
        tangency_json = outdir / "tangency_portfolio_only.json"
        capm_json = outdir / "capm_alpha_beta.json"
        assert tangency_json.exists(), "tangency_portfolio_only.json was not created"
        assert capm_json.exists(), "capm_alpha_beta.json was not created"

        # Verify the structure of the JSON results
        with open(output_json) as f:
            data = json.load(f)

        assert "tickers" in data
        assert "horizon_days" in data
        assert data["horizon_days"] == 42  # 2mo * 21 = 42
        assert "market_caps_usd" in data
        assert "market_weights" in data
        assert "equilibrium_excess_returns" in data
        assert "tangency_portfolio" in data
        assert "efficient_frontier" in data
        assert "config" in data

        # Check weights sum to approximately 1
        tangency_weights = data["tangency_portfolio"]["weights"]
        total_weight = sum(tangency_weights.values())
        np.testing.assert_almost_equal(total_weight, 1.0, decimal=5)

        # Verify tangency_portfolio_only.json structure
        with open(tangency_json) as f:
            t_data = json.load(f)
        for key in ["weights", "expected_return", "volatility", "sharpe_ratio", "beta", "alpha"]:
            assert key in t_data

        # Verify capm_alpha_beta.json structure
        with open(capm_json) as f:
            c_data = json.load(f)
        for key in [
            "tangency_alpha",
            "tangency_beta",
            "benchmark_return",
            "benchmark_volatility",
            "individual_assets",
        ]:
            assert key in c_data
        for asset in ["AAPL", "MSFT"]:
            assert asset in c_data["individual_assets"]
            assert "alpha" in c_data["individual_assets"][asset]
            assert "beta" in c_data["individual_assets"][asset]


@pytest.mark.integration
def test_bl_ef_optim_cli_integration_with_eur_buy(tmp_path: Path, cli_runner: CliRunner) -> None:
    """
    Integration test that runs the full bl-ef-optim CLI pipeline with --eur-buy using mock data.
    """
    tickers_file = tmp_path / "tickers.json"
    outdir = tmp_path / "results"

    # Write a test tickers list
    tickers_list = ["AAPL", "MSFT"]
    with open(tickers_file, "w") as f:
        json.dump(tickers_list, f)

    # Define mock daily price data
    dates = pd.date_range("2025-01-01", periods=10)
    mock_aapl = pd.DataFrame({"Close": [150.0 + i * 1.5 for i in range(10)]}, index=dates)
    mock_msft = pd.DataFrame({"Close": [250.0 + i * 2.0 for i in range(10)]}, index=dates)
    mock_vt = pd.DataFrame({"Close": [100.0 + i * 1.0 for i in range(10)]}, index=dates)
    # Risk free rate ticker yield (e.g. 4.25%)
    mock_rf_yield = pd.DataFrame({"Close": [4.25] * 10}, index=dates)

    with (
        patch("service.bl_optim_service.get_ticker_info") as mock_info,
        patch("service.portfolio_service.get_ticker_info") as mock_port_info,
        patch("service.bl_optim_service.get_market_data") as mock_market_data,
        patch("service.bl_optim_service.get_exchange_rate") as mock_rate,
        patch("service.portfolio_service.get_exchange_rate") as mock_port_rate,
        patch("service.main_service.align_and_combine_data") as mock_align,
        patch("service.main_service.normalize_data_to_usd") as mock_norm,
    ):
        # Mock ticker info with market caps
        def side_effect_info(ticker: str) -> dict[str, Any]:
            if ticker == "AAPL":
                return {"marketCap": 2000000000000, "currency": "USD"}
            elif ticker == "MSFT":
                return {"marketCap": 1800000000000, "currency": "USD"}
            elif ticker == "VT":
                return {"marketCap": 1500000000000, "currency": "USD"}
            return {}

        mock_info.side_effect = side_effect_info
        mock_port_info.side_effect = side_effect_info

        # Mock market data downloading and caching
        def side_effect_market(ticker: str, period: str) -> pd.DataFrame:
            if ticker == "AAPL":
                return mock_aapl
            elif ticker == "MSFT":
                return mock_msft
            elif ticker == "VT":
                return mock_vt
            elif ticker in ("^ZT=F", "^YT=F"):
                return mock_rf_yield
            return pd.DataFrame()

        mock_market_data.side_effect = side_effect_market

        # Mock exchange rate
        mock_rate.return_value = 1.0  # 1 USD = 1.0 USD
        mock_port_rate.return_value = 1.0  # 1 USD = 1.0 USD

        # Mock align and normalize
        mock_align.return_value = {"AAPL": mock_aapl, "MSFT": mock_msft, "VT": mock_vt}
        mock_norm.return_value = {"AAPL": mock_aapl, "MSFT": mock_msft, "VT": mock_vt}

        # Run the command via Typer CliRunner with --usd-buy
        result = cli_runner.invoke(
            bl_ef_cli.app,
            [
                "--tickers",
                str(tickers_file),
                "--horizon",
                "2mo",
                "--risk-free",
                "^ZT=F",
                "--benchmark",
                "VT",
                "--period",
                "1y",
                "--outdir",
                str(outdir),
                "--usd-buy",
                "10000",
            ],
        )

        assert result.exit_code == 0, f"CLI execution failed: {result.output}"

        # Verify separate report files exist
        tangency_json = outdir / "tangency_portfolio_only.json"
        output_json = outdir / "bl_optimization_results.json"
        assert tangency_json.exists(), "tangency_portfolio_only.json was not created"
        assert output_json.exists(), "bl_optimization_results.json was not created"

        # Verify structure contains allocation
        with open(tangency_json) as f:
            t_data = json.load(f)
        assert "allocation" in t_data
        assert t_data["allocation"]["total_investment_usd"] == 10000.0
        assert "AAPL" in t_data["allocation"]["constituents"]
        assert "MSFT" in t_data["allocation"]["constituents"]

        with open(output_json) as f:
            data = json.load(f)
        assert "allocation" in data["tangency_portfolio"]
        assert data["tangency_portfolio"]["allocation"]["total_investment_usd"] == 10000.0


