import numpy as np
import pandas as pd
import pytest

from service.reporting_service import (
    calculate_correlation,
    calculate_portfolio_daily_returns,
    calculate_portfolio_yield,
    compute_metrics,
)


@pytest.fixture
def sample_data() -> dict[str, pd.DataFrame]:
    # 5 days of data
    dates = pd.date_range("2023-01-01", periods=5)

    # AAPL goes 100 -> 105 (+5%)
    aapl_close = [100.0, 101.0, 102.0, 104.0, 105.0]
    aapl_div = [0.0, 0.0, 1.5, 0.0, 0.0]

    # MSFT goes 200 -> 190 (-5%)
    msft_close = [200.0, 198.0, 195.0, 192.0, 190.0]
    msft_div = [0.0, 0.0, 0.0, 0.0, 0.0]

    df_aapl = pd.DataFrame({"Close": aapl_close, "Dividends": aapl_div}, index=dates)
    df_msft = pd.DataFrame({"Close": msft_close, "Dividends": msft_div}, index=dates)

    return {"AAPL": df_aapl, "MSFT": df_msft}


@pytest.mark.unit
def test_calculate_portfolio_daily_returns(sample_data: dict[str, pd.DataFrame]) -> None:
    weights = {"AAPL": 0.5, "MSFT": 0.5}
    returns = calculate_portfolio_daily_returns(sample_data, weights)

    # We should have 4 days of returns
    assert len(returns) == 4

    # First return: AAPL: 101/100-1 = 0.01, MSFT: 198/200-1 = -0.01
    # Port return: 0.5*0.01 + 0.5*(-0.01) = 0.0
    np.testing.assert_almost_equal(returns.iloc[0], 0.0)


@pytest.mark.unit
def test_calculate_portfolio_yield(sample_data: dict[str, pd.DataFrame]) -> None:
    weights = {"AAPL": 0.5, "MSFT": 0.5}
    div_yield = calculate_portfolio_yield(sample_data, weights)

    # AAPL yield: (1.5 / 100) * (252 / 5) = 0.015 * 50.4 = 0.756
    # MSFT yield: 0.0
    # Port yield: 0.5 * 0.756 = 0.378
    np.testing.assert_almost_equal(div_yield, 0.378)


@pytest.mark.unit
def test_compute_metrics() -> None:
    # Create daily returns that compound to exactly 10% over 252 days
    # daily rate = (1.10)^(1/252) - 1
    daily_rate = (1.10) ** (1 / 252) - 1
    returns = pd.Series([daily_rate] * 252)

    metrics = compute_metrics(returns, 0.05)

    # Return should be ~ 10%
    np.testing.assert_almost_equal(metrics["Return"], 0.10)

    # Volatility should be ~ 0 since variance of constant is 0
    np.testing.assert_almost_equal(metrics["Volatility"], 0.0)

    # Yield should be what we passed in
    assert metrics["Yield"] == 0.05


@pytest.mark.unit
def test_compute_metrics_empty() -> None:
    returns = pd.Series(dtype=float)
    metrics = compute_metrics(returns, 0.0)
    assert metrics["Return"] == 0.0
    assert metrics["Volatility"] == 0.0
    assert metrics["Yield"] == 0.0


@pytest.mark.unit
def test_calculate_correlation() -> None:
    s1 = pd.Series([0.1, 0.2, -0.1, 0.0])
    s2 = pd.Series([0.1, 0.2, -0.1, 0.0])
    # Perfect correlation
    assert calculate_correlation(s1, s2) == 1.0

    s3 = pd.Series([-0.1, -0.2, 0.1, 0.0])
    # Inverse correlation
    assert calculate_correlation(s1, s3) == -1.0

    s_empty = pd.Series(dtype=float)
    assert calculate_correlation(s1, s_empty) == 0.0
