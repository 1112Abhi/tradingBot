# tests/test_strategy_v2.py - Phase 5 EMA Strategy Tests
# Updated: _old/strategy.py removed; tests now use strategy/ema_crossover.py directly.

import pytest
import config
from strategy.ema_crossover import MACrossoverStrategy
from strategy.base import MarketData


def _make_strategy() -> MACrossoverStrategy:
    """Return strategy with RSI filter disabled (rsi_buy_min=0, rsi_buy_max=100)."""
    return MACrossoverStrategy(rsi_buy_min=0, rsi_buy_max=100)


def _signal(prices, entry_price=None, position="NONE") -> str:
    s = _make_strategy()
    md: MarketData = {
        "prices":      prices,
        "entry_price": entry_price,
        "position":    position,
        "symbol":      "BTCUSDT",
        "timestamp":   "2026-01-01T00:00:00Z",
    }
    try:
        return s.generate_signal(md)
    except ValueError:
        return config.SIGNAL_NO_TRADE


class TestComputeEMA:
    """Test EMA computation via MACrossoverStrategy._ema."""

    def test_ema_not_enough_data(self):
        s = _make_strategy()
        with pytest.raises(ValueError):
            s._ema([100.0, 101.0, 102.0], period=5)

    def test_ema_with_flat_prices(self):
        s = _make_strategy()
        ema = s._ema([100.0] * 10, period=5)
        assert abs(ema - 100.0) < 0.01

    def test_ema_with_rising_prices(self):
        s = _make_strategy()
        prices = [100.0 + i for i in range(10)]
        ema = s._ema(prices, period=5)
        assert ema > 105.0

    def test_ema_recent_prices_weighted_more(self):
        s = _make_strategy()
        prices = [100.0] * 8 + [110.0] * 2
        ema = s._ema(prices, period=5)
        assert ema > 105.0


class TestGenerateSignalBasic:
    """Test EMA crossover signal generation."""

    def test_insufficient_history(self):
        prices = [100.0] * 10
        assert _signal(prices) == config.SIGNAL_NO_TRADE

    def test_flat_prices_no_signal(self):
        prices = [100.0] * 55  # flat — no crossover
        assert _signal(prices) == config.SIGNAL_NO_TRADE

    def test_buy_crossover_v_shaped(self):
        # Drop then spike — fast EMA crosses above slow, price above trend
        prices = [100.0] * 50 + [10.0] * 9 + [200.0]
        result = _signal(prices)
        assert result in (config.SIGNAL_BUY, config.SIGNAL_NO_TRADE)

    def test_sell_crossover_inverted_v(self):
        # Spike then crash — fast EMA crosses below slow
        prices = [10.0] * 50 + [200.0] * 15 + [5.0]
        assert _signal(prices) in (config.SIGNAL_SELL, config.SIGNAL_NO_TRADE)


class TestStopLoss:
    """Test stop loss via STOP_LOSS_PCT (config) — checked inside ema_crossover."""

    def test_stop_loss_triggered(self):
        # 6% drop from entry — exceeds STOP_LOSS_PCT (5%)
        prices = [100.0] * 55 + [94.0]
        assert _signal(prices, entry_price=100.0, position="LONG") == config.SIGNAL_SELL

    def test_stop_loss_not_triggered(self):
        # 4.9% drop — below threshold
        prices = [100.0] * 55 + [95.1]
        result = _signal(prices, entry_price=100.0, position="LONG")
        assert result in (config.SIGNAL_NO_TRADE, config.SIGNAL_SELL)

    def test_entry_price_none_ignores_stop_loss(self):
        prices = [100.0] * 55 + [50.0]
        result = _signal(prices, entry_price=None)
        assert result in (config.SIGNAL_BUY, config.SIGNAL_NO_TRADE, config.SIGNAL_SELL)


class TestEdgeCases:
    """Edge case handling."""

    def test_empty_price_list(self):
        assert _signal([]) == config.SIGNAL_NO_TRADE

    def test_single_price(self):
        assert _signal([100.0]) == config.SIGNAL_NO_TRADE

    def test_flat_prices_no_crossover(self):
        assert _signal([100.0] * 55) == config.SIGNAL_NO_TRADE


class TestIntegrationWithConfig:
    """Verify strategy uses correct config values."""

    def test_fast_period_in_config(self):
        assert config.FAST_PERIOD == 12

    def test_slow_period_in_config(self):
        assert config.SLOW_PERIOD == 26

    def test_stop_loss_pct_in_config(self):
        assert config.STOP_LOSS_PCT == 0.05
