# tests/test_telegram_commands.py

from unittest.mock import MagicMock, patch

from telegram.commands import handle_command, cmd_summary, cmd_history, cmd_price, cmd_help


def _mock_db(positions=None, trades=None):
    db = MagicMock()
    db.get_all_open_positions.return_value = positions or []
    db.get_recent_live_trades.return_value = trades or []
    return db


# ── /summary ──────────────────────────────────────────────────────────────────

def test_summary_no_positions():
    db = _mock_db(positions=[])
    assert "No open positions" in cmd_summary(db)


def test_summary_with_position():
    pos = {
        "symbol": "BTCUSDT", "interval": "4h", "strategy": "ema_crossover",
        "entry_price": 80000.0, "position_value": 2500.0,
        "sl_price": 78800.0, "tp_price": 84800.0, "entry_ts": "2026-04-25T00:00:00Z",
    }
    db = _mock_db(positions=[pos])
    with patch("telegram.commands._fetch_live_price", return_value=82000.0):
        reply = cmd_summary(db)
    assert "ema_crossover" in reply
    assert "82,000" in reply or "82000" in reply
    assert "Unrealized" in reply


def test_summary_price_unavailable():
    pos = {
        "symbol": "BTCUSDT", "interval": "4h", "strategy": "mean_reversion",
        "entry_price": 80000.0, "position_value": 2500.0,
        "sl_price": 78800.0, "tp_price": 84800.0, "entry_ts": "2026-04-25T00:00:00Z",
    }
    db = _mock_db(positions=[pos])
    with patch("telegram.commands._fetch_live_price", return_value=None):
        reply = cmd_summary(db)
    assert "N/A" in reply


# ── /history ──────────────────────────────────────────────────────────────────

def test_history_no_trades():
    db = _mock_db(trades=[])
    assert "No completed trades" in cmd_history(db)


def test_history_with_trades():
    trade = {
        "symbol": "BTCUSDT", "interval": "4h", "strategy": "ema_crossover",
        "entry_price": 69000.0, "exit_price": 73000.0,
        "pnl_dollar": 168.76, "pnl_pct": 6.0,
        "entry_ts": "2026-04-06T00:00:00Z", "exit_ts": "2026-04-13T20:00:00Z",
        "exit_reason": "take_profit", "strategy_mode": "portfolio",
    }
    db = _mock_db(trades=[trade])
    reply = cmd_history(db)
    assert "ema_crossover" in reply
    assert "168" in reply
    assert "TP" in reply


def test_history_shows_experiment_tag():
    trade = {
        "symbol": "ETHUSDT", "interval": "1h", "strategy": "bb_breakout",
        "entry_price": 2000.0, "exit_price": 1970.0,
        "pnl_dollar": -42.14, "pnl_pct": -1.69,
        "entry_ts": "2026-04-06T03:00:00Z", "exit_ts": "2026-04-06T23:00:00Z",
        "exit_reason": "stop_loss", "strategy_mode": "experiment",
    }
    db = _mock_db(trades=[trade])
    reply = cmd_history(db)
    assert "[EXP]" in reply
    assert "SL" in reply


# ── /price ────────────────────────────────────────────────────────────────────

def test_price_success():
    with patch("telegram.commands._fetch_live_price", return_value=94000.0):
        reply = cmd_price()
    assert "BTC" in reply
    assert "94,000" in reply or "94000" in reply


def test_price_unavailable():
    with patch("telegram.commands._fetch_live_price", return_value=None):
        reply = cmd_price()
    assert "unavailable" in reply


# ── /help ─────────────────────────────────────────────────────────────────────

def test_help():
    reply = cmd_help()
    assert "/summary" in reply
    assert "/history" in reply
    assert "/price" in reply


# ── handle_command routing ────────────────────────────────────────────────────

def test_routing_slash_summary():
    db = _mock_db()
    reply = handle_command("/summary", db)
    assert "No open positions" in reply


def test_routing_plain_text_summary():
    db = _mock_db()
    reply = handle_command("summary", db)
    assert "No open positions" in reply


def test_routing_natural_language():
    db = _mock_db()
    reply = handle_command("give me a summary", db)
    assert "No open positions" in reply


def test_routing_history():
    db = _mock_db()
    reply = handle_command("/history", db)
    assert "No completed trades" in reply


def test_routing_price():
    with patch("telegram.commands._fetch_live_price", return_value=94000.0):
        reply = handle_command("/price", _mock_db())
    assert "BTC" in reply


def test_routing_help():
    reply = handle_command("/help", _mock_db())
    assert "/summary" in reply


def test_routing_unknown():
    reply = handle_command("/xyz", _mock_db())
    assert "Unknown" in reply
