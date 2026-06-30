import logging
from typing import TYPE_CHECKING, Any

import pandas as pd

from service.yfinance_service import get_exchange_rate, get_ticker_info

if TYPE_CHECKING:
    from pathlib import Path


def calculate_market_cap_allocations(tickers: list[str], total_euros: float) -> pd.DataFrame:
    """
    Calculates the allocation for each ticker based on its market capitalization.
    Normalizes market caps to EUR before calculating weights.
    """
    logging.info(f"Calculating market-cap weighted allocations for {len(tickers)} tickers...")

    data = []
    total_market_cap_eur = 0.0

    # 1. Fetch market caps and normalize to EUR
    for ticker in tickers:
        info = get_ticker_info(ticker)
        mkt_cap = info.get("marketCap")
        currency = info.get("currency", "USD")  # Default to USD if missing

        if mkt_cap is None:
            logging.error(f"Could not find market cap for '{ticker}'. Skipping.")
            continue

        # Convert to EUR
        rate_to_eur = get_exchange_rate(currency, "EUR")
        mkt_cap_eur = mkt_cap * rate_to_eur

        data.append(
            {
                "Ticker": ticker,
                "MarketCap_Orig": mkt_cap,
                "Currency": currency,
                "MarketCap_EUR": mkt_cap_eur,
            }
        )
        total_market_cap_eur += mkt_cap_eur

    if total_market_cap_eur == 0:
        raise ValueError("Total market cap is zero. Cannot calculate allocations.")

    # 2. Get EUR/USD rate for the output column
    eur_usd_rate = get_exchange_rate("EUR", "USD")

    # 3. Calculate weights and allocations
    results = []
    for item in data:
        weight = item["MarketCap_EUR"] / total_market_cap_eur
        allocation_eur = total_euros * weight
        allocation_usd = allocation_eur * eur_usd_rate

        results.append(
            {
                "Ticker": item["Ticker"],
                "Euros to Allocate": round(allocation_eur, 2),
                "Dollars to Allocate": round(allocation_usd, 2),
                "Percentage": f"{weight:.2%}",
            }
        )

    # Sort results by Ticker name alphabetically
    results.sort(key=lambda x: x["Ticker"])

    df = pd.DataFrame(results)
    logging.info(f"Allocation calculation complete for {len(results)} tickers.")
    return df


def generate_allocation_csv(df: pd.DataFrame, outfile: Path) -> None:
    """
    Saves the allocation dataframe to a CSV file.
    """
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(outfile, index=False)
    logging.info(f"Successfully saved allocation report to: {outfile}")


def calculate_portfolio_allocation(
    weights: dict[str, float], total_euros: float
) -> dict[str, Any]:
    """
    Calculates detailed cash allocations in EUR and target local currency
    for a dictionary of weights and total euros.
    """
    logging.info(f"Distributing {total_euros} EUR across optimized portfolio weights...")

    constituents = {}
    for ticker, weight in weights.items():
        info = get_ticker_info(ticker)
        currency = info.get("currency", "USD")

        # Calculate Euro allocation
        eur_amount = total_euros * weight

        # Convert Euro amount to target/local currency using yfinance exchange rates
        rate_to_local = get_exchange_rate("EUR", currency)
        local_amount = eur_amount * rate_to_local

        constituents[ticker] = {
            "weight": float(weight),
            "eur_amount": float(round(eur_amount, 2)),
            "local_currency": currency,
            "local_amount": float(round(local_amount, 2)),
        }

    return {
        "total_investment_eur": float(total_euros),
        "constituents": constituents,
    }


def calculate_portfolio_allocation_usd(
    weights: dict[str, float], total_usd: float
) -> dict[str, Any]:
    """
    Calculates detailed cash allocations in USD and target local currency
    for a dictionary of weights and total USD.
    """
    logging.info(f"Distributing {total_usd} USD across optimized portfolio weights...")

    constituents = {}
    for ticker, weight in weights.items():
        info = get_ticker_info(ticker)
        currency = info.get("currency", "USD")

        # Calculate USD allocation
        usd_amount = total_usd * weight

        # Convert USD amount to target/local currency using yfinance exchange rates
        rate_to_local = get_exchange_rate("USD", currency)
        local_amount = usd_amount * rate_to_local

        constituents[ticker] = {
            "weight": float(weight),
            "usd_amount": float(round(usd_amount, 2)),
            "local_currency": currency,
            "local_amount": float(round(local_amount, 2)),
        }

    return {
        "total_investment_usd": float(total_usd),
        "constituents": constituents,
    }

