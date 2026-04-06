# tests/test_telegram_commands.py

import pytest
from unittest.mock import patch, MagicMock
from telegram.commands import (
    handle_command,
    cmd_status,
    cmd_price,
    cmd_symbols,
    cmd_test,
    cmd_help,
)
import config


def test_handle_command_status():
    """Test /status command."""
    with patch('telegram.commands.get_state', return_value={"last_signal": "BUY", "last_price": 66884.0}):
        response = handle_command("/status")
        assert "BUY" in response
        assert "66884" in response or "66,884" in response


def test_handle_command_symbols():
    """Test /symbols command."""
    response = handle_command("/symbols")
    assert "bitcoin" in response.lower()
    assert "ethereum" in response.lower()


def test_handle_command_help():
    """Test /help command."""
    response = handle_command("/help")
    assert "/status" in response
    assert "/price" in response
    assert "/symbols" in response


def test_handle_command_unknown():
    """Test unknown command."""
    response = handle_command("/unknown")
    assert "Unknown command" in response


def test_cmd_price_valid_symbol():
    """Test price command with valid symbol."""
    with patch('telegram.commands.fetch_price', return_value=42500.0):
        response = cmd_price("bitcoin")
        assert ("42500" in response or "42,500" in response)
        assert "BITCOIN" in response


def test_cmd_price_invalid_symbol():
    """Test price command with invalid symbol."""
    response = cmd_price("invalid_symbol")
    assert "not available" in response or "❌" in response


def test_cmd_price_fetch_error():
    """Test price command when fetch fails."""
    with patch('telegram.commands.fetch_price', side_effect=Exception("Network error")):
        response = cmd_price("bitcoin")
        assert "Error" in response or "❌" in response


def test_cmd_test_success():
    """Test /test command on success."""
    with patch('telegram.commands.fetch_price', return_value=95.0), \
         patch('telegram.commands.get_state', return_value={"last_signal": "BUY", "last_price": 95.0}):
        response = cmd_test()
        assert "✅" in response or "OK" in response or "Pipeline" in response
        # Check if price appears (with or without formatting)
        assert "95" in response


def test_cmd_test_error():
    """Test /test command on error."""
    with patch('telegram.commands.fetch_price', side_effect=Exception("API error")):
        response = cmd_test()
        assert "❌" in response or "Error" in response


def test_cmd_status_no_state():
    """Test status when no state exists."""
    with patch('telegram.commands.get_state', return_value={"last_signal": None, "last_price": None}):
        response = cmd_status()
        assert "UNKNOWN" in response or "Status" in response
