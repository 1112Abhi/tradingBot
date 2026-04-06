# backtest/engine.py - Backtesting Engine

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import config
from strategy.aggregator import aggregate
from strategy.risk_manager import compute_atr, compute_position_size
from backtest.database import Database
from backtest.metrics import compute_metrics
from strategy.base import BaseStrategy, MarketData
from strategy.factory import get_strategies


def run_backtest(
    symbol: str = "BTCUSDT",
    interval: str = config.BACKTEST_INTERVAL,
    mode: str = "both",                     # "per", "agg", "both"
    db: Optional[Database] = None,
    strategies: Optional[List[BaseStrategy]] = None,
    sl_pct: Optional[float] = None,
    tp_pct: Optional[float] = None,
) -> List[str]:
    """
    Run a backtest against stored historical data.

    Signal at bar t → execution at bar t+1 (no lookahead).
    Warmup bars (< MIN_WINDOW) are skipped — no trades possible.
    Open positions at end-of-data are force-closed at the last bar.

    Args:
        symbol:     Binance pair stored in DB (e.g. "BTCUSDT").
        interval:   Candle interval (e.g. "1h").
        mode:       "per" = per-strategy only, "agg" = aggregated only,
                    "both" = run both and store as separate DB runs.
        db:         Optional Database instance (created if not provided).
        strategies: Optional pre-configured strategy list. If None, loads
                    from config via get_strategies() (normal operation).
        sl_pct:     Stop-loss fraction override (e.g. 0.015). Falls back to
                    config.BACKTEST_STOP_LOSS_PCT when None.
        tp_pct:     Take-profit fraction override (e.g. 0.06). Falls back to
                    config.BACKTEST_TAKE_PROFIT_PCT when None.

    Returns:
        List of run_ids stored in the DB (one per mode).
    """
    db         = db or Database()
    strategies = strategies if strategies is not None else get_strategies()
    bars       = db.get_prices(symbol, interval)

    if len(bars) < config.BACKTEST_MIN_WINDOW + 1:
        raise ValueError(
            f"Not enough data: need > {config.BACKTEST_MIN_WINDOW} bars, "
            f"got {len(bars)}. Run DataLoader.sync() first."
        )

    run_ids: List[str] = []

    if mode in ("per", "both"):
        for strategy in strategies:
            run_id = _run_single(
                bars       = bars,
                strategies = [strategy],
                aggregated = False,
                symbol     = symbol,
                interval   = interval,
                db         = db,
                sl_pct     = sl_pct,
                tp_pct     = tp_pct,
            )
            run_ids.append(run_id)
            _print_summary(db, run_id)

    if mode in ("agg", "both"):
        run_id = _run_single(
            bars       = bars,
            strategies = strategies,
            aggregated = True,
            symbol     = symbol,
            interval   = interval,
            db         = db,
            sl_pct     = sl_pct,
            tp_pct     = tp_pct,
        )
        run_ids.append(run_id)
        _print_summary(db, run_id)

    return run_ids


# ---------------------------------------------------------------------------
# Core simulation loop
# ---------------------------------------------------------------------------

