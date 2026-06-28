import numpy as np
import pandas as pd
import pytest

from service.bl_optimization_service import (
    calculate_historical_statistics,
    compute_black_litterman_posterior,
    compute_efficient_frontier_analytical,
)


@pytest.fixture
def dummy_returns() -> pd.DataFrame:
    """
    Returns a dataframe with 5 days of dummy returns for 3 assets.
    """
    dates = pd.date_range("2026-01-01", periods=5)
    data = {
        "AssetA": [0.01, -0.005, 0.02, 0.005, -0.01],
        "AssetB": [0.005, 0.01, -0.01, 0.015, 0.02],
        "AssetC": [-0.002, 0.008, 0.012, -0.005, 0.01],
    }
    return pd.DataFrame(data, index=dates)


@pytest.mark.unit
def test_calculate_historical_statistics(dummy_returns: pd.DataFrame) -> None:
    ann_returns, ann_cov = calculate_historical_statistics(dummy_returns)

    assert isinstance(ann_returns, pd.Series)
    assert isinstance(ann_cov, pd.DataFrame)

    assert list(ann_returns.index) == ["AssetA", "AssetB", "AssetC"]
    assert list(ann_cov.index) == ["AssetA", "AssetB", "AssetC"]
    assert list(ann_cov.columns) == ["AssetA", "AssetB", "AssetC"]

    # Simple check on annualized returns
    mean_a = dummy_returns["AssetA"].mean()
    expected_ann_a = (1 + mean_a) ** 252 - 1
    np.testing.assert_almost_equal(ann_returns["AssetA"], expected_ann_a)

    # Simple check on annualized covariance
    cov_ab = dummy_returns["AssetA"].cov(dummy_returns["AssetB"])
    expected_cov_ab = cov_ab * 252
    np.testing.assert_almost_equal(ann_cov.loc["AssetA", "AssetB"], expected_cov_ab)


@pytest.mark.unit
def test_compute_black_litterman_posterior_no_views(dummy_returns: pd.DataFrame) -> None:
    ann_returns, ann_cov = calculate_historical_statistics(dummy_returns)
    mkt_weights = pd.Series({"AssetA": 0.4, "AssetB": 0.4, "AssetC": 0.2})

    # Call BL with no views
    mu_bl, sigma_bl = compute_black_litterman_posterior(
        ann_returns=ann_returns,
        ann_cov=ann_cov,
        mkt_weights=mkt_weights,
        risk_aversion=3.0,
        tau=0.05,
    )

    # With no views, posterior returns should equal prior equilibrium returns (Pi)
    # Pi = lambda * Sigma * w
    sigma = ann_cov.to_numpy()
    w = mkt_weights.to_numpy()
    expected_pi = 3.0 * (sigma @ w)

    np.testing.assert_array_almost_equal(mu_bl.to_numpy(), expected_pi)
    np.testing.assert_array_almost_equal(sigma_bl.to_numpy(), sigma)


@pytest.mark.unit
def test_compute_black_litterman_posterior_with_views(dummy_returns: pd.DataFrame) -> None:
    ann_returns, ann_cov = calculate_historical_statistics(dummy_returns)
    mkt_weights = pd.Series({"AssetA": 0.4, "AssetB": 0.4, "AssetC": 0.2})

    # Define a simple view: AssetA will outperform AssetB by 2%
    # P = [1, -1, 0]
    # Q = [0.02]
    p_views = np.array([[1.0, -1.0, 0.0]])
    q_views = np.array([0.02])

    mu_bl, sigma_bl = compute_black_litterman_posterior(
        ann_returns=ann_returns,
        ann_cov=ann_cov,
        mkt_weights=mkt_weights,
        risk_aversion=3.0,
        tau=0.05,
        p_views=p_views,
        q_views=q_views,
    )

    assert len(mu_bl) == 3
    assert sigma_bl.shape == (3, 3)
    # The posterior returns should be different from the prior equilibrium returns
    # because of the view
    sigma = ann_cov.to_numpy()
    w = mkt_weights.to_numpy()
    pi_prior = 3.0 * (sigma @ w)

    assert not np.array_equal(mu_bl.to_numpy(), pi_prior)


@pytest.mark.unit
def test_compute_efficient_frontier_analytical() -> None:
    # Set up some simple known returns and diagonal covariance
    assets = ["Asset1", "Asset2"]
    mu = pd.Series([0.12, 0.08], index=assets)
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.02]], index=assets, columns=assets)

    frontier_vols, frontier_returns, tangency_weights, tangency_vol, tangency_return = (
        compute_efficient_frontier_analytical(mu=mu, cov=cov, rf_rate=0.02, n_points=50)
    )

    assert len(frontier_vols) == 50
    assert len(frontier_returns) == 50
    assert len(tangency_weights) == 2

    # Tangency weights analytical formula verification
    # w_tan = Sigma^-1 * (mu - rf * 1) / (1^T * Sigma^-1 * (mu - rf * 1))
    # Sigma^-1 = diag(1/0.04, 1/0.02) = diag(25, 50)
    # mu - rf * 1 = [0.10, 0.06]
    # Sigma^-1 * (mu - rf * 1) = [2.5, 3.0]
    # 1^T * [2.5, 3.0] = 5.5
    # w_tan = [2.5/5.5, 3.0/5.5] = [5/11, 6/11] ~ [0.4545, 0.5454]
    np.testing.assert_almost_equal(tangency_weights["Asset1"], 5.0 / 11.0, decimal=4)
    np.testing.assert_almost_equal(tangency_weights["Asset2"], 6.0 / 11.0, decimal=4)

    # Check expected return and volatility of tangency portfolio
    expected_ret = (5.0 / 11.0) * 0.12 + (6.0 / 11.0) * 0.08
    np.testing.assert_almost_equal(tangency_return, expected_ret, decimal=4)

    expected_var = (5.0 / 11.0) ** 2 * 0.04 + (6.0 / 11.0) ** 2 * 0.02
    np.testing.assert_almost_equal(tangency_vol, np.sqrt(expected_var), decimal=4)
