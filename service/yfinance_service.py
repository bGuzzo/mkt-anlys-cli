import yfinance as yf
import pandas as pd
from pathlib import Path
import datetime
import logging

CACHE_DIR = Path("./yfinance_cache")

def get_market_data(ticker: str, period: str) -> pd.DataFrame:
    """
    Fetches market data (historical prices and dividends) for a given ticker and period.
    Implements a local Parquet cache to avoid redundant API calls on the same day.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.date.today().isoformat()
    safe_ticker = ticker.replace("^", "").replace("=", "_")
    cache_file = CACHE_DIR / f"{safe_ticker}_{period}_{today_str}.parquet"
    
    if cache_file.exists():
        logging.info(f"Cache hit: Loading '{ticker}' for period '{period}' from {cache_file.name}")
        try:
            df = pd.read_parquet(cache_file)
            if not df.empty:
                logging.info(f"Successfully loaded {len(df)} rows for '{ticker}' from cache.")
                return df
        except Exception as e:
            logging.warning(f"Cache read failed for {cache_file}: {e}. Falling back to download.")
            
    logging.info(f"Cache miss: Downloading '{ticker}' for period '{period}' from yfinance...")
    try:
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(period=period)
        
        if df.empty:
            logging.error(f"No data returned from yfinance for '{ticker}' ({period}).")
            return pd.DataFrame()
            
        logging.info(f"Downloaded {len(df)} rows for '{ticker}'. Saving to cache...")
        df.to_parquet(cache_file)
        return df
    except Exception as e:
        logging.error(f"yfinance download error for '{ticker}': {e}")
        return pd.DataFrame()

def align_and_combine_data(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    """
    Fetches data for multiple tickers and returns a dictionary of dataframes.
    """
    logging.info(f"Synchronizing data for {len(tickers)} tickers over '{period}'...")
    data = {}
    for ticker in tickers:
        df = get_market_data(ticker, period)
        if df.empty:
             logging.error(f"Critical error: Ticker '{ticker}' has no data. Aborting synchronization.")
             raise ValueError(f"Could not fetch sufficient data for ticker {ticker} for period {period}.")
        data[ticker] = df
    logging.info("All tickers synchronized successfully.")
    return data
