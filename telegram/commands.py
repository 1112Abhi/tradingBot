# telegram/commands.py - Telegram Command Handlers
#
# Commands (slash or plain text):
#   /summary   — open positions + unrealized P&L + capital deployed
#   /trades    — same as summary (alias)
#   /history   — last 10 completed trades
#   /price     — live BTC + ETH price
#   /sentiment — current market sentiment snapshot
#   /help      — command list
#
# Natural language aliases also supported (e.g. "give me summary", "active trades")

import logging
import requests
from typing import Optional

import config


# ── Live price fetch ───────────────────────────────────────────────────────────

def _fetch_live_price(symbol: str) -> Optional[float]:
    """Fetch current mid price from Binance REST API."""
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": symbol},
            timeout=5,
        )
        resp.raise_for_status()
        return float(resp.json()["price"])
    except Exception as exc:
        logging.warning(f"[COMMANDS] price fetch failed for {symbol}: {exc}")
        return None


# ── Command handlers ───────────────────────────────────────────────────────────

def cmd_summary(db) -> str:
    """Open positions with unrealized P&L and capital usage."""
    positions = db.get_all_open_positions()

    if not positions:
        return "📭 No open positions."

    lines = ["📊 Open Positions\n"]
    total_unrealized = 0.0
    total_deployed   = 0.0
    capital          = config.BACKTEST_CAPITAL

    # Fetch live prices once per unique symbol
    symbols = {p["symbol"] for p in positions}
    prices  = {s: _fetch_live_price(s) for s in symbols}

    for p in positions:
        live_price  = prices.get(p["symbol"])
        entry_price = p["entry_price"]
        pos_value   = p["position_value"]

        if live_price and entry_price:
            pnl_pct    = (live_price - entry_price) / entry_price * 100
            pnl_dollar = pos_value * (live_price - entry_price) / entry_price
            total_unrealized += pnl_dollar
            price_str  = f"${live_price:,.2f}"
            pnl_str    = f"${pnl_dollar:+.2f} ({pnl_pct:+.2f}%)"
        else:
            price_str = "N/A"
            pnl_str   = "N/A"

        total_deployed += pos_value

        lines.append(
            f"• {p['strategy']} | {p['symbol']} {p['interval']}\n"
            f"  Entry: ${entry_price:,.2f}  Live: {price_str}\n"
            f"  Size: ${pos_value:,.0f} ({pos_value / capital * 100:.0f}%)\n"
            f"  Unrealized P&L: {pnl_str}\n"
            f"  SL: ${p['sl_price']:,.2f}  TP: ${p['tp_price']:,.2f}"
        )

    lines.append(
        f"\n💼 Deployed: ${total_deployed:,.0f} ({total_deployed / capital * 100:.0f}% of capital)"
        f"\n📈 Total Unrealized: ${total_unrealized:+,.2f}"
    )
    return "\n".join(lines)


def cmd_history(db, limit: int = 10) -> str:
    """Last N completed trades across all strategies."""
    trades = db.get_recent_live_trades(limit=limit)

    if not trades:
        return "📭 No completed trades yet."

    lines = [f"📋 Last {len(trades)} Trades\n"]
    total_pnl = 0.0

    for t in trades:
        emoji      = "✅" if t["pnl_dollar"] >= 0 else "❌"
        reason_map = {"take_profit": "TP", "stop_loss": "SL", "timeout": "TOut"}
        reason     = reason_map.get(t["exit_reason"], t["exit_reason"])
        mode_tag   = "[EXP]" if t.get("strategy_mode") == "experiment" else ""
        total_pnl += t["pnl_dollar"]

        lines.append(
            f"{emoji} {t['strategy']} {mode_tag} | {t['symbol']} {t['interval']}\n"
            f"  {t['entry_ts'][:10]} -> {t['exit_ts'][:10]}  ({reason})\n"
            f"  Entry: ${t['entry_price']:,.2f}  Exit: ${t['exit_price']:,.2f}\n"
            f"  P&L: ${t['pnl_dollar']:+.2f} ({t['pnl_pct']:+.2f}%)"
        )

    lines.append(f"\n💰 Total P&L: ${total_pnl:+,.2f}")
    return "\n".join(lines)


def cmd_price() -> str:
    """Fetch live BTC and ETH price."""
    results = []
    for symbol, name in [("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")]:
        price = _fetch_live_price(symbol)
        if price:
            results.append(f"• {name}: ${price:,.2f}")
        else:
            results.append(f"• {name}: unavailable")
    return "💰 Live Prices\n" + "\n".join(results)


def cmd_sentiment() -> str:
    """Fetch and format current multi-source sentiment snapshot."""
    try:
        from sentiment import aggregator
        result = aggregator.fetch("BTCUSDT")

        comp = result.composite
        if comp >= 0.4:
            mood = "Greedy — MR entries skipped"
        elif comp <= -0.2:
            mood = "Fearful — MR entries boosted"
        else:
            mood = "Neutral"

        lines = [
            "📡 Market Sentiment\n",
            f"Composite: {comp:+.2f}  ({mood})\n",
        ]
        if result.fg_label:
            lines.append(f"• Fear & Greed: {result.fg_score}/100 ({result.fg_label})")
        if result.funding_label:
            lines.append(f"• Funding Rate: {result.funding * 100:+.4f}% ({result.funding_label})")
        if result.dvol_label:
            lines.append(f"• DVOL (BTC Vol Index): {result.dvol:.1f} ({result.dvol_label})")
        if result.put_call:
            lines.append(f"• Put/Call OI Ratio: {result.put_call:.2f}")
        if result.news_label:
            lines.append(f"• News Sentiment: {result.news_score:+.2f} ({result.news_label})")
        if result.errors:
            lines.append(f"\nWarning: {len(result.errors)} source(s) unavailable: {', '.join(result.errors.keys())}")

        return "\n".join(lines)
    except Exception as exc:
        return f"Sentiment unavailable: {exc}"


def cmd_help() -> str:
    return (
        "🤖 Commands\n\n"
        "/summary   — open positions + unrealized P&L\n"
        "/history   — last 10 completed trades\n"
        "/price     — live BTC + ETH price\n"
        "/sentiment — market sentiment snapshot\n"
        "/help      — this message\n\n"
        "Plain text also works: \"summary\", \"history\", \"price\", \"sentiment\""
    )


# ── Router ─────────────────────────────────────────────────────────────────────

def handle_command(text: str, db) -> str:
    """
    Route a Telegram message to the right command handler.
    Supports /slash commands and natural language aliases.
    """
    t    = text.strip().lower()
    word = t.lstrip("/").split()[0] if t else ""

    if word in ("summary", "trades", "positions", "active"):
        return cmd_summary(db)
    elif word in ("history", "hist", "completed", "closed"):
        return cmd_history(db)
    elif word in ("price", "prices"):
        return cmd_price()
    elif word in ("sentiment", "fear", "greed", "mood"):
        return cmd_sentiment()
    elif word in ("help",):
        return cmd_help()

    # Natural language fallback
    if any(k in t for k in ("summary", "open trade", "active trade", "position", "unrealized", "pnl")):
        return cmd_summary(db)
    if any(k in t for k in ("history", "completed", "past trade", "closed")):
        return cmd_history(db)
    if any(k in t for k in ("price", "how much", "btc", "eth")):
        return cmd_price()
    if any(k in t for k in ("sentiment", "fear", "greed", "mood", "market feel")):
        return cmd_sentiment()

    return "❓ Unknown command. Type /help for available commands."
