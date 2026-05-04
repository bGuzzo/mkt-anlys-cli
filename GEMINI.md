# Market Analysis CLI - Project Context

## Project Overview
A Python-based CLI tool designed to perform market analysis and evaluate stock portfolio strategies against historical data. It leverages the `yfinance` library to fetch market data and generates visual charts (PNG) and statistical reports (CSV).

**Key Features (Planned):**
- Portfolio strategy evaluation using custom weights.
- Benchmark comparison (e.g., S&P 500).
- Visual performance charts (one per period).
- Risk and return statistics (yield/dividends, returns, volatility).

## Tech Stack
- **Language:** Python (>= 3.14.0)
- **Dependency Management:** [uv](https://github.com/astral-sh/uv)
- **CLI Framework:** [Typer](https://typer.tiangolo.com/) (enforces type hints and clean CLI design)
- **Data Source:** `yfinance`
- **Data Processing:** `Pandas` / `NumPy` / `pyarrow` (for Parquet support)
- **Visualization:** `Matplotlib`
- **Testing:** `pytest`

## Technical Assumptions
To ensure consistency across the implementation, the following choices have been made:
- **Output Naming Conventions:**
    - Charts: `{idx_name}_{period}.png` (e.g., `my_portfolio_1y.png`)
    - Statistics: `{idx_name}_summary.csv` (Note: This is the ONLY intentional CSV output; all other intermediate data must use Parquet)
- **Testing Strategy:** A `tests/` directory will be established. Logic for annualized returns, volatility, and dividend yield calculations must be covered by unit tests.
- **Data Handling:** All market data will be handled as Pandas DataFrames. Time-series alignment between different tickers will be performed using daily closing prices. **Avoid CSV for internal computations.**
- **Local Caching:** A local cache directory `./yfinance_cache/` must be used to store raw data from `yfinance`.
    - **Cache Key:** Files should be named using the pattern `{ticker}_{period}_{fetch_date}.parquet` (e.g., `AAPL_1y_2024-05-03.parquet`).
    - **Format:** Data MUST be stored as **Parquet** files for performance and type preservation.
    - **Retrieval Logic:** The `yfinance_service.py` must:
        1. Check if a valid cache file exists for the ticker/period/date combination.
        2. If it exists, load the data directly from Parquet into a Pandas DataFrame.
        3. If it does not exist, download the data, save it as Parquet to the cache directory, and then return the DataFrame.

## Getting Started

### Prerequisites
- Python 3.14+
- `uv` installed on your system.

### Installation
```bash
# Sync dependencies
uv sync
```

### Running the CLI
The project is currently in its early development phase. The main entry point is `mkt-anlys-cli.py`.

```bash
uv run mkt-anlys-cli.py
```

## Project Structure
- `mkt-anlys-cli.py`: Primary CLI entry point and argument parser.
- `service/`: Directory for core business logic and modular services.
- `pyproject.toml`: Project configuration and dependencies.
- `README.md`: User-facing documentation and feature roadmap.

## Architectural Principles
- **Loose Coupling:** Services should be independent. If a service needs to communicate with another, it should do so through well-defined interfaces or by being orchestrated from the CLI layer.
- **Single-Source Truth (Stats):** All statistical output should be consolidated into a single, well-structured CSV file that pivots metrics by period for easy comparison.

## Data Validation & Error Handling
To ensure robust analysis, the following validations must be implemented:
- **Weight Integrity:** The `weights` dictionary must be validated to ensure keys are valid tickers and values are numeric. The system should warn or error if weights do not sum to 1.0.
- **Period Validation:** Only the following periods are supported: `3mo, 6mo, 1y, 2y, 5y, 10y`. Any other input should be rejected with a clear error message.
- **Data Availability:** Check if the requested `period` exceeds the historical data available for any ticker in the portfolio. Handle "NaN" or missing data gracefully in calculations.
- **Directory Safety:** Ensure the `outdir` exists or is created safely before writing any files.

## Visualization Standards
Charts produced by the `plotting_service.py` must adhere to these quality standards:
- **Granularity:** Use daily price data to ensure high resolution and accurate trend representation.
- **Details:** Every chart must include:
    - A clear **Title** specifying the index name, benchmark, and period.
    - **Legend** clearly distinguishing the Index from the Benchmark.
    - **Axis Labels** for both time (X-axis) and cumulative returns/price (Y-axis).
    - **Grid lines** for better readability.
- **Output:** Save as high-quality PNG files in the specified `outdir`.

## Development Conventions
- **Modular Services:** Use multiple files within the `service/` directory to separate responsibilities. Create new services as needed to keep files focused:
    - `main_service.py`: (Optional/Recommended) Acts as the primary orchestrator within the service layer, coordinating calls between specialized services.
    - `yfinance_service.py`: Dedicated to fetching and pre-processing data from the `yfinance` API. Responsible for managing the `./yfinance_cache/` to minimize API calls.
    - `plotting_service.py`: Handles the generation of charts and visual representations.
    - `reporting_service.py`: Responsible for calculating statistics and generating CSV reports.
    - *Other services:* Feel free to create additional services (e.g., `validation_service.py`, `config_service.py`) to further decouple logic.
- **Package Structure:** The `service/` directory is a proper Python package with an `__init__.py`.
- **Logging Standards:** Uses a refined, space-separated format (Date/Time, Level, [File:Row], Function, Message) for high traceability without excessive padding.

## Implementation Status
- [x] Implement argument parsing in `mkt-anlys-cli.py` (Typer).
- [x] Implement period validation (`3mo, 6mo, 1y, 2y, 5y, 10y`).
- [x] Implement data fetching service with local Parquet caching.
- [x] Implement high-resolution cumulative performance charts (Matplotlib).
- [x] Implement financial statistics (Return, Volatility, Yield, Correlation).
- [x] Orchestrate via `main_service.py` with verbose audit logging.
- [x] Establish unit testing for financial logic.

