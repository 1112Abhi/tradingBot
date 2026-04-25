# core/candle_watcher.py - Unified Multi-Symbol Candle Watcher
#
# Design:
#   - Supports multiple strategy groups, each owning one (symbol, interval) pair
#   - Groups loaded from YAML configs at startup
#   - mode="portfolio" → capital allocated, PortfolioState enforced
#   - mode="experiment" → signals logged and simulated, NO capital impact
#   - Each candle processed exactly once (idempotency via live_processed_candles)
#   - Position state persisted in DB — survives restarts
#   - Telegram: heartbeat every hour + trade entry/exit alerts
#   - Binance fetch: retry with exponential backoff, per symbol

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

import config
from backtest.database import Database
from backtest.data_loader import DataLoader
from strategy.base import BaseStrategy, MarketData
from core.portfolio_state import PortfolioState
from telegram.bot import send_message
from telegram.listener import BotListener
from utils.config_loader import load_config

POLL_INTERVAL_SECS = 300   # 5 min
HEARTBEAT_INTERVAL = 3600  # 1 hour

# All intervals to sync per symbol on each poll
SYNC_INTERVALS = ["15m", "30m", "1h", "4h"]

MAX_RETRIES   = 3
RETRY_BACKOFF = [5, 15, 30]


@dataclass
class StrategyGroup:
    """
    One logical trading unit: a single (symbol, interval) + its strategies.

    mode="portfolio"  → uses capital, PortfolioState enforced, [LIVE] tag
    mode="experiment" → no capital, signals observed only,    [EXPERIMENT] tag
    """
    symbol:         str
    interval:       str
    mode:           str                        # "portfolio" | "experiment"
    strategies:     List[BaseStrategy]
    sl_pct:         float
    tp_pct:         float
    position_sizes: Dict[str, float] = field(default_factory=dict)  # strategy.name → capital fraction

    @property
    def tag(self) -> str:
        return "[LIVE]" if self.mode == "portfolio" else "[EXPERIMENT]"

    @property
    def key(self):
        return (self.symbol, self.interval)


def _interval_hours(interval: str) -> float:
    """Convert interval string to hours (e.g. '4h'→4, '1h'→1, '30m'→0.5)."""
    if interval.endswith("h"):
        return float(interval[:-1])
    if interval.endswith("m"):
        return float(interval[:-1]) / 60
    return 1.0


