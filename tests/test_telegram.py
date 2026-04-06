# tests/test_telegram.py

import pytest
from unittest.mock import patch, MagicMock
from telegram.bot import send_message


def test_send_message_returns_true_on_valid_input():
    """Test with mocked requests to avoid real API calls."""
    with patch('telegram.bot.requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = send_message("BUY signal detected at price 100.0")
        assert result is True


def test_send_message_returns_false_on_empty_string():
    result = send_message("")
    assert result is False


def test_send_message_returns_false_on_non_string():
    result = send_message(None)
    assert result is False


def test_send_message_accepts_any_text():
    """Test with mocked requests."""
    with patch('telegram.bot.requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = send_message("NO_TRADE")
        assert result is True