def _run_single(
    bars: list,
    strategies: List[BaseStrategy],
    aggregated: bool,
    symbol: str,
    interval: str,
    db: Database,
    sl_pct: Optional[float] = None,
    tp_pct: Optional[float] = None,
) -> str:
    """
    Simulate one backtest run (either per-strategy or aggregated).

    Returns the run_id stored in the DB.
    """
    run_id          = str(uuid.uuid4())
    initial_capital = config.BACKTEST_CAPITAL
    capital         = initial_capital
    warmup_bars     = config.BACKTEST_MIN_WINDOW

    # Rolling position state
    position             = "NONE"
    entry_price          = None
    entry_ts             = None
    entry_bar            = None
    entry_position_value = None   # locked at entry via ATR risk sizing
    trade_num            = 0
    trades: List[dict]   = []

    # Exit parameters: caller overrides take priority over config
    STOP_LOSS_PCT   = sl_pct if sl_pct is not None else config.BACKTEST_STOP_LOSS_PCT
    TAKE_PROFIT_PCT = tp_pct if tp_pct is not None else config.BACKTEST_TAKE_PROFIT_PCT
    MAX_HOLD_BARS   = 100     # Exit if no SL/TP hit after 100 bars

    strategy_label = (
        config.AGGREGATION_METHOD if aggregated
        else strategies[0].name
    )

    # ── Main loop ──────────────────────────────────────────────────────
    # Signal at index t (bars 0..t), execute at index t+1
    for t in range(warmup_bars, len(bars) - 1):
        window      = [dict(b) for b in bars[:t + 1]]
        exec_bar    = bars[t + 1]               # execution bar (t+1)
        exec_price  = exec_bar["mid"]
        exec_ts     = exec_bar["timestamp"]

        market_data: MarketData = {
            "prices":      [row["mid"] for row in window],
            "entry_price": entry_price,
            "position":    position,
            "symbol":      symbol,
            "timestamp":   window[-1]["timestamp"],
            "volumes":     [row["volume"] for row in window],
        }

        signal = _get_signal(market_data, strategies, aggregated)

        # ── State machine ──────────────────────────────────────────────
        if signal == config.SIGNAL_BUY and position == "NONE":
            prices = market_data["prices"]
            try:
                atr = compute_atr(prices, config.ATR_PERIOD)
            except ValueError:
                atr = exec_price * config.ATR_REFERENCE_PCT  # fallback: 1% of price

            # Apply buy slippage: we pay slightly more than mid price
            slipped_entry        = exec_price * (1 + config.SLIPPAGE_RATE)
            position             = "LONG"
            entry_price          = slipped_entry
            entry_ts             = exec_ts
            entry_bar            = t
            entry_position_value = compute_position_size(
                capital  = capital,
                atr      = atr,
                price    = exec_price,
                sl_pct   = STOP_LOSS_PCT,
            )

        elif position == "LONG":
            # V4: ONLY mechanical stops - NO EMA exit signal
            stop_loss_price = entry_price * (1 - STOP_LOSS_PCT)
            take_profit_price = entry_price * (1 + TAKE_PROFIT_PCT)
            
            exit_triggered = False
            exit_reason = "signal"
            
            # Take profit
            if exec_price >= take_profit_price:
                exit_triggered = True
                exit_reason = "take_profit"
            # Stop loss
            elif exec_price <= stop_loss_price:
                exit_triggered = True
                exit_reason = "stop_loss"
            # Timeout: exit if held > MAX_HOLD_BARS without hitting SL/TP
            elif (t - entry_bar) > MAX_HOLD_BARS:
                exit_triggered = True
                exit_reason = "timeout"
            
            if exit_triggered:
                trade = _close_trade(
                    trade_num      = trade_num + 1,
                    entry_ts       = entry_ts,
                    exit_ts        = exec_ts,
                    entry_price    = entry_price,
                    exit_price     = exec_price,
                    position_value = entry_position_value,
                    exit_reason    = exit_reason,
                )
                capital              += trade["pnl_dollar"]
                trade_num            += 1
                trades.append(trade)
                position             = "NONE"
                entry_price          = None
                entry_ts             = None
                entry_position_value = None

    # ── Force-close at end of data ─────────────────────────────────────
    if position == "LONG":
        last_bar = bars[-1]
        trade = _close_trade(
            trade_num      = trade_num + 1,
            entry_ts       = entry_ts,
            exit_ts        = last_bar["timestamp"],
            entry_price    = entry_price,
            exit_price     = last_bar["mid"],
            position_value = entry_position_value,
            exit_reason    = "end_of_data",
        )
        capital += trade["pnl_dollar"]
        trades.append(trade)

    # ── Metrics + persist ──────────────────────────────────────────────
    metrics = compute_metrics(
        trades          = trades,
        initial_capital = initial_capital,
        final_capital   = capital,
        total_bars      = len(bars),
        warmup_bars     = warmup_bars,
        interval        = interval,
    )

    start_date = bars[warmup_bars]["timestamp"]
    end_date   = bars[-1]["timestamp"]

    db.insert_run(
        run_id             = run_id,
        symbol             = symbol,
        interval           = interval,
        strategy           = strategy_label,
        aggregation_method = config.AGGREGATION_METHOD if aggregated else None,
        start_date         = start_date,
        end_date           = end_date,
        metrics            = metrics,
        fee_pct            = config.BACKTEST_FEE_PCT,
    )

    for trade in trades:
        db.insert_trade(run_id, trade)

    return run_id


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _get_signal(
    market_data: MarketData,
    strategies: List[BaseStrategy],
    aggregated: bool,
) -> str:
    """
    Generate signal for a single bar.
    Mirrors live monitor.py exactly: exceptions → NO_TRADE (warn + continue).
    """
    per_strategy: dict = {}

    for strategy in strategies:
        try:
            per_strategy[strategy.name] = strategy.generate_signal(market_data)
        except Exception as exc:
            print(f"[ENGINE] {strategy.name} skipped at {market_data['timestamp']}: {exc}")
            per_strategy[strategy.name] = config.SIGNAL_NO_TRADE

    if aggregated:
        return aggregate(per_strategy)

    # Per-strategy mode: only one strategy in list
    return list(per_strategy.values())[0]


