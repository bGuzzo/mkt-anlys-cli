import typer
import json
import logging
from typing import List
from pathlib import Path

# Setup refined logging format (no tabulation/heavy padding)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s [%(filename)s:%(lineno)d] %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = typer.Typer(help="Market Analysis CLI tool for portfolio strategy evaluation.")

VALID_PERIODS = {"3mo", "6mo", "1y", "2y", "3y", "5y", "10y"}

def validate_weights(weights_str: str) -> dict[str, float]:
    """Parses and validates the weights input."""
    try:
        weights = json.loads(weights_str)
    except json.JSONDecodeError:
        raise typer.BadParameter("Weights must be a valid JSON string, e.g. '{\"AAPL\": 0.4, \"MSFT\": 0.6}'")
    
    if not isinstance(weights, dict):
        raise typer.BadParameter("Weights must be a dictionary.")
        
    total_weight = 0.0
    for ticker, weight in weights.items():
        if not isinstance(ticker, str):
            raise typer.BadParameter(f"Ticker '{ticker}' must be a string.")
        if not isinstance(weight, (int, float)):
            raise typer.BadParameter(f"Weight for '{ticker}' must be a number.")
        total_weight += weight
        
    if not (0.99 <= total_weight <= 1.01): # Allow minor floating point inaccuracies
        raise typer.BadParameter(f"Weights must sum to 1.0. Current sum: {total_weight}")
        
    return weights

def validate_periods(periods_str: str) -> List[str]:
    """Parses and validates the periods input."""
    periods = [p.strip() for p in periods_str.split(",")]
    invalid_periods = [p for p in periods if p not in VALID_PERIODS]
    if invalid_periods:
        raise typer.BadParameter(f"Invalid periods: {', '.join(invalid_periods)}. Supported periods: {', '.join(VALID_PERIODS)}")
    return periods

def validate_idx_name(idx_name: str) -> str:
    """Validates the index name."""
    if " " in idx_name:
        raise typer.BadParameter("Index name must not contain spaces.")
    return idx_name

@app.command()
def main(
    weights: str = typer.Option(..., "--weights", help="A dict which maps a ticker (yfinance) to a weight (0 to 1). Example: '{\"AAPL\": 0.4, \"MSFT\": 0.4, \"AMZN\": 0.2}'"),
    benchmark: str = typer.Option(..., "--benchmark", help="A ticker (yfinance) used as reference in the plots and statistics. Example: '^GSPC'"),
    outdir: Path = typer.Option(..., "--outdir", help="The target directory to store the output computations (charts + CSV stats)."),
    period: str = typer.Option(..., "--period", help="The timeframe for which you want to evaluate your strategy. Example: '1y, 5y'. Supported: 3mo, 6mo, 1y, 2y, 5y, 10y"),
    idx_name: str = typer.Option(..., "--idx_name", help="The name of your index (should not contain spaces). Example: 'my_index'")
):
    """
    Evaluate your stock portfolio strategy against historical data.
    """
    parsed_weights = validate_weights(weights)
    parsed_periods = validate_periods(period)
    parsed_idx_name = validate_idx_name(idx_name)
    
    # Ensure outdir exists
    outdir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Starting analysis for '{parsed_idx_name}'")
    logging.info(f"Weights: {parsed_weights}")
    logging.info(f"Benchmark: {benchmark}")
    logging.info(f"Periods: {parsed_periods}")
    logging.info(f"Output Directory: {outdir}")

    # Here we will call the main_service orchestrator
    from service.main_service import run_analysis
    run_analysis(
        weights=parsed_weights,
        benchmark=benchmark,
        outdir=outdir,
        periods=parsed_periods,
        idx_name=parsed_idx_name
    )

if __name__ == "__main__":
    app()