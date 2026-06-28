from unittest.mock import patch

import pytest

from service.portfolio_service import calculate_portfolio_allocation


@pytest.mark.unit
def test_calculate_portfolio_allocation() -> None:
    weights = {"AAPL": 0.6, "MSFT": 0.4}
    total_euros = 10000.0

    with (
        patch("service.portfolio_service.get_ticker_info") as mock_info,
        patch("service.portfolio_service.get_exchange_rate") as mock_rate,
    ):
        def side_effect_info(ticker: str) -> dict[str, str]:
            if ticker == "AAPL":
                return {"currency": "USD"}
            elif ticker == "MSFT":
                return {"currency": "EUR"}
            return {}

        mock_info.side_effect = side_effect_info

        def side_effect_rate(source: str, target: str) -> float:
            if source == "EUR" and target == "USD":
                return 1.10
            if source == "EUR" and target == "EUR":
                return 1.0
            return 1.0

        mock_rate.side_effect = side_effect_rate

        allocation = calculate_portfolio_allocation(weights, total_euros)

        assert allocation["total_investment_eur"] == 10000.0
        assert "AAPL" in allocation["constituents"]
        assert "MSFT" in allocation["constituents"]

        # AAPL: 10000 * 0.6 = 6000 EUR
        # Converted to USD: 6000 * 1.10 = 6600.0 USD
        assert allocation["constituents"]["AAPL"]["weight"] == 0.6
        assert allocation["constituents"]["AAPL"]["eur_amount"] == 6000.0
        assert allocation["constituents"]["AAPL"]["local_currency"] == "USD"
        assert allocation["constituents"]["AAPL"]["local_amount"] == 6600.0

        # MSFT: 10000 * 0.4 = 4000 EUR
        # Converted to EUR: 4000 * 1.0 = 4000.0 EUR
        assert allocation["constituents"]["MSFT"]["weight"] == 0.4
        assert allocation["constituents"]["MSFT"]["eur_amount"] == 4000.0
        assert allocation["constituents"]["MSFT"]["local_currency"] == "EUR"
        assert allocation["constituents"]["MSFT"]["local_amount"] == 4000.0
