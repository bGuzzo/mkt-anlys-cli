"""
Black-Litterman and portfolio optimization pipeline services.
Implements market weight construction, covariance scaling, implied equilibrium returns,
zero-views Black-Litterman state, and efficient frontier/tangency portfolio quadratic optimization.
"""

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.optimize import minimize

from service.yfinance_service import get_exchange_rate, get_market_data, get_ticker_info

if TYPE_CHECKING:
    import pandas as pd

# Strict Tau parameter definition
TAU: float = 1.0 / 30.0


def parse_horizon(horizon_str: str) -> int:
    """
    Parses investment horizon string into number of trading days.
    e.g. '2mo' -> 42 days, '40' -> 40 days.
    """
    horizon_str = horizon_str.strip().lower()
    if horizon_str.endswith("mo"):
        try:
            months = int(horizon_str[:-2])
            return months * 21
        except ValueError as err:
            raise ValueError(f"Invalid horizon format: {horizon_str}") from err
    else:
        try:
            return int(horizon_str)
        except ValueError as err:
            raise ValueError(f"Invalid horizon format: {horizon_str}") from err


def get_risk_free_rate(rf_param: str) -> float:
    """
    Returns the annualized risk-free rate (as a decimal).
    """
    try:
        return float(rf_param)
    except ValueError:
        pass

    # Try fetching as a yfinance ticker if it is not numeric
    logging.info(f"Fetching risk-free rate from ticker '{rf_param}'...")
    df = get_market_data(rf_param, period="1mo")
    if df.empty:
        raise ValueError(f"Could not fetch yield for risk-free asset '{rf_param}'")
    latest_yield_percent = float(df["Close"].iloc[-1])
    # Treasury yields from yfinance are in percentage points (e.g., 4.5 means 4.5%)
    r_f = latest_yield_percent / 100.0
    logging.info(f"Retrieved rate from '{rf_param}': {r_f:.6f} ({latest_yield_percent:.4f}%)")
    return r_f


