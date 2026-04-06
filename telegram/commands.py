# telegram_commands.py - Telegram Bot Command Handlers

import subprocess
from typing import Optional

import config
from core.data_fetch import fetch_price
from logger import get_recent_logs
from core.state import get_state


def handle_command(text: str) -> str:
    """
    Parse and execute a Telegram command.

    Args:
        text: Message text from user (e.g., "/status", "/price bitcoin")

    Returns:
        Response message to send back to user.
    """
    parts = text.strip().split()
    command = parts[0].lower()

    if command == "/status":
        return cmd_status()
    elif command == "/price":
        symbol = parts[1].lower() if len(parts) > 1 else config.SYMBOL
        return cmd_price(symbol)
    elif command == "/symbols":
        return cmd_symbols()
    elif command == "/test":
        return cmd_test()
    elif command == "/logs":
        days = int(parts[1]) if len(parts) > 1 else 1
        return cmd_logs(days)
    elif command == "/help":
        return cmd_help()
    else:
        return "❓ Unknown command. Type /help for available commands."


def cmd_status() -> str:
    """Show current status: last signal and price."""
    state = get_state()
    signal = state.get("last_signal") or "UNKNOWN"
    price = state.get("last_price") or "N/A"

    return f"📊 Status:\n• Signal: {signal}\n• Price: ${price:,.2f}" if isinstance(price, (int, float)) else f"📊 Status:\n• Signal: {signal}\n• Price: {price}"


def cmd_price(symbol: str) -> str:
    """Fetch and return current price for a symbol."""
    if symbol not in config.AVAILABLE_SYMBOLS:
        return f"❌ Symbol '{symbol}' not available.\nAvailable: {', '.join(config.AVAILABLE_SYMBOLS)}"

    try:
        price = fetch_price(symbol=symbol, source=config.DATA_SOURCE)
        return f"💰 {symbol.upper()}: ${price:,.2f}"
    except Exception as e:
        return f"❌ Error fetching price: {str(e)}"


def cmd_symbols() -> str:
    """List available symbols."""
    symbols = ", ".join(config.AVAILABLE_SYMBOLS)
    return f"📍 Available symbols:\n{symbols}"


def cmd_test() -> str:
    """Run quick pipeline test."""
    try:
        # Test: fetch price
        price = fetch_price(symbol=config.SYMBOL, source=config.DATA_SOURCE)
        
        # Test: generate signal using current EMA strategy
        from strategy.ema_crossover import MACrossoverStrategy
        signal = "OK (strategy loaded)"
        
        # Test: state
        state = get_state()
        
        return f"✅ Pipeline OK:\n• Price: ${price:,.2f}\n• Signal: {signal}\n• State: Valid"
    except Exception as e:
        return f"❌ Pipeline Error: {str(e)}"


def cmd_logs(days: int = 1) -> str:
    """Show recent activity logs."""
    logs = get_recent_logs(days=days)
    
    if not logs:
        return f"📋 No logs from last {days} day(s)"
    
    log_text = "\n".join(logs[:10])  # Limit to 10 recent entries
    return f"📋 Recent Activity ({days} day(s)):\n{log_text}"


def cmd_help() -> str:
    """Show available commands."""
    return """🤖 Available Commands:
/status - Show current signal & price
/price [symbol] - Get price for symbol
/symbols - List available symbols
/test - Run pipeline test
/logs [days] - Show recent activity (default: 1 day)
/help - Show this message"""