class CandleWatcher:
    """
    Unified live / paper trading loop for multiple symbol+interval groups.

    Execution matches backtest exactly:
        Signal at candle T → entry at candle T+1 open (mid price)
        SL/TP/timeout logic identical to backtest engine
        Fees and slippage applied the same way
    """

    def __init__(
        self,
        groups: List[StrategyGroup],
        db:     Optional[Database] = None,
    ) -> None:
        self.groups    = groups
        self.db        = db or Database()
        self.loaders:  Dict[str, DataLoader] = {}   # one loader per symbol
        self.portfolio = PortfolioState(self.db)

        # One DataLoader per unique symbol
        for g in self.groups:
            if g.symbol not in self.loaders:
                self.loaders[g.symbol] = DataLoader(db=self.db)

        self._last_heartbeat: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        for g in self.groups:
            names = ", ".join(s.name for s in g.strategies)
            logging.info(
                f"[WATCHER] Group {g.symbol} {g.interval} [{g.mode}] "
                f"strategies=[{names}]  SL={g.sl_pct*100:.1f}%  TP={g.tp_pct*100:.1f}%"
            )

        self._restore_positions()
        self._catch_up()
        self._send_heartbeat()

        BotListener(db=self.db).start()

        try:
            while True:
                self._poll_once()
                self._maybe_heartbeat()
                time.sleep(POLL_INTERVAL_SECS)
        except KeyboardInterrupt:
            logging.info("[WATCHER] Stopped by user")

    # ------------------------------------------------------------------
    # Catch-up
    # ------------------------------------------------------------------

    def _restore_positions(self) -> None:
        for g in self.groups:
            positions = self.db.get_all_live_positions(g.symbol, g.interval)
            if positions:
                for pos in positions:
                    logging.info(
                        f"[WATCHER] {g.tag} Restored position: {pos['strategy']} "
                        f"entry={pos['entry_price']:.2f} at {pos['entry_ts']}"
                    )
            else:
                logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} — no open positions")

    def _catch_up(self) -> None:
        for g in self.groups:
            self._catch_up_group(g)

    def _catch_up_group(self, g: StrategyGroup) -> None:
        last_ts   = self.db.get_last_processed_candle(g.symbol, g.interval)
        first_run = last_ts is None

        if last_ts:
            logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} catching up from {last_ts}")
        else:
            last_ts = self.db.get_last_timestamp(g.symbol, g.interval)
            logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} first run, DB last: {last_ts}")

        self._fetch_symbol(g.symbol)

        bars = self.db.get_prices(g.symbol, g.interval, start=last_ts)
        if bars and bars[0]["timestamp"] == last_ts:
            bars = list(bars[1:])

        if not bars:
            logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} no missed candles")
            if first_run and last_ts:
                self.db.mark_candle_processed(g.symbol, g.interval, last_ts)
            return

        n         = len(bars)
        gap_hours = n * _interval_hours(g.interval)
        logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} processing {n} missed candle(s) ({gap_hours:.1f}h gap)")

        trades_before = self._count_trades(g)
        for bar in bars:
            self._process_candle(g, bar["timestamp"], trade_type="catch_up")
        trades_after = self._count_trades(g)
        new_trades   = trades_after - trades_before

        last_processed = self.db.get_last_processed_candle(g.symbol, g.interval)
        msg = (
            f"[CATCH-UP] {g.symbol} {g.interval} [{g.mode}]\n"
            f"Candles : {n}  ({gap_hours:.1f}h gap)\n"
            f"Trades  : {new_trades}\n"
            f"Up to   : {last_processed}"
        )
        logging.info(f"[WATCHER] {msg.replace(chr(10), '  ')}")
        if not first_run:
            _safe_send(msg)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _poll_once(self) -> None:
        # Sync data for each unique symbol
        synced_symbols = set()
        for g in self.groups:
            if g.symbol not in synced_symbols:
                self._fetch_symbol(g.symbol)
                synced_symbols.add(g.symbol)

        # Process new candles for each group
        for g in self.groups:
            last_processed = self.db.get_last_processed_candle(g.symbol, g.interval)
            recent = [dict(b) for b in self.db.get_prices(g.symbol, g.interval, start=last_processed)]

            if recent and recent[0]["timestamp"] == last_processed:
                recent = recent[1:]

            processable = recent[:-1] if len(recent) >= 2 else []

            if processable:
                logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} processing {len(processable)} new candle(s)")
                for bar in processable:
                    lag = _compute_lag(bar["timestamp"])
                    logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} candle {bar['timestamp']}  lag={lag:.0f}s")
                    self._process_candle(g, bar["timestamp"], trade_type="live")
            else:
                lag = _compute_lag(last_processed)
                logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} no new candle — last={last_processed}  lag={lag:.0f}s")

    # ------------------------------------------------------------------
    # Per-candle logic
    # ------------------------------------------------------------------

    def _process_candle(self, g: StrategyGroup, candle_ts: str, trade_type: str) -> None:
        if self.db.is_candle_processed(g.symbol, g.interval, candle_ts):
            return

        all_bars = self.db.get_prices(g.symbol, g.interval)
        bar_list = [dict(b) for b in all_bars]

        idx = next((i for i, b in enumerate(bar_list) if b["timestamp"] == candle_ts), None)
        if idx is None:
            logging.info(f"[WATCHER] {g.tag} {g.symbol} {g.interval} candle {candle_ts} not found — skipping")
            return

        if idx < config.BACKTEST_MIN_WINDOW:
            self.db.mark_candle_processed(g.symbol, g.interval, candle_ts)
            return

        if idx + 1 >= len(bar_list):
            return  # no execution bar yet — will be processed next poll

        window     = bar_list[:idx + 1]
        exec_bar   = bar_list[idx + 1]
        exec_price = exec_bar["mid"]
        exec_ts    = exec_bar["timestamp"]
        prices     = [b["mid"]    for b in window]
        volumes    = [b["volume"] for b in window]

        for strategy in g.strategies:
            position = self.db.get_live_position(g.symbol, g.interval, strategy.name)

            market_data: MarketData = {
                "prices":      prices,
                "entry_price": position["entry_price"] if position else None,
                "position":    "LONG" if position else "NONE",
                "symbol":      g.symbol,
                "timestamp":   candle_ts,
                "volumes":     volumes,
            }

            try:
                signal = strategy.generate_signal(market_data)
            except Exception as exc:
                logging.info(f"[WATCHER] {g.tag} [{strategy.name}] error at {candle_ts}: {exc}")
                signal = config.SIGNAL_NO_TRADE

            if signal == config.SIGNAL_BUY and not position:
                self._enter_position(g, strategy, candle_ts, exec_ts, exec_price, trade_type)

            elif position:
                entry_bar_idx = next(
                    (i for i, b in enumerate(bar_list) if b["timestamp"] == position["entry_candle_ts"]), 0
                )
                bars_held   = idx - entry_bar_idx
                exit_reason = None

                if exec_price >= position["tp_price"]:
                    exit_reason = "take_profit"
                elif exec_price <= position["sl_price"]:
                    exit_reason = "stop_loss"
                elif bars_held > 100:
                    exit_reason = "timeout"

                if exit_reason:
                    self._exit_position(g, strategy, position, exec_ts, exec_price, exit_reason, trade_type)

        self.db.mark_candle_processed(g.symbol, g.interval, candle_ts)

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def _enter_position(
        self,
        g:          StrategyGroup,
        strategy:   BaseStrategy,
        candle_ts:  str,
        exec_ts:    str,
        exec_price: float,
        trade_type: str,
    ) -> None:
        entry_price   = exec_price * (1 + config.SLIPPAGE_RATE)
        capital       = config.BACKTEST_CAPITAL
        size_fraction = g.position_sizes.get(strategy.name, config.PORTFOLIO_PER_STRATEGY_FRACTION)
        pos_value     = capital * size_fraction

        if g.mode == "portfolio":
            allowed, reason = self.portfolio.can_enter(g.symbol, g.interval, strategy.name, pos_value)
            if not allowed:
                logging.info(f"[PORTFOLIO] ENTRY REJECTED — {strategy.name} — {reason}")
                return
            total_used  = self.portfolio._total_used(g.symbol, g.interval)
            usage_after = (total_used + pos_value) / capital * 100
            logging.info(
                f"[PORTFOLIO] ENTRY ALLOWED — {strategy.name} — "
                f"size: {pos_value/capital*100:.0f}% (${pos_value:,.0f}) — "
                f"total usage: {usage_after:.0f}%"
            )
        else:
            logging.info(f"[EXPERIMENT] SIMULATED ENTRY — {g.symbol} {g.interval} [{strategy.name}]")

        sl_price = entry_price * (1 - g.sl_pct)
        tp_price = entry_price * (1 + g.tp_pct)

        pos = {
            "symbol":          g.symbol,
            "interval":        g.interval,
            "strategy":        strategy.name,
            "entry_candle_ts": candle_ts,
            "entry_ts":        exec_ts,
            "entry_price":     round(entry_price, 8),
            "position_value":  round(pos_value, 4),
            "sl_price":        round(sl_price, 8),
            "tp_price":        round(tp_price, 8),
            "trade_type":      trade_type,
        }
        self.db.open_live_position(pos)

        tag = g.tag
        if trade_type == "catch_up":
            tag = "[CATCH-UP]"

        msg = (
            f"{tag} PAPER BUY {g.symbol} [{strategy.name}]\n"
            f"Entry : ${entry_price:,.2f}\n"
            f"SL    : ${sl_price:,.2f} (-{g.sl_pct*100:.1f}%)\n"
            f"TP    : ${tp_price:,.2f} (+{g.tp_pct*100:.1f}%)\n"
            f"Size  : ${pos_value:,.2f}  |  {config.LEVERAGE}x leverage\n"
            f"Time  : {exec_ts}"
        )
        logging.info(f"[WATCHER] {msg.replace(chr(10), '  ')}")
        _safe_send(msg)

    def _exit_position(
        self,
        g:           StrategyGroup,
        strategy:    BaseStrategy,
        position:    dict,
        exec_ts:     str,
        exec_price:  float,
        exit_reason: str,
        trade_type:  str,
    ) -> None:
        exit_exec  = exec_price * (1 - config.SLIPPAGE_RATE)
        entry      = position["entry_price"]
        pos_value  = position["position_value"]
        eff_pos    = pos_value * config.LEVERAGE

        gross_pnl  = eff_pos * (exit_exec - entry) / entry
        entry_fee  = eff_pos * config.BACKTEST_FEE_PCT
        exit_fee   = (eff_pos + gross_pnl) * config.BACKTEST_FEE_PCT
        total_fees = entry_fee + exit_fee
        net_pnl    = gross_pnl - total_fees
        pnl_pct    = (net_pnl / pos_value * 100) if pos_value else 0.0

        trade = {
            "symbol":          g.symbol,
            "interval":        g.interval,
            "strategy":        strategy.name,
            "trade_type":      trade_type,
            "strategy_mode":   g.mode,
            "entry_candle_ts": position["entry_candle_ts"],
            "entry_ts":        position["entry_ts"],
            "exit_ts":         exec_ts,
            "entry_price":     round(entry, 8),
            "exit_price":      round(exit_exec, 8),
            "position_value":  round(pos_value, 4),
            "gross_pnl":       round(gross_pnl, 4),
            "fees_paid":       round(total_fees, 4),
            "pnl_dollar":      round(net_pnl, 4),
            "pnl_pct":         round(pnl_pct, 4),
            "exit_reason":     exit_reason,
            "leverage_used":   config.LEVERAGE,
        }
        self.db.insert_live_trade(trade)
        self.db.close_live_position(g.symbol, g.interval, strategy.name)

        if g.mode == "portfolio":
            logging.info(
                f"[PORTFOLIO] Position freed — {strategy.name}  "
                f"| {self.portfolio.summary(g.symbol, g.interval)}"
            )

        all_trades = self.db.get_live_trades(g.symbol, g.interval, strategy.name)
        total_net  = sum(t["pnl_dollar"] for t in all_trades)
        n_wins     = sum(1 for t in all_trades if t["pnl_dollar"] > 0)
        outcome    = "TP" if exit_reason == "take_profit" else ("SL" if exit_reason == "stop_loss" else exit_reason.upper())
        emoji      = "✅" if net_pnl > 0 else "❌"
        tag        = g.tag if trade_type == "live" else "[CATCH-UP]"

        msg = (
            f"{tag} PAPER EXIT {g.symbol} [{strategy.name}] {emoji} {outcome}\n"
            f"Entry : ${entry:,.2f}  Exit: ${exit_exec:,.2f}\n"
            f"PnL   : ${net_pnl:+,.2f} ({pnl_pct:+.2f}%)  Fees: ${total_fees:.2f}\n"
            f"Total : ${total_net:+,.2f} from {len(all_trades)} trades ({n_wins} wins)\n"
            f"Time  : {exec_ts}"
        )
        logging.info(f"[WATCHER] {msg.replace(chr(10), '  ')}")
        _safe_send(msg)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _maybe_heartbeat(self) -> None:
        now = datetime.now(timezone.utc)
        if (self._last_heartbeat is None or
                (now - self._last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL):
            self._send_heartbeat()

    def _send_heartbeat(self) -> None:
        now_str   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sections  = []

        for g in self.groups:
            last_ts = self.db.get_last_processed_candle(g.symbol, g.interval)
            lag     = _compute_lag(last_ts)
            lines   = [f"{'PORTFOLIO' if g.mode == 'portfolio' else 'EXPERIMENT'} ({g.symbol} {g.interval}):"]

            trades_all = []
            n_open     = 0
            for s in g.strategies:
                pos = self.db.get_live_position(g.symbol, g.interval, s.name)
                pos_str = f"LONG @ ${pos['entry_price']:,.2f}" if pos else "NONE"
                lines.append(f"  {s.name:<20}: {pos_str}")
                if pos:
                    n_open += 1
                trades_all += self.db.get_live_trades(g.symbol, g.interval, s.name)

            total_net = sum(t["pnl_dollar"] for t in trades_all)
            if g.mode == "portfolio":
                cap_pct = self.portfolio._total_used(g.symbol, g.interval) / config.BACKTEST_CAPITAL * 100
                lines.append(f"  Capital: {cap_pct:.0f}% deployed  Lag: {lag:.0f}s")
            else:
                lines.append(f"  (no capital)  Lag: {lag:.0f}s")
            lines.append(f"  Trades: {len(trades_all)}  PnL: ${total_net:+,.2f}")
            sections.append("\n".join(lines))

            logging.info(
                f"[WATCHER] HEARTBEAT {g.symbol} {g.interval} [{g.mode}] — "
                f"open={n_open}/{len(g.strategies)}  lag={lag:.0f}s  "
                f"trades={len(trades_all)}  pnl=${total_net:+,.2f}"
            )

        msg = f"[BOT ALIVE] {now_str}\n\n" + "\n\n".join(sections)
        _safe_send(msg)
        self._last_heartbeat = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_symbol(self, symbol: str) -> None:
        """Sync all SYNC_INTERVALS for a symbol with retry + backoff."""
        loader = self.loaders[symbol]
        for interval in SYNC_INTERVALS:
            for attempt, wait in enumerate(RETRY_BACKOFF):
                try:
                    loader.sync(symbol=symbol, interval=interval)
                    break
                except Exception as exc:
                    if attempt == len(RETRY_BACKOFF) - 1:
                        logging.info(f"[WATCHER] Binance fetch failed {symbol} {interval} after {MAX_RETRIES} attempts: {exc}")
                    else:
                        logging.info(f"[WATCHER] Binance fetch error {symbol} {interval} (attempt {attempt+1}): {exc} — retrying in {wait}s")
                        time.sleep(wait)

    def _count_trades(self, g: StrategyGroup) -> int:
        return sum(
            len(self.db.get_live_trades(g.symbol, g.interval, s.name))
            for s in g.strategies
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _compute_lag(candle_ts: Optional[str]) -> float:
    if not candle_ts:
        return 0.0
    try:
        ts = datetime.strptime(candle_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except ValueError:
        return 0.0


def _safe_send(msg: str) -> None:
    try:
        send_message(msg)
    except Exception as exc:
        logging.info(f"[WATCHER] Telegram error (non-fatal): {exc}")
