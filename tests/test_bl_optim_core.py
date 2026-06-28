import numpy as np
import pandas as pd
import pytest

from service.bl_optim_service import (
    TAU,
    compute_efficient_frontier_long_only,
    compute_implied_excess_returns,
    compute_scaled_covariance,
    construct_market_weights,
    construct_market_weights_dict,
    get_zero_views_black_litterman,
    optimize_frontier_point,
    optimize_tangency_portfolio,
)


@pytest.mark.unit
def test_construct_market_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock yfinance_service methods
    monkeypatch.setattr(
        "service.bl_optim_service.get_ticker_info",
        lambda ticker: (
            {"marketCap": 200_000_000 if ticker == "AAPL" else 100_000_000, "currency": "USD"}
        ),
    )
    monkeypatch.setattr(
        "service.bl_optim_service.get_exchange_rate",
        lambda from_curr, to_curr: 0.9 if from_curr == "USD" else 1.0,
    )

    tickers = ["AAPL", "MSFT"]
    weights, _caps_eur = construct_market_weights_dict(tickers)

    # AAPL cap = 200m * 0.9 = 180m EUR
    # MSFT cap = 100m * 0.9 = 90m EUR
    # Total = 270m EUR
    assert len(weights) == 2
    np.testing.assert_almost_equal(weights["AAPL"], 2.0 / 3.0)
    np.testing.assert_almost_equal(weights["MSFT"], 1.0 / 3.0)

    # Check ndarray helper
    weights_arr = construct_market_weights(tickers)
    assert len(weights_arr) == 2
    np.testing.assert_almost_equal(weights_arr[0], 2.0 / 3.0)
    np.testing.assert_almost_equal(weights_arr[1], 1.0 / 3.0)


@pytest.mark.unit
def test_compute_scaled_covariance() -> None:
    dates = pd.date_range("2023-01-01", periods=3)
    data = {
        "AAPL": [0.01, -0.01, 0.02],
        "MSFT": [-0.02, 0.03, -0.01],
    }
    df = pd.DataFrame(data, index=dates)

    scaled_cov = compute_scaled_covariance(df, 30)
    assert scaled_cov.shape == (2, 2)

    # Let's verify scaling factor
    expected_cov = df.cov().to_numpy() * 30.0
    np.testing.assert_almost_equal(scaled_cov, expected_cov)


@pytest.mark.unit
def test_compute_implied_excess_returns() -> None:
    sigma = np.array([[0.1, 0.02], [0.02, 0.08]])
    w = np.array([0.6, 0.4])
    lam = 2.5

    pi = compute_implied_excess_returns(lam, sigma, w)

    # Expected: lam * (sigma @ w)
    expected_pi = np.array([0.17, 0.11])
    np.testing.assert_almost_equal(pi, expected_pi)


@pytest.mark.unit
def test_get_zero_views_black_litterman() -> None:
    pi = np.array([0.05, 0.03])
    sigma = np.array([[0.1, 0.01], [0.01, 0.1]])

    expected_r, adjusted_cov = get_zero_views_black_litterman(pi, sigma, tau=TAU)

    np.testing.assert_almost_equal(expected_r, pi)
    np.testing.assert_almost_equal(adjusted_cov, (1.0 + TAU) * sigma)


@pytest.mark.unit
def test_portfolio_optimization() -> None:
    expected_returns = np.array([0.12, 0.08])
    covariance_matrix = np.array([[0.04, 0.01], [0.01, 0.02]])
    r_f = 0.02

    # Max Sharpe
    w_ms = optimize_tangency_portfolio(expected_returns, covariance_matrix, r_f)
    assert len(w_ms) == 2
    np.testing.assert_almost_equal(np.sum(w_ms), 1.0)
    assert w_ms[0] >= 0.0
    assert w_ms[1] >= 0.0

    # Target Return
    target_r = 0.10
    w_tr = optimize_frontier_point(expected_returns, covariance_matrix, target_r)
    np.testing.assert_almost_equal(np.sum(w_tr), 1.0)

    # Efficient Frontier
    vols, rets, weights_list = compute_efficient_frontier_long_only(
        expected_returns, covariance_matrix, n_points=10
    )
    assert len(vols) == 10
    assert len(rets) == 10
    assert len(weights_list) == 10
