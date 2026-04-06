# data_fetch.py - Price Data Module

import requests
import config


def fetch_price(
    symbol: str = config.SYMBOL,
    source: str = config.DATA_SOURCE,
) -> float:
    """
    Fetch the current asset price from a real or mock data source.

    Args:
        symbol: Asset identifier. CoinGecko: "bitcoin"; Binance: "BTCUSDT".
        source: One of "coingecko", "binance", or "dummy".

    Returns:
        Current price as a float.

    Raises:
        ValueError: If source is unsupported or response is malformed.
        requests.RequestException: On network failure.
    """
    if source == "dummy":
        return config.DUMMY_PRICE

    if source == "coingecko":
        return _fetch_coingecko(symbol)

    if source == "binance":
        return _fetch_binance(symbol)

    raise ValueError(f"Unsupported data source: {source}")


def _fetch_coingecko(symbol: str) -> float:
    """Fetch price from CoinGecko simple/price endpoint (no auth required)."""
    params = {"ids": symbol, "vs_currencies": "usd"}
    response = requests.get(config.COINGECKO_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    if symbol not in data:
        raise ValueError(f"Symbol '{symbol}' not found in CoinGecko response.")
    return float(data[symbol]["usd"])


def _fetch_binance(symbol: str) -> float:
    """Fetch price from Binance ticker endpoint (no auth required)."""
    params = {"symbol": symbol.upper()}
    response = requests.get(config.BINANCE_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    if "price" not in data:
        raise ValueError(f"Symbol '{symbol}' not found in Binance response.")
    return float(data["price"])
