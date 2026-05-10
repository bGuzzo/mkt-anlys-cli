import logging
import pandas as pd
from pathlib import Path
from service.yfinance_service import get_ticker_info, get_exchange_rate

def calculate_market_cap_allocations(
    tickers: list[str], 
    total_euros: float
) -> pd.DataFrame:
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
        mkt_cap = info.get('marketCap')
        currency = info.get('currency', 'USD') # Default to USD if missing
        
        if mkt_cap is None:
            logging.error(f"Could not find market cap for '{ticker}'. Skipping.")
            continue
            
        # Convert to EUR
        rate_to_eur = get_exchange_rate(currency, 'EUR')
        mkt_cap_eur = mkt_cap * rate_to_eur
        
        data.append({
            'Ticker': ticker,
            'MarketCap_Orig': mkt_cap,
            'Currency': currency,
            'MarketCap_EUR': mkt_cap_eur
        })
        total_market_cap_eur += mkt_cap_eur
        
    if total_market_cap_eur == 0:
        raise ValueError("Total market cap is zero. Cannot calculate allocations.")
        
    # 2. Get EUR/USD rate for the output column
    eur_usd_rate = get_exchange_rate('EUR', 'USD')
    
    # 3. Calculate weights and allocations
    results = []
    for item in data:
        weight = item['MarketCap_EUR'] / total_market_cap_eur
        allocation_eur = total_euros * weight
        allocation_usd = allocation_eur * eur_usd_rate
        
        results.append({
            'Ticker': item['Ticker'],
            'Euros to Allocate': round(allocation_eur, 2),
            'Dollars to Allocate': round(allocation_usd, 2),
            'Percentage': f"{weight:.2%}"
        })
        
    # Sort results by Ticker name alphabetically
    results.sort(key=lambda x: x['Ticker'])
        
    df = pd.DataFrame(results)
    logging.info(f"Allocation calculation complete for {len(results)} tickers.")
    return df

def generate_allocation_csv(df: pd.DataFrame, outfile: Path):
    """
    Saves the allocation dataframe to a CSV file.
    """
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(outfile, index=False)
    logging.info(f"Successfully saved allocation report to: {outfile}")
