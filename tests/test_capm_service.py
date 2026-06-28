from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from service.capm_service import (
    analyze_capm,
    calculate_alpha,
    calculate_alphas,
    calculate_annualized_return,
    calculate_beta,
    calculate_betas,
    calculate_tangency_portfolio_returns,
    fetch_and_normalize_asset,
)


@pytest.fixture
def sample_normalized_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2026-01-01", periods=5)
    # Asset A goes 100 -> 101 -> 102 -> 103 -> 104 (+ ~1% daily close trend)
    df_a = pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=dates)
    # Asset B goes 50 -> 49 -> 48 -> 47 -> 46 (~ -2% daily close trend)
    df_b = pd.DataFrame({"Close": [50.0, 49.0, 48.0, 47.0, 46.0]}, index=dates)
    return {"AssetA": df_a, "AssetB": df_b}


@pytest.fixture
def sample_benchmark_data() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=5)
    # Benchmark goes 1000 -> 1010 -> 1020 -> 1030 -> 1040 (~1% daily close trend)
    return pd.DataFrame({"Close": [1000.0, 1010.0, 1020.0, 1030.0, 1040.0]}, index=dates)


@pytest.mark.unit
def test_calculate_annualized_return() -> None:
    # 252 days of daily return that compounds to exactly 10%
    daily_rate = (1.10) ** (1 / 252) - 1
    returns = pd.Series([daily_rate] * 252)
    ann_ret = calculate_annualized_return(returns)
    np.testing.assert_almost_equal(ann_ret, 0.10)

    # Empty series
    assert calculate_annualized_return(pd.Series(dtype=float)) == 0.0


@pytest.mark.unit
def test_calculate_tangency_portfolio_returns(
    sample_normalized_data: dict[str, pd.DataFrame]
) -> None:
    weights = {"AssetA": 0.6, "AssetB": 0.4}
    portfolio_returns = calculate_tangency_portfolio_returns(sample_normalized_data, weights)

    assert len(portfolio_returns) == 4

    # Verification of first day return:
    # AssetA: 101/100 - 1 = 0.01
    # AssetB: 49/50 - 1 = -0.02
    # Portfolio: 0.6 * 0.01 + 0.4 * (-0.02) = 0.006 - 0.008 = -0.002
    np.testing.assert_almost_equal(portfolio_returns.iloc[0], -0.002)


@pytest.mark.unit
def test_calculate_beta() -> None:
    dates = pd.date_range("2026-01-01", periods=5)
    benchmark_returns = pd.Series([0.01, 0.02, -0.01, 0.015], index=dates[1:])
    # Perfectly aligned asset
    asset_returns = benchmark_returns * 1.5

    beta = calculate_beta(asset_returns, benchmark_returns)
    np.testing.assert_almost_equal(beta, 1.5)

    # Empty returns
    assert calculate_beta(pd.Series(dtype=float), benchmark_returns) == 0.0


@pytest.mark.unit
def test_calculate_betas_and_alphas(
    sample_normalized_data: dict[str, pd.DataFrame], sample_benchmark_data: pd.DataFrame
) -> None:
    weights = {"AssetA": 0.5, "AssetB": 0.5}
    benchmark_returns = sample_benchmark_data["Close"].pct_change().dropna()
    portfolio_returns = calculate_tangency_portfolio_returns(sample_normalized_data, weights)

    betas = calculate_betas(
        sample_normalized_data, portfolio_returns, benchmark_returns, weights
    )
    assert "portfolio" in betas
    assert "AssetA" in betas
    assert "AssetB" in betas

    alphas = calculate_alphas(
        sample_normalized_data,
        portfolio_returns,
        benchmark_returns,
        betas,
        weights,
        rf_rate=0.02,
    )
    assert "portfolio" in alphas
    assert "AssetA" in alphas
    assert "AssetB" in alphas


@pytest.mark.unit
def test_calculate_alpha() -> None:
    # Standard formula verification:
    # alpha = ann_asset_return - (rf + beta * (ann_benchmark_return - rf))
    # Let E(Rp) = 12%, E(Rm) = 8%, beta = 1.2, rf = 3%
    # Expected alpha = 12% - (3% + 1.2 * (8% - 3%)) = 12% - (3% + 6%) = 3%

    # Create dummy returns with specific compounding
    dates = pd.date_range("2026-01-01", periods=253)
    daily_m = (1.08) ** (1 / 252) - 1
    daily_a = (1.12) ** (1 / 252) - 1

    benchmark_returns = pd.Series([daily_m] * 252, index=dates[1:])
    asset_returns = pd.Series([daily_a] * 252, index=dates[1:])

    alpha = calculate_alpha(asset_returns, benchmark_returns, beta=1.2, rf_rate=0.03)
    np.testing.assert_almost_equal(alpha, 0.03, decimal=4)


@pytest.mark.unit
def test_analyze_capm(
    sample_normalized_data: dict[str, pd.DataFrame], sample_benchmark_data: pd.DataFrame
) -> None:
    weights = {"AssetA": 0.5, "AssetB": 0.5}
    res = analyze_capm(sample_normalized_data, sample_benchmark_data, weights, rf_rate=0.01)

    assert "benchmark_expected_return" in res
    assert "portfolio_expected_return" in res
    assert "betas" in res
    assert "alphas" in res
    assert res["rf_rate"] == 0.01


@pytest.mark.unit
@patch("service.capm_service.get_market_data")
@patch("service.capm_service.get_ticker_info")
@patch("service.capm_service.get_historical_exchange_rates")
def test_fetch_and_normalize_asset(
    mock_get_rates: MagicMock, mock_get_info: MagicMock, mock_get_data: MagicMock
) -> None:
    dates = pd.date_range("2026-01-01", periods=3)
    mock_df = pd.DataFrame({"Close": [100.0, 102.0, 104.0]}, index=dates)
    mock_get_data.return_value = mock_df

    # Case 1: Ticker already in EUR
    mock_get_info.return_value = {"currency": "EUR"}
    df_eur = fetch_and_normalize_asset("TEST", "1y")
    assert not df_eur.empty
    np.testing.assert_array_equal(df_eur["Close"].values, [100.0, 102.0, 104.0])

    # Case 2: Ticker in USD, converted using rates
    mock_get_info.return_value = {"currency": "USD"}
    mock_rates = pd.Series([0.90, 0.91, 0.92], index=dates)
    mock_get_rates.return_value = mock_rates

    df_usd_to_eur = fetch_and_normalize_asset("TEST", "1y")
    assert not df_usd_to_eur.empty
    # Verified multiplication: 100 * 0.90 = 90.0, 102 * 0.91 = 92.82, 104 * 0.92 = 95.68
    np.testing.assert_almost_equal(df_usd_to_eur["Close"].iloc[0], 90.0)
    np.testing.assert_almost_equal(df_usd_to_eur["Close"].iloc[1], 92.82)
    np.testing.assert_almost_equal(df_usd_to_eur["Close"].iloc[2], 95.68)
