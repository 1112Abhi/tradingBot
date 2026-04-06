# main.py - Trading Bot Orchestrator

import config
from core.data_fetch import fetch_price
from logger import log_activity
from core.state import get_state, save_state, should_send_alert, update_price_history
from strategy import generate_signal
from telegram.bot import send_message


def run() -> bool:
    """
    Single-shot pipeline: Fetch → Analyse → Alert → Log → Persist state.
    
    Supports both v1 (simple threshold) and v2 (EMA crossover) strategies
    based on STRATEGY_VERSION in config.

    Returns:
        True if the run completed without a fetch error.
    """
    state = get_state()
    price = fetch_price(symbol=config.SYMBOL, source=config.DATA_SOURCE)
    
    # Build price history and generate signal
    if config.STRATEGY_VERSION == 2:
        # v2: EMA Crossover strategy
        price_history = update_price_history(price)
        entry_price = state.get("entry_price")
        signal = generate_signal(
            prices=price_history,
            entry_price=entry_price
        )
    else:
        # v1: Simple threshold strategy (backward compat)
        price_history = []
        entry_price = None
        signal = generate_signal(price=price)

    if should_send_alert(signal, state["last_signal"]):
        message = f"📊 {config.SYMBOL.upper()} | Signal: {signal} | Price: ${price:,.2f}"
        success = send_message(message)
        action = "alert_sent" if success else "alert_failed"
        # Update entry price on BUY signal
        if signal == config.SIGNAL_BUY:
            entry_price = price
    else:
        action = "skipped"

    save_state(signal, price, price_history, entry_price)
    log_activity(price, signal, action)
    return True


if __name__ == "__main__":
    run()
