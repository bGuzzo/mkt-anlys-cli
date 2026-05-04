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