import logging

import numpy as np
import pandas as pd

# Standard annualization factor
TRADING_DAYS_PER_YEAR = 252


def calculate_historical_statistics(
    returns_df: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Calculates annualized mean returns and the annualized covariance matrix from daily returns.
    Assumes 252 trading days per year.
    """
    logging.info("Calculating annualized historical returns and covariance matrix...")
    mean_daily = returns_df.mean()
    ann_returns = (1 + mean_daily) ** TRADING_DAYS_PER_YEAR - 1

    cov_daily = returns_df.cov()
    ann_cov = cov_daily * TRADING_DAYS_PER_YEAR

    return ann_returns, ann_cov


def compute_black_litterman_posterior(
    ann_returns: pd.Series,
    ann_cov: pd.DataFrame,
    mkt_weights: pd.Series,
    risk_aversion: float = 3.0,
    tau: float = 0.05,
    p_views: np.ndarray | None = None,
    q_views: np.ndarray | None = None,
    omega: np.ndarray | None = None,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Computes the Black-Litterman posterior returns and covariance matrix.
    If no views are provided, the posterior returns default to the implied
    equilibrium returns (prior).

    Parameters:
    - ann_returns: Annualized expected returns (historical/prior)
    - ann_cov: Annualized covariance matrix of returns
    - mkt_weights: Market portfolio weights (prior weights)
    - risk_aversion: Risk aversion coefficient (lambda)
    - tau: Scale factor for prior uncertainty
    - p_views: View projection matrix (K x N)
    - q_views: View expected returns vector (K x 1)
    - omega: View uncertainty covariance matrix (K x K)
    """
    logging.info("Computing Black-Litterman equilibrium and posterior...")
    assets = list(ann_returns.index)
    n_assets = len(assets)

    # 1. Implied equilibrium returns (Prior Pi)
    # Pi = lambda * Sigma * w
    sigma = ann_cov.to_numpy()
    w = mkt_weights.reindex(assets).to_numpy()

    # Check for NaN weights or mismatch
    if np.any(np.isnan(w)):
        logging.warning(
            "Market weights contain NaN or missing values. Defaulting to equal weights."
        )
        w = np.ones(n_assets) / n_assets

    pi_prior = risk_aversion * (sigma @ w)

    if p_views is None or q_views is None or len(p_views) == 0:
        logging.info(
            "No investor views provided. Posterior returns default to implied prior returns."
        )
        return pd.Series(pi_prior, index=assets), ann_cov

    p = np.array(p_views, dtype=float)
    q = np.array(q_views, dtype=float).reshape(-1, 1)

    # If omega is not provided, use the standard diagonal approximation:
    # omega = diag(P * (tau * Sigma) * P_T)
    if omega is None:
        omega_full = p @ (tau * sigma) @ p.T
        omega = np.diag(np.diag(omega_full))
        # Ensure no exact zeros on diagonal for stability
        omega[omega == 0] = 1e-6
    else:
        omega = np.array(omega, dtype=float)

    # Standard BL formula:
    # mu_bl = Pi + tau * Sigma * P_T * (P * tau * Sigma * P_T + Omega)^-1 * (Q - P * Pi)
    pi_prior_reshaped = pi_prior.reshape(-1, 1)

    # Avoid singular matrix by adding small regularization if needed
    sigma_scaled = tau * sigma
    view_cov_inv_term = p @ sigma_scaled @ p.T + omega

    try:
        inv_term = np.linalg.inv(view_cov_inv_term)
        mu_bl_raw = pi_prior_reshaped + sigma_scaled @ p.T @ inv_term @ (q - p @ pi_prior_reshaped)
        mu_bl = mu_bl_raw.flatten()
    except np.linalg.LinAlgError as err:
        logging.error(f"Inversion failed in Black-Litterman formula: {err}. Using prior Pi.")
        mu_bl = pi_prior

    # Posterior Covariance
    # Sigma_bl = Sigma + [(tau * Sigma)^-1 + P_T * Omega^-1 * P]^-1
    try:
        tau_sigma_inv = np.linalg.inv(sigma_scaled)
        omega_inv = np.linalg.inv(omega)
        post_cov_inv = np.linalg.inv(tau_sigma_inv + p.T @ omega_inv @ p)
        sigma_bl = sigma + post_cov_inv
    except np.linalg.LinAlgError:
        logging.warning(
            "Inversion failed for posterior covariance. Using original covariance matrix."
        )
        sigma_bl = sigma

    return pd.Series(mu_bl, index=assets), pd.DataFrame(sigma_bl, index=assets, columns=assets)


def compute_efficient_frontier_analytical(
    mu: pd.Series,
    cov: pd.DataFrame,
    rf_rate: float = 0.02,
    n_points: int = 100,
) -> tuple[np.ndarray, np.ndarray, pd.Series, float, float]:
    """
    Computes the analytical unconstrained minimum-variance (efficient) frontier.
    Returns:
    - frontier_vols: Array of volatilities along the frontier
    - frontier_returns: Array of expected returns along the frontier
    - tangency_weights: Weights of the optimal Sharpe ratio (tangency) portfolio
    - tangency_vol: Volatility of the tangency portfolio
    - tangency_return: Expected return of the tangency portfolio
    """
    logging.info("Computing analytical efficient frontier and tangency portfolio...")
    assets = list(mu.index)
    n_assets = len(assets)

    mu_arr = mu.to_numpy()
    sigma = cov.to_numpy()

    # Regularize covariance matrix to ensure invertibility
    reg_val = 1e-6
    sigma_reg = sigma + np.eye(n_assets) * reg_val

    try:
        sigma_inv = np.linalg.inv(sigma_reg)
    except np.linalg.LinAlgError as err:
        logging.error(f"Covariance matrix is singular and cannot be inverted: {err}")
        # Return fallback zero arrays
        return (
            np.zeros(n_points),
            np.zeros(n_points),
            pd.Series(1.0 / n_assets, index=assets),
            0.0,
            0.0,
        )

    ones = np.ones(n_assets)

    # Frontier coefficients
    a = ones @ sigma_inv @ ones
    b = mu_arr @ sigma_inv @ ones
    c = mu_arr @ sigma_inv @ mu_arr
    d = a * c - b**2

    if d <= 0:
        logging.warning(f"Frontier determinant D is non-positive ({d:.6f}). Normalizing D.")
        d = max(d, 1e-6)

    # Minimum and maximum expected returns for plotting
    min_mu = float(mu.min() - 0.05)
    max_mu = float(mu.max() + 0.10)
    frontier_returns = np.linspace(min_mu, max_mu, n_points)

    # Volatilities corresponding to each return level on the hyperbola
    # sigma^2 = (A * mu_p^2 - 2 * B * mu_p + C) / D
    vols_list = []
    for r in frontier_returns:
        var_p = (a * (r**2) - 2 * b * r + c) / d
        var_p = max(var_p, 1e-8)  # prevent negative variance
        vols_list.append(np.sqrt(var_p))

    frontier_vols = np.array(vols_list)

    # Tangency Portfolio weights (Maximum Sharpe Ratio)
    # w_tan = Sigma^-1 * (mu - rf * 1) / (1^T * Sigma^-1 * (mu - rf * 1))
    excess_returns = mu_arr - rf_rate * ones
    weights_numerator = sigma_inv @ excess_returns
    weights_denominator = ones @ weights_numerator

    if abs(weights_denominator) < 1e-8:
        weights_denominator = 1e-8 if weights_denominator >= 0 else -1e-8

    w_tan = weights_numerator / weights_denominator

    # Calculate return and vol of the tangency portfolio
    tangency_return = float(w_tan @ mu_arr)
    tangency_vol = float(np.sqrt(w_tan @ sigma @ w_tan))

    return (
        frontier_vols,
        frontier_returns,
        pd.Series(w_tan, index=assets),
        tangency_vol,
        tangency_return,
    )
