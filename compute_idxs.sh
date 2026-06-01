#!/bin/zsh

source ./.venv/bin/activate

uv run mkt-anlys-cli.py \
--weights "$(cat ./configs/ftse_all_wrld_20_eq_weight.json)" \
--benchmark 'VT' \
--outdir "./results/vt20_eq_weight" \
--period "3mo, 6mo, 1y, 3y, 5y, 10y" \
--idx_name "vt20_eq_weight"

uv run mkt-anlys-cli.py \
--weights "$(cat ./configs/sp20_eq_weight.json)" \
--benchmark 'VOO' \
--outdir "./results/sp20_eq_weight" \
--period "3mo, 6mo, 1y, 3y, 5y, 10y" \
--idx_name "sp20_eq_weight"

uv run mkt-anlys-cli.py \
--weights "$(cat ./configs/ibkr_portfolio.json)" \
--benchmark 'VOO' \
--outdir "./results/ibkr_portfolio_50_50_voo" \
--period "3mo, 6mo, 1y, 3y, 5y, 10y" \
--idx_name "ibkr_portfolio"

uv run mkt-anlys-cli.py \
--weights "$(cat ./configs/ibkr_portfolio.json)" \
--benchmark 'VT' \
--outdir "./results/ibkr_portfolio_vt_eu_ap_27" \
--period "3mo, 6mo, 1y, 3y, 5y, 10y" \
--idx_name "ibkr_portfolio_vt_eu_ap_27"

uv run mkt-anlys-cli.py \
--weights "$(cat ./configs/ibkr_portfolio.json)" \
--benchmark 'VT' \
--outdir "./results/ibkr_portfolio_vt_eu_ap_30" \
--period "3mo, 6mo, 1y, 3y, 5y, 10y" \
--idx_name "ibkr_portfolio_vt_eu_ap_30"

uv run mkt-anlys-cli.py \
--weights "$(cat ./configs/ibkr_portfolio+bnd.json)" \
--benchmark 'VT' \
--outdir "./results/ibkr_portfolio_vt_eu_ap_30_bnd" \
--period "3mo, 6mo, 1y, 3y, 5y, 10y" \
--idx_name "ibkr_portfolio_vt_eu_ap_30_bnd"


uv run mkt-anlys-cli.py \
--weights "$(cat configs/ibkr_portfolio_mkt_cap.json)" \
--benchmark 'VT' \
--outdir "./results/ibkr_mkt_cap" \
--period "6mo, 1y, 3y, 5y, 10y" \
--idx_name "ibkr_mkt_cap"

# ==============================================================================
# PORTFOLIO CONSTRUCTION EXAMPLE (Generate buy list from a JSON list file)
# ==============================================================================
# To compute the exact amount of each stock to buy based on market capitalization
# given a list of tickers in a JSON file and a specific EUR budget (e.g. 3000 EUR):
#
# uv run portfolio-cli.py \
#   --input configs/ibkr_portfolio_list.json \
#   --amount 3000 \
#   --outfile portfolio_res/ibkr_allocation_3k.csv
# ==============================================================================