import yfinance as yf
import pandas as pd
from pathlib import Path
import datetime
import logging
import json

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
                # Normalize index to timezone-naive dates
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    logging.info(f"Normalizing timezone '{df.index.tz}' for '{ticker}' (cached).")
                df.index = pd.to_datetime(df.index.date)
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
            
        # Normalize index to timezone-naive dates
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            logging.info(f"Normalizing timezone '{df.index.tz}' for '{ticker}' (downloaded).")
        df.index = pd.to_datetime(df.index.date)
        
        logging.info(f"Downloaded {len(df)} rows for '{ticker}'. Saving to cache...")
        df.to_parquet(cache_file)
        return df
    except Exception as e:
        logging.error(f"yfinance download error for '{ticker}': {e}")
        return pd.DataFrame()

def get_ticker_info(ticker: str) -> dict:
    """
    Fetches metadata for a given ticker from yfinance.
    Implements a simple daily cache for metadata.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.date.today().isoformat()
    safe_ticker = ticker.replace("^", "").replace("=", "_")
    cache_file = CACHE_DIR / f"{safe_ticker}_info_{today_str}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Metadata cache read failed for {cache_file}: {e}")

    logging.info(f"Fetching metadata for '{ticker}' from yfinance...")
    try:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info
        with open(cache_file, "w") as f:
            json.dump(info, f)
        return info
    except Exception as e:
        logging.error(f"Error fetching metadata for '{ticker}': {e}")
        return {}

def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """
    Fetches the current exchange rate between two currencies.
    """
    if from_currency == to_currency:
        return 1.0
        
    pair = f"{from_currency}{to_currency}=X"
    logging.info(f"Fetching current exchange rate for '{pair}'...")
    try:
        df = get_market_data(pair, period="1d")
        if not df.empty:
            rate = df['Close'].iloc[-1]
            logging.info(f"Exchange rate for '{pair}': {rate:.4f}")
            return float(rate)
        else:
            logging.error(f"Could not fetch exchange rate for '{pair}'.")
            return 1.0
    except Exception as e:
        logging.error(f"Error fetching exchange rate for '{pair}': {e}")
        return 1.0

def get_historical_exchange_rates(from_currency: str, to_currency: str, period: str) -> pd.Series:
    """
    Fetches the historical exchange rate series between two currencies.
    Returns a pandas Series of the 'Close' prices.
    """
    if from_currency == to_currency:
        return pd.Series()
        
    pair = f"{from_currency}{to_currency}=X"
    logging.info(f"Fetching historical exchange rates for '{pair}' over '{period}'...")
    df = get_market_data(pair, period=period)
    if not df.empty:
        return df['Close']
    else:
        logging.error(f"Could not fetch historical exchange rates for '{pair}'.")
        return pd.Series()

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
