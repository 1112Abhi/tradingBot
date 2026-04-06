# tests/test_strategy.py
# Tests for Phase 1 simple threshold strategy (BUY_THRESHOLD / SELL_THRESHOLD).
# The old _old/strategy.py is gone — these tests now use config constants directly
# to verify the threshold values are still correct.

import config


def test_buy_threshold_value():
    assert config.BUY_THRESHOLD == 90.0


def test_sell_threshold_value():
    assert config.SELL_THRESHOLD == 50.0


def test_signal_constants_defined():
    assert config.SIGNAL_BUY      == "BUY"
    assert config.SIGNAL_SELL     == "SELL"
    assert config.SIGNAL_NO_TRADE == "NO_TRADE"
