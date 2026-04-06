# tests/test_data_fetch.py

from core.data_fetch import fetch_price


def test_fetch_price_returns_number():
    result = fetch_price(source="dummy")
    assert isinstance(result, (int, float))


def test_fetch_price_is_positive():
    result = fetch_price(source="dummy")
    assert result > 0


def test_fetch_price_returns_expected_dummy_value():
    result = fetch_price(source="dummy")
    assert result == 100.0