def construct_market_weights_dict(tickers: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """
    Constructs market weights from market cap info.
    Normalizes market caps to EUR.
    Returns:
    - Dict of normalized market weights.
    - Dict of raw market caps in EUR.
    """
    logging.info("Constructing market weights from market caps in EUR...")
    market_caps_eur: dict[str, float] = {}
    total_mkt_cap_eur = 0.0

    for ticker in tickers:
        info = get_ticker_info(ticker)
        mkt_cap = info.get("marketCap")
        currency = info.get("currency", "USD")

        if mkt_cap is None:
            logging.warning(f"No market cap for '{ticker}'. Defaulting to equal weight proxy.")
            continue

        rate_to_eur = get_exchange_rate(currency, "EUR")
        mkt_cap_eur = float(mkt_cap) * rate_to_eur
        market_caps_eur[ticker] = mkt_cap_eur
        total_mkt_cap_eur += mkt_cap_eur

    # Handle missing tickers
    missing_tickers = [t for ticker in tickers if (t := ticker) not in market_caps_eur]
    if missing_tickers:
        avg_cap = total_mkt_cap_eur / len(market_caps_eur) if market_caps_eur else 1.0e11
        for ticker in missing_tickers:
            market_caps_eur[ticker] = avg_cap
            total_mkt_cap_eur += avg_cap

    weights: dict[str, float] = {}
    if total_mkt_cap_eur > 0:
        for ticker in tickers:
            weights[ticker] = market_caps_eur[ticker] / total_mkt_cap_eur
    else:
        for ticker in tickers:
            weights[ticker] = 1.0 / len(tickers)

    return weights, market_caps_eur


def construct_market_weights(tickers: list[str]) -> np.ndarray:
    """
    Constructs market weights from market cap info and returns a 1D NumPy array.
    """
    weights_dict, _ = construct_market_weights_dict(tickers)
    return np.array([weights_dict[t] for t in tickers], dtype=float)


def compute_scaled_covariance(returns_df: pd.DataFrame, horizon_days: int) -> np.ndarray:
    """
    Computes scaled covariance matrix: Sigma_horizon = Sigma_daily * Horizon_Days.
    Ensures NaN and infinite values are handled gracefully.
    """
    if returns_df.empty:
        raise ValueError("Returns DataFrame is empty.")

    clean_df = returns_df.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    cov_daily = clean_df.cov().to_numpy()
    return np.asarray(cov_daily * float(horizon_days), dtype=float)


def compute_implied_excess_returns(
    lambda_coefficient: float, sigma_horizon: np.ndarray, w_mkt: np.ndarray
) -> np.ndarray:
    """
    Computes implied equilibrium excess returns:
    Pi_horizon = lambda_coefficient * Sigma_horizon * w_mkt.
    """
    if sigma_horizon.ndim != 2 or sigma_horizon.shape[0] != sigma_horizon.shape[1]:
        raise ValueError("sigma_horizon must be a square 2D matrix.")
    if w_mkt.ndim != 1 or w_mkt.shape[0] != sigma_horizon.shape[0]:
        raise ValueError("w_mkt must be a 1D array aligned with sigma_horizon dimensions.")

    return np.asarray(lambda_coefficient * (sigma_horizon @ w_mkt), dtype=float)


def get_zero_views_black_litterman(
    pi_horizon: np.ndarray, sigma_horizon: np.ndarray, tau: float = TAU
) -> tuple[np.ndarray, np.ndarray]:
    """
    In zero-views state, expected returns = Pi_horizon,
    adjusted covariance = (1 + tau) * Sigma_horizon.
    """
    if pi_horizon.ndim != 1:
        raise ValueError("pi_horizon must be a 1D array.")
    if sigma_horizon.ndim != 2 or sigma_horizon.shape[0] != sigma_horizon.shape[1]:
        raise ValueError("sigma_horizon must be a square 2D matrix.")
    if pi_horizon.shape[0] != sigma_horizon.shape[0]:
        raise ValueError("Dimensions of pi_horizon and sigma_horizon must match.")

    expected_returns = pi_horizon.copy()
    adjusted_covariance = (1.0 + tau) * sigma_horizon
    return expected_returns, adjusted_covariance


def portfolio_variance(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    """
    Calculates portfolio variance.
    """
    return float(np.dot(weights.T, np.dot(cov_matrix, weights)))


def negative_sharpe_ratio(
    weights: np.ndarray, expected_returns: np.ndarray, cov_matrix: np.ndarray, rf_rate: float
) -> float:
    """
    Calculates negative Sharpe ratio for minimization.
    """
    port_return = np.dot(weights, expected_returns)
    port_var = portfolio_variance(weights, cov_matrix)
    port_vol = np.sqrt(port_var) if port_var > 0 else 1e-8
    return -float((port_return - rf_rate) / port_vol)


def portfolio_return_constraint(
    weights: np.ndarray, expected_returns: np.ndarray, target_return: float
) -> float:
    """
    Constraint function for target return.
    """
    return float(np.dot(weights, expected_returns) - target_return)


def sum_to_one_constraint(w: np.ndarray) -> float:
    """
    Constraint enforcing that the sum of portfolio weights equals 1.0.
    """
    return float(np.sum(w) - 1.0)


def optimize_tangency_portfolio(
    expected_returns: np.ndarray, cov_matrix: np.ndarray, rf_rate: float
) -> np.ndarray:
    """
    Finds the maximum Sharpe Ratio (tangency) portfolio under long-only constraints.
    """
    n_assets = len(expected_returns)
    init_weights = np.ones(n_assets) / n_assets
    bounds = tuple((0.0, 1.0) for _ in range(n_assets))
    constraints = {"type": "eq", "fun": sum_to_one_constraint}

    res = minimize(
        negative_sharpe_ratio,
        init_weights,
        args=(expected_returns, cov_matrix, rf_rate),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )

    if not res.success:
        logging.warning(
            f"Tangency optimization did not converge: {res.message}. Using initial weights."
        )
        return init_weights
    return np.asarray(res.x)


def optimize_frontier_point(
    expected_returns: np.ndarray, cov_matrix: np.ndarray, target_return: float
) -> np.ndarray:
    """
    Finds the minimum variance portfolio weights for a target return under long-only constraints.
    """
    n_assets = len(expected_returns)
    init_weights = np.ones(n_assets) / n_assets
    bounds = tuple((0.0, 1.0) for _ in range(n_assets))
    constraints = [
        {"type": "eq", "fun": sum_to_one_constraint},
        {
            "type": "eq",
            "fun": portfolio_return_constraint,
            "args": (expected_returns, target_return),
        },
    ]

    res = minimize(
        portfolio_variance,
        init_weights,
        args=(cov_matrix,),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )

    if not res.success:
        return init_weights
    return np.asarray(res.x)


def compute_efficient_frontier_long_only(
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n_points: int = 50,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """
    Computes the long-only efficient frontier.
    Returns:
    - frontier_vols: Array of volatilities along the frontier
    - frontier_returns: Array of expected returns along the frontier
    - frontier_weights: List of weight arrays for each point
    """
    min_ret = float(np.min(expected_returns))
    max_ret = float(np.max(expected_returns))

    target_returns = np.linspace(min_ret, max_ret, n_points)

    vols = []
    rets = []
    weights_list = []

    for r_target in target_returns:
        w = optimize_frontier_point(expected_returns, cov_matrix, r_target)
        p_var = portfolio_variance(w, cov_matrix)
        vols.append(np.sqrt(p_var))
        rets.append(r_target)
        weights_list.append(w)

    return np.array(vols), np.array(rets), weights_list


def run_black_litterman_optimization(
    tickers: list[str],
    prices_df: pd.DataFrame,
    horizon_days: int,
    rf_annual: float,
    lambda_coeff: float = 3.0,
    tau: float = TAU,
) -> dict[str, Any]:
    """
    Orchestrates the Black-Litterman optimization under zero-views (equilibrium state).
    All calculations are normalized to EUR.
    """
    valid_tickers = [t for t in tickers if t in prices_df.columns]
    if len(valid_tickers) < len(tickers):
        missing = set(tickers) - set(valid_tickers)
        logging.warning(f"Some tickers are missing from price data: {missing}")

    prices_df_clean = prices_df[valid_tickers].dropna()
    if prices_df_clean.empty:
        raise ValueError("Prices DataFrame is empty after dropping NaNs.")

    mkt_weights_dict, mkt_caps_eur = construct_market_weights_dict(valid_tickers)
    w_mkt = np.array([mkt_weights_dict[t] for t in valid_tickers])

    daily_returns = prices_df_clean.pct_change().dropna()
    sigma_daily = daily_returns.cov().to_numpy()

    sigma_horizon = sigma_daily * horizon_days
    rf_horizon = rf_annual * (horizon_days / 360.0)

    pi_horizon = lambda_coeff * (sigma_horizon @ w_mkt)

    expected_returns_horizon = pi_horizon + rf_horizon
    sigma_adjusted = (1.0 + tau) * sigma_horizon

    w_tangency = optimize_tangency_portfolio(
        expected_returns=expected_returns_horizon,
        cov_matrix=sigma_adjusted,
        rf_rate=rf_horizon,
    )

    tangency_return = float(np.dot(w_tangency, expected_returns_horizon))
    tangency_vol = float(np.sqrt(portfolio_variance(w_tangency, sigma_adjusted)))

    vols, rets, weights_list = compute_efficient_frontier_long_only(
        expected_returns=expected_returns_horizon,
        cov_matrix=sigma_adjusted,
        n_points=30,
    )

    results = {
        "tickers": valid_tickers,
        "horizon_days": horizon_days,
        "rf_annual": rf_annual,
        "rf_horizon": rf_horizon,
        "lambda": lambda_coeff,
        "tau": tau,
        "market_caps_eur": mkt_caps_eur,
        "market_weights": {t: float(mkt_weights_dict[t]) for t in valid_tickers},
        "equilibrium_excess_returns": {
            t: float(pi_horizon[i]) for i, t in enumerate(valid_tickers)
        },
        "expected_total_returns": {
            t: float(expected_returns_horizon[i]) for i, t in enumerate(valid_tickers)
        },
        "posterior_covariance": {
            t1: {t2: float(sigma_adjusted[i][j]) for j, t2 in enumerate(valid_tickers)}
            for i, t1 in enumerate(valid_tickers)
        },
        "tangency_portfolio": {
            "weights": {t: float(w_tangency[i]) for i, t in enumerate(valid_tickers)},
            "expected_return": tangency_return,
            "volatility": tangency_vol,
            "sharpe_ratio": (
                (tangency_return - rf_horizon) / tangency_vol if tangency_vol > 0 else 0.0
            ),
        },
        "efficient_frontier": [
            {
                "volatility": float(vols[i]),
                "expected_return": float(rets[i]),
                "weights": {t: float(weights_list[i][j]) for j, t in enumerate(valid_tickers)},
            }
            for i in range(len(vols))
        ],
    }

    return results


def optimize_max_sharpe_ratio(
    expected_returns: np.ndarray, cov_matrix: np.ndarray, rf_rate: float
) -> dict[str, Any]:
    """
    Finds the maximum Sharpe Ratio (tangency) portfolio. Wrapper for unit tests.
    """
    w = optimize_tangency_portfolio(expected_returns, cov_matrix, rf_rate)
    return {
        "success": True,
        "weights": w,
        "return": float(np.dot(w, expected_returns)),
        "volatility": float(np.sqrt(portfolio_variance(w, cov_matrix))),
    }


def optimize_portfolio_for_target_return(
    expected_returns: np.ndarray, cov_matrix: np.ndarray, target_return: float
) -> dict[str, Any]:
    """
    Finds the minimum variance portfolio weights for a target return. Wrapper for unit tests.
    """
    w = optimize_frontier_point(expected_returns, cov_matrix, target_return)
    return {
        "success": True,
        "weights": w,
        "return": target_return,
        "volatility": float(np.sqrt(portfolio_variance(w, cov_matrix))),
    }


def compute_efficient_frontier(
    expected_returns: np.ndarray, cov_matrix: np.ndarray, num_points: int = 10
) -> list[dict[str, Any]]:
    """
    Computes the long-only efficient frontier. Wrapper for unit tests.
    """
    vols, rets, weights_list = compute_efficient_frontier_long_only(
        expected_returns, cov_matrix, num_points
    )
    return [
        {
            "weights": weights_list[i],
            "return": rets[i],
            "volatility": vols[i],
        }
        for i in range(len(vols))
    ]
