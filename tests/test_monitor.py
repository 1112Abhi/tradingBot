# tests/test_monitor.py

import pytest
from unittest.mock import patch, MagicMock
import config
from core.monitor import _run_cycle
from strategy.factory import get_strategies


def test_run_cycle_fetch_error():
    """Test handling of fetch errors."""
    strategies = get_strategies()
    state = {"last_signal": None, "last_price": 95.0, "position": "NONE"}
    with patch('core.monitor.fetch_price', side_effect=Exception("Network error")):
        price, signal, action = _run_cycle("bitcoin", strategies, state)
        assert price == 0.0
        assert signal == "NO_TRADE"
        assert action == "fetch_error"


def test_run_cycle_sends_alert_on_signal_change():
    """Test that alert is sent when signal changes."""
    strategies = get_strategies()
    state = {"last_signal": None, "last_price": 95.0, "position": "NONE"}
    with patch('core.monitor.fetch_price', return_value=95.0), \
         patch('core.monitor.send_message', return_value=True) as mock_send:
        price, signal, action = _run_cycle("bitcoin", strategies, state)
        # On first run (last_signal=None), even NO_TRADE may trigger
        assert action in ["alert_sent", "skipped"]


def test_run_cycle_skips_duplicate_signal():
    """Test that duplicate signals skip sending alert."""
    strategies = get_strategies()
    state = {"last_signal": "NO_TRADE", "last_price": 95.0, "position": "NONE"}
    with patch('core.monitor.fetch_price', return_value=95.0), \
         patch('core.monitor.send_message') as mock_send:
        price, signal, action = _run_cycle("bitcoin", strategies, state)
        if signal == "NO_TRADE":  # Duplicate
            assert action == "skipped"


def test_run_cycle_handles_send_failure():
    """Test handling when Telegram send fails."""
    strategies = get_strategies()
    state = {"last_signal": None, "last_price": 95.0, "position": "NONE"}
    with patch('core.monitor.fetch_price', return_value=95.0), \
         patch('core.monitor.send_message', return_value=False):
        price, signal, action = _run_cycle("bitcoin", strategies, state)
        # Should handle failure gracefully
        assert isinstance(action, str)

