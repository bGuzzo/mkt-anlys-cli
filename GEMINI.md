# Market Analysis CLI - Project Context

## Project Overview
A Python-based CLI toolset designed to perform market analysis and evaluate stock portfolio strategies.

**Key Tools:**
- **mkt-anlys-cli.py:** Evaluates portfolio strategy performance (returns, volatility, yield) against historical benchmarks using custom weights.
- **portfolio-cli.py:** Assists in portfolio construction by calculating market-cap weighted allocations (similar to the S&P 500) for a list of tickers, normalizing all values to Euros.

## Tech Stack
- **Language:** Python (>= 3.14.0)
- **Dependency Management:** [uv](https://github.com/astral-sh/uv)
- **CLI Framework:** [Typer](https://typer.tiangolo.com/)
- **Data Source:** `yfinance`
- **Data Processing:** `Pandas` / `NumPy` / `pyarrow`
- **Visualization:** `Matplotlib`
- **Testing:** `pytest`

## Architectural Principles & SOLID Guidelines

To ensure long-term maintainability and scalability, the following principles MUST be followed:

### 1. SOLID Principles
- **Single Responsibility (SRP):** Each service class or module must have one, and only one, reason to change. (e.g., `yfinance_service` only handles data retrieval, not calculation).
- **Open/Closed:** Services should be open for extension but closed for modification. Use composition over inheritance.
- **Liskov Substitution:** Derived types must be completely substitutable for their base types.
- **Interface Segregation:** Prefer many client-specific interfaces over one general-purpose interface.
- **Dependency Inversion:** Depend on abstractions, not concretions. Orchestration layers (like `main_service`) should drive the high-level logic while implementation details are hidden in specialized services.

### 2. Loose Coupling & Modular Design
- **Service Isolation:** Services must not have deep internal dependencies on each other's state. Communication should happen through clear function signatures and data structures (DataFrames/Series).
- **Orchestration Layer:** Use "Main" services or the CLI layer to coordinate multiple specialized services. Avoid "spaghetti" calls where services invoke each other in a circular or deep chain.
- **No Nested Functions:** Do NOT use nested function declarations. All functions must be defined at the module level to ensure they are accessible for unit testing and maintain a flat, readable structure.

### 3. Fault Tolerance & Robustness
- **Graceful Degradation:** If a ticker fails to fetch or a market cap is missing, the system should log a clear error and continue processing the remaining constituents whenever possible.
- **Data Validation:** Validate all external inputs (JSON, CSV, CLI arguments) early. Use Typer's validation hooks for CLI arguments.
- **NaN Handling:** Financial calculations must explicitly handle `NaN` or infinite values resulting from pct_change or division by zero, preventing crashes during report generation.

## Technical Assumptions
- **Output Naming Conventions:**
    - Charts: `{idx_name}_{period}.png`
    - Statistics: `{idx_name}_summary.csv`
    - Portfolio Allocation: Custom path provided via `--outfile`.
- **Data Handling:** All market data handled as Pandas DataFrames. Parquet is the preferred format for caching.
- **Local Caching:** `./yfinance_cache/` stores raw data.
    - **Cache Key:** `{ticker}_{period}_{fetch_date}.parquet`.
- **Currency Normalization (Unified EUR Perspective):** 
    - Both `mkt-anlys-cli.py` and `portfolio-cli.py` normalize ALL data to **EUR**.
    - For performance analysis, historical prices and dividends are converted using daily historical exchange rates (e.g., `USDEUR=X`) before calculating returns and metrics.
    - For portfolio construction, market caps are converted to EUR using current rates.
    - This ensures a consistent EUR-based perspective for all financial metrics (CAGR, Volatility, Yield, Allocations), regardless of the asset's original trading currency (USD, KRW, JPY, etc.).

## Implementation Status
- [x] Implement argument parsing in `mkt-anlys-cli.py` (Typer).
- [x] Implement period validation (`3mo, 6mo, 1y, 2y, 5y, 10y`).
- [x] Implement data fetching service with local Parquet caching.
- [x] Implement high-resolution cumulative performance charts (Matplotlib).
- [x] Implement financial statistics (Return, Volatility, Yield, Correlation).
- [x] Orchestrate via `main_service.py` with verbose audit logging.
- [x] Implement `portfolio-cli.py` for market-cap weighted allocations.
- [x] Implement currency-aware market cap normalization and exchange rate fetching.
- [x] **New:** Implement currency-aware historical normalization for performance evaluation in `mkt-anlys-cli.py`.
- [x] Establish unit testing for financial logic.

## Development Conventions
- **Modular Services:**
    - `main_service.py`: Orchestrates performance analysis.
    - `yfinance_service.py`: Handles all API interactions and caching. Now includes metadata and historical exchange rate fetching.
    - `portfolio_service.py`: Dedicated logic for portfolio construction.
    - `plotting_service.py`: Chart generation.
    - `reporting_service.py`: Stats calculation and CSV report generation.
- **Logging Standards:** Verbose, space-separated format (Date/Time, Level, [File:Row], Function, Message) is mandatory. Every significant branch, API call, and calculation milestone must be logged.
- **Testing:** New logic must be accompanied by tests in the `tests/` directory.

## Getting Started

### Prerequisites
- Python 3.14+
- `uv` installed on your system.

### Installation
```bash
# Sync dependencies
uv sync
```

### Running the CLIs
```bash
# Performance Analysis
uv run mkt-anlys-cli.py --weights '{"AAPL": 0.5, "MSFT": 0.5}' --benchmark '^GSPC' --outdir "./results" --period "1y" --idx_name "my_idx"

# Portfolio Construction
uv run portfolio-cli.py --input tickers.json --amount 10000 --outfile allocation.csv
```
