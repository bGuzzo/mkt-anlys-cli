import typer
import json
import logging
from pathlib import Path
from service.portfolio_service import calculate_market_cap_allocations, generate_allocation_csv

# Setup refined logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s [%(filename)s:%(lineno)d] %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = typer.Typer(help="Portfolio Construction CLI for market-cap weighted allocations.")

def validate_input_file(input_file: Path) -> list[str]:
    """Validates the input JSON file."""
    if not input_file.exists():
        raise typer.BadParameter(f"Input file '{input_file}' does not exist.")
    try:
        with open(input_file, 'r') as f:
            tickers = json.load(f)
    except json.JSONDecodeError:
        raise typer.BadParameter(f"Input file '{input_file}' must be a valid JSON.")
        
    if not isinstance(tickers, list):
        raise typer.BadParameter("Input file must contain a list of tickers.")
        
    for ticker in tickers:
        if not isinstance(ticker, str):
            raise typer.BadParameter(f"Ticker '{ticker}' must be a string.")
            
    return tickers

@app.command()
def main(
    input_file: Path = typer.Option(..., "--input", help="Path to a JSON file containing a list of yfinance tickers."),
    amount: float = typer.Option(..., "--amount", help="Total amount in Euros to invest."),
    outfile: Path = typer.Option(..., "--outfile", help="Path to the output CSV file.")
):
    """
    Compute market-cap weighted allocations for a list of stocks.
    
    Example:
    uv run portfolio-cli.py --input configs/ibkr_portfolio_list.json --amount 3000 --outfile portfolio_res/ibkr_allocation_3k.csv
    """
    logging.info(f"Starting portfolio allocation for {amount} EUR")
    
    # 1. Validate Input
    try:
        tickers = validate_input_file(input_file)
    except Exception as e:
        logging.error(f"Validation failed: {e}")
        raise typer.Exit(code=1)
        
    # 2. Perform Calculations
    try:
        df_allocations = calculate_market_cap_allocations(tickers, amount)
    except Exception as e:
        logging.error(f"Allocation calculation failed: {e}")
        raise typer.Exit(code=1)
        
    # 3. Save Output
    try:
        generate_allocation_csv(df_allocations, outfile)
    except Exception as e:
        logging.error(f"Failed to save output: {e}")
        raise typer.Exit(code=1)

    logging.info("Portfolio allocation completed successfully.")

if __name__ == "__main__":
    app()