# ---------------------------------------------------------------------------
# Trade helpers
# ---------------------------------------------------------------------------

def _close_trade(
    trade_num: int,
    entry_ts: str,
    exit_ts: str,
    entry_price: float,
    exit_price: float,
    position_value: float,
    exit_reason: str,
) -> dict:
    """
    Compute P&L for a closed trade with leverage, slippage, and fees on both legs.

    entry_price is already slippage-adjusted (set at entry time).
    exit_price is the raw mid price; sell slippage is applied here.

    Leverage scales the effective exposure while position_value is the
    actual capital committed (used as denominator for pnl_pct).
    """
    # Apply sell slippage: we receive slightly less than mid price
    exit_exec = exit_price * (1 - config.SLIPPAGE_RATE)

    # Leverage scales exposure, not capital committed
    effective_position = position_value * config.LEVERAGE

    # P&L on leveraged exposure
    gross_pnl  = effective_position * (exit_exec - entry_price) / entry_price
    entry_fee  = effective_position * config.BACKTEST_FEE_PCT
    exit_fee   = (effective_position + gross_pnl) * config.BACKTEST_FEE_PCT
    total_fees = entry_fee + exit_fee
    net_pnl    = gross_pnl - total_fees

    # pnl_pct relative to capital committed (not leveraged exposure)
    pnl_pct = (net_pnl / position_value * 100) if position_value else 0.0

    return {
        "trade_num":     trade_num,
        "entry_ts":      entry_ts,
        "exit_ts":       exit_ts,
        "entry_price":   round(entry_price, 8),   # slippage-adjusted
        "exit_price":    round(exit_exec, 8),     # slippage-adjusted
        "gross_pnl":     round(gross_pnl, 4),
        "fees_paid":     round(total_fees, 4),
        "pnl_dollar":    round(net_pnl, 4),
        "pnl_pct":       round(pnl_pct, 4),
        "exit_reason":   exit_reason,
        "leverage_used": config.LEVERAGE,
    }


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def _print_summary(db: Database, run_id: str) -> None:
    """Print a formatted summary for a completed run."""
    run = db.get_run(run_id)
    if not run:
        return

    print()
    print("=" * 55)
    print(f"  BACKTEST COMPLETE")
    print(f"  run_id   : {run_id}")
    print(f"  symbol   : {run['symbol']} ({run['interval']})")
    print(f"  strategy : {run['strategy']}")
    print(f"  period   : {run['start_date'][:10]} → {run['end_date'][:10]}")
    print("-" * 55)
    print(f"  bars     : {run['total_bars']} total / {run['tradeable_bars']} tradeable")
    print(f"  trades   : {run['total_trades']} ({run['winning_trades']} wins)")
    print(f"  win rate : {run['win_rate_pct']:.1f}%")
    print(f"  return   : {run['total_return_pct']:+.2f}%")
    print(f"  sharpe   : {run.get('sharpe_ratio', 0.0):.4f}")
    print(f"  drawdown : {run['max_drawdown_pct']:.2f}%")
    print(f"  capital  : ${run['initial_capital']:,.2f} → ${run['final_capital']:,.2f}")
    gross = run.get('gross_pnl', 0.0)
    fees  = run.get('total_fees_paid', 0.0)
    print(f"  gross pnl: ${gross:+,.2f}  fees: ${fees:,.2f}  leverage: {config.LEVERAGE}x")
    print("=" * 55)
    print(f"  To query trades: SELECT * FROM backtest_trades WHERE run_id='{run_id}';")
    print()
