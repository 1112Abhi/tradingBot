# tests/test_state.py

import os
import json
import pytest
from core.state import get_state, save_state, should_send_alert
import config


def test_get_state_default_on_missing_file():
    """Test that get_state returns defaults if file doesn't exist."""
    if os.path.exists(config.STATE_FILE):
        os.remove(config.STATE_FILE)
    
    state = get_state()
    assert state["last_signal"] is None
    assert state["last_price"] is None


def test_save_and_get_state():
    """Test that state persists to JSON."""
    if os.path.exists(config.STATE_FILE):
        os.remove(config.STATE_FILE)
    
    save_state("BUY", 105.5)
    state = get_state()
    
    assert state["last_signal"] == "BUY"
    assert state["last_price"] == 105.5


def test_should_send_alert_on_first_run():
    """Test alert is sent on first run (last_signal is None)."""
    assert should_send_alert("BUY", None) is True


def test_should_send_alert_on_signal_change():
    """Test alert is sent when signal changes."""
    assert should_send_alert("BUY", "NO_TRADE") is True


def test_should_send_alert_skips_duplicate():
    """Test alert is skipped for duplicate signals."""
    assert should_send_alert("BUY", "BUY") is False
