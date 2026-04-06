# core/candle_watcher.py - Phase 7.6 Live / Paper Trading Candle Watcher
#
# Design:
#   - On startup: catch up all missed 4h candles since last processed timestamp
#   - Polling loop: check for new completed candle every POLL_INTERVAL_SECS
#   - Each candle processed exactly once (idempotency via live_processed_candles table)
#   - Position state persisted in DB — survives restarts
#   - Telegram: heartbeat every hour + trade entry/exit alerts
#   - Binance fetch: retry with exponential backoff
#   - Telegram failures never crash execution

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import requests

import config
from backtest.database import Database
from backtest.data_loader import DataLoader
from strategy.ema_crossover import MACrossoverStrategy
from strategy.mean_reversion import MeanReversionStrategy
from core.portfolio_state import PortfolioState
from telegram.bot import send_message
from utils.config_loader import load_config

# How often to poll for a new completed candle (seconds)
POLL_INTERVAL_SECS = 300   # 5 min — well within 4h window
HEARTBEAT_INTERVAL = 3600  # 1 hour

# Intervals synced from Binance on every poll (strategy uses STRATEGY_INTERVAL only)
# Storing granular data now allows future strategies without re-fetching history
SYNC_INTERVALS    = ["15m", "30m", "1h", "4h"]

# Retry config for Binance fetches
MAX_RETRIES   = 3
RETRY_BACKOFF = [5, 15, 30]  # seconds between retries


class CandleWatcher:
    """
    Live / paper trading loop for a single symbol + interval.

    Execution matches backtest exactly:
        Signal at candle T → entry at candle T+1 open (mid price)
        SL/TP/timeout logic identical to backtest engine
        Fees and slippage applied the same way
    """

    def __init__(
        self,
        symbol:   str = "BTCUSDT",
        interval: str = "4h",
        db:       Optional[Database] = None,
    ) -> None:
        self.symbol   = symbol
        self.interval = interval
        self.db       = db or Database()
        self.loader   = DataLoader(db=self.db)

        # Load strategy configs from YAML and instantiate
        _ema_cfg = load_config("ema_crossover")
        _mr_cfg  = load_config("mean_reversion")

        self.strategies = [
            MACrossoverStrategy(**_ema_cfg["params"]),
            MeanReversionStrategy(**_mr_cfg["params"]),
        ]

        self.portfolio = PortfolioState(self.db)

        # SL/TP: both strategies share the same risk params (from mean_reversion as reference)
        self._sl_pct = _mr_cfg["risk"]["sl"] / 100
        self._tp_pct = _mr_cfg["risk"]["tp"] / 100

        self._last_heartbeat: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Start the watcher. Catches up missed candles, then polls indefinitely.
        Runs until interrupted (KeyboardInterrupt).
        """
        strategy_names = ", ".join(s.name for s in self.strategies)
        logging.info(f"[WATCHER] Starting — {self.symbol} {self.interval}  strategies=[{strategy_names}]")
        logging.info(f"[WATCHER] SL={self._sl_pct*100:.1f}%  TP={self._tp_pct*100:.1f}%  "
                     f"leverage={config.LEVERAGE}x  fee={config.BACKTEST_FEE_PCT*100:.3f}%  "
                     f"cap_per_strategy={config.PORTFOLIO_PER_STRATEGY_FRACTION*100:.0f}%  "
                     f"cap_total={config.PORTFOLIO_TOTAL_FRACTION*100:.0f}%")

        # Restore open positions from DB for all strategies
        open_positions = self.db.get_all_live_positions(self.symbol, self.interval)
        if open_positions:
            for pos in open_positions:
                logging.info(f"[WATCHER] Restored position: {pos['strategy']}  "
                             f"entry={pos['entry_price']:.2f} at {pos['entry_ts']}")
        else:
            logging.info("[WATCHER] No open positions — starting fresh")

        # Catch up missed candles
        self._catch_up()

        # Send startup heartbeat
        self._send_heartbeat()

        # Poll loop
        try:
            while True:
                self._poll_once()
                self._maybe_heartbeat()
                time.sleep(POLL_INTERVAL_SECS)
        except KeyboardInterrupt:
            logging.info("[WATCHER] Stopped by user")

    # ------------------------------------------------------------------
    # Catch-up on missed candles
    # ------------------------------------------------------------------

    def _catch_up(self) -> None:
        """
        Fetch and process all completed candles since the last processed timestamp.
        Uses the same DataLoader as the backtest pipeline.
        Sends a Telegram summary on completion if any candles were missed.
        """
        last_ts   = self.db.get_last_processed_candle(self.symbol, self.interval)
        first_run = last_ts is None

        if last_ts:
            logging.info(f"[WATCHER] Catching up from {last_ts}")
        else:
            # First ever run — start from what's in the DB
            last_ts = self.db.get_last_timestamp(self.symbol, self.interval)
            logging.info(f"[WATCHER] First run, using last DB timestamp: {last_ts}")

        # Sync latest bars from Binance
        inserted = self._fetch_with_retry()
        if inserted:
            logging.info(f"[WATCHER] Synced {inserted} new bars from Binance")

        # Get all bars after last processed
        bars = self.db.get_prices(self.symbol, self.interval, start=last_ts)

        # Skip the first bar if it equals last_ts (already processed)
        if bars and bars[0]["timestamp"] == last_ts:
            bars = list(bars[1:])

        if not bars:
            logging.info("[WATCHER] No missed candles to process")
            # On first run: mark the starting point so _poll_once can detect future candles
            if first_run and last_ts:
                self.db.mark_candle_processed(self.symbol, self.interval, last_ts)
                logging.info(f"[WATCHER] Starting point marked: {last_ts}")
            return

        n         = len(bars)
        gap_hours = n * 4  # 4h interval
        logging.info(f"[WATCHER] Processing {n} missed candle(s) ({gap_hours}h gap) as catch_up")

        trades_before = sum(
            len(self.db.get_live_trades(self.symbol, self.interval, s.name))
            for s in self.strategies
        )

        for bar in bars:
            self._process_candle(bar["timestamp"], trade_type="catch_up")

        trades_after = sum(
            len(self.db.get_live_trades(self.symbol, self.interval, s.name))
            for s in self.strategies
        )
        new_trades     = trades_after - trades_before
        last_processed = self.db.get_last_processed_candle(self.symbol, self.interval)

        msg = (
            f"[CATCH-UP COMPLETE] {self.symbol} {self.interval}\n"
            f"Candles processed : {n}  ({gap_hours}h gap)\n"
            f"Trades triggered  : {new_trades}\n"
            f"Now up to         : {last_processed}"
        )
        logging.info(f"[WATCHER] {msg.replace(chr(10), '  ')}")
        # Only Telegram-alert if there was a real gap (not first-ever startup)
        if not first_run:
            _safe_send(msg)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll_once(self) -> None:
        """
        Sync Binance and process all unprocessed candles that have a next bar.

        Key rule: candle T can only be processed when candle T+1 exists in DB,
        because T+1's open price is needed for trade execution.
        The latest bar in DB never has a next bar yet — skip it.
        """
        self._fetch_with_retry()

        last_processed = self.db.get_last_processed_candle(self.symbol, self.interval)

        # Load only bars from last_processed onwards (efficient — avoids full scan)
        recent = [dict(b) for b in self.db.get_prices(
            self.symbol, self.interval, start=last_processed
        )]

        # Drop the already-processed bar (first in list equals last_processed)
        if recent and recent[0]["timestamp"] == last_processed:
            recent = recent[1:]

        # Bars we can process = all except the last (which has no next bar yet)
        processable = recent[:-1] if len(recent) >= 2 else []

        if processable:
            logging.info(f"[WATCHER] Processing {len(processable)} new candle(s)")
            for bar in processable:
                lag = self._compute_lag(bar["timestamp"])
                logging.info(f"[WATCHER] Candle {bar['timestamp']}  lag={lag:.0f}s")
                self._process_candle(bar["timestamp"], trade_type="live")
        else:
            logging.info(f"[WATCHER] No new candle — last={last_processed}  "
                         f"lag={self._compute_lag(last_processed):.0f}s")

    # ------------------------------------------------------------------
    # Per-candle logic (mirrors backtest engine exactly)
    # ------------------------------------------------------------------

    def _process_candle(self, candle_ts: str, trade_type: str) -> None:
        """
        Process one completed candle. Idempotent — safe to call twice.

        Signal@candle_ts → execution at NEXT bar open (mid price).
        SL/TP check happens on the NEXT bar (same as backtest).
        """
        # ── Idempotency guard ──────────────────────────────────────────
        if self.db.is_candle_processed(self.symbol, self.interval, candle_ts):
            return

        # ── Load bar window up to and including this candle ───────────
        all_bars = self.db.get_prices(self.symbol, self.interval)
        bar_list = [dict(b) for b in all_bars]

        # Find index of this candle
        idx = next((i for i, b in enumerate(bar_list) if b["timestamp"] == candle_ts), None)
        if idx is None:
            logging.info(f"[WATCHER] Candle {candle_ts} not found in DB — skipping")
            return

        # Need at least BACKTEST_MIN_WINDOW bars before this candle
        if idx < config.BACKTEST_MIN_WINDOW:
            self.db.mark_candle_processed(self.symbol, self.interval, candle_ts)
            return

        # Need a next bar for execution price
        if idx + 1 >= len(bar_list):
            # No next bar yet — will be processed in next poll
            return

        window     = bar_list[:idx + 1]
        exec_bar   = bar_list[idx + 1]
        exec_price = exec_bar["mid"]
        exec_ts    = exec_bar["timestamp"]

        prices = [b["mid"] for b in window]

        from strategy.base import MarketData

        # ── Run each strategy independently on this candle ────────────
        for strategy in self.strategies:
            position = self.db.get_live_position(self.symbol, self.interval, strategy.name)

            market_data: MarketData = {
                "prices":      prices,
                "entry_price": position["entry_price"] if position else None,
                "position":    "LONG" if position else "NONE",
                "symbol":      self.symbol,
                "timestamp":   candle_ts,
                "volumes":     [b["volume"] for b in window],
            }

            try:
                signal = strategy.generate_signal(market_data)
            except Exception as exc:
                logging.info(f"[WATCHER] [{strategy.name}] Strategy error at {candle_ts}: {exc}")
                signal = config.SIGNAL_NO_TRADE

            # ── State machine (identical to engine.py) ─────────────────
            if signal == config.SIGNAL_BUY and not position:
                self._enter_position(
                    candle_ts  = candle_ts,
                    exec_ts    = exec_ts,
                    exec_price = exec_price,
                    prices     = prices,
                    trade_type = trade_type,
                    strategy   = strategy,
                )

            elif position:
                sl_price = position["sl_price"]
                tp_price = position["tp_price"]

                entry_bar_idx = next(
                    (i for i, b in enumerate(bar_list) if b["timestamp"] == position["entry_candle_ts"]),
                    0,
                )
                bars_held = idx - entry_bar_idx

                exit_reason = None
                if exec_price >= tp_price:
                    exit_reason = "take_profit"
                elif exec_price <= sl_price:
                    exit_reason = "stop_loss"
                elif bars_held > 100:
                    exit_reason = "timeout"

                if exit_reason:
                    self._exit_position(
                        position    = position,
                        exec_ts     = exec_ts,
                        exec_price  = exec_price,
                        exit_reason = exit_reason,
                        trade_type  = trade_type,
                        strategy    = strategy,
                    )

        # ── Mark candle done ───────────────────────────────────────────
        self.db.mark_candle_processed(self.symbol, self.interval, candle_ts)

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def _enter_position(
        self,
        candle_ts:  str,
        exec_ts:    str,
        exec_price: float,
        prices:     list,
        trade_type: str,
        strategy,
    ) -> None:
        """Open a new paper position after portfolio guard check. Alerts on Telegram."""
        # Slippage on buy
        entry_price = exec_price * (1 + config.SLIPPAGE_RATE)

        # Fixed position sizing: 25% of capital per strategy (Phase 8.2 finalized)
        capital   = config.BACKTEST_CAPITAL
        pos_value = capital * config.PORTFOLIO_PER_STRATEGY_FRACTION  # $2,500

        # ── Portfolio guard ────────────────────────────────────────────
        allowed, reason = self.portfolio.can_enter(
            self.symbol, self.interval, strategy.name, pos_value
        )
        size_pct      = pos_value / capital * 100
        total_used    = self.portfolio._total_used(self.symbol, self.interval)
        usage_after   = (total_used + pos_value) / capital * 100

        if not allowed:
            logging.info(
                f"[PORTFOLIO] ENTRY REJECTED — {strategy.name} — reason: {reason}"
            )
            return

        logging.info(
            f"[PORTFOLIO] ENTRY ALLOWED — {strategy.name} — "
            f"size: {size_pct:.0f}% (${pos_value:,.0f}) — "
            f"total usage: {usage_after:.0f}%"
        )
        # ──────────────────────────────────────────────────────────────
        # ──────────────────────────────────────────────────────────────

        sl_price = entry_price * (1 - self._sl_pct)
        tp_price = entry_price * (1 + self._tp_pct)

        pos = {
            "symbol":          self.symbol,
            "interval":        self.interval,
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

        tag = "[LIVE]" if trade_type == "live" else "[CATCH-UP]"
        msg = (
            f"{tag} PAPER BUY {self.symbol} [{strategy.name}]\n"
            f"Entry : ${entry_price:,.2f}\n"
            f"SL    : ${sl_price:,.2f} (-{self._sl_pct*100:.1f}%)\n"
            f"TP    : ${tp_price:,.2f} (+{self._tp_pct*100:.1f}%)\n"
            f"Size  : ${pos_value:,.2f}  |  {config.LEVERAGE}x leverage\n"
            f"Time  : {exec_ts}"
        )
        logging.info(f"[WATCHER] {msg.replace(chr(10), '  ')}")
        _safe_send(msg)

    def _exit_position(
        self,
        position:    dict,
        exec_ts:     str,
        exec_price:  float,
        exit_reason: str,
        trade_type:  str,
        strategy,
    ) -> None:
        """Close paper position, log trade, alert on Telegram."""
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
            "symbol":          self.symbol,
            "interval":        self.interval,
            "strategy":        strategy.name,
            "trade_type":      trade_type,
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
        self.db.close_live_position(self.symbol, self.interval, strategy.name)

        logging.info(
            f"[PORTFOLIO] Position freed — {strategy.name}  "
            f"| {self.portfolio.summary(self.symbol, self.interval)}"
        )

        # Running stats for this strategy
        all_trades = self.db.get_live_trades(self.symbol, self.interval, strategy.name)
        total_net  = sum(t["pnl_dollar"] for t in all_trades)
        n_wins     = sum(1 for t in all_trades if t["pnl_dollar"] > 0)

        outcome = "TP" if exit_reason == "take_profit" else ("SL" if exit_reason == "stop_loss" else exit_reason.upper())
        emoji   = "✅" if net_pnl > 0 else "❌"
        tag     = "[LIVE]" if trade_type == "live" else "[CATCH-UP]"
        msg = (
            f"{tag} PAPER EXIT {self.symbol} [{strategy.name}] {emoji} {outcome}\n"
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
        last_ts = self.db.get_last_processed_candle(self.symbol, self.interval)
        lag     = self._compute_lag(last_ts)

        # Aggregate stats across all strategies
        all_trades = []
        pos_lines  = []
        for s in self.strategies:
            pos = self.db.get_live_position(self.symbol, self.interval, s.name)
            pos_str = f"LONG @ ${pos['entry_price']:,.2f}" if pos else "NONE"
            pos_lines.append(f"  {s.name:<20}: {pos_str}")
            all_trades += self.db.get_live_trades(self.symbol, self.interval, s.name)

        total_net   = sum(t["pnl_dollar"] for t in all_trades)
        n_open      = sum(1 for s in self.strategies
                         if self.db.get_live_position(self.symbol, self.interval, s.name))
        capital_pct = self.portfolio._total_used(self.symbol, self.interval) / config.BACKTEST_CAPITAL * 100
        now_str     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        msg = (
            f"[BOT ALIVE] {self.symbol} {self.interval}\n"
            + "\n".join(pos_lines) + "\n"
            f"Open       : {n_open}/{len(self.strategies)} positions  "
            f"Capital: {capital_pct:.0f}% deployed\n"
            f"Last candle: {last_ts or 'none'}  (lag {lag:.0f}s)\n"
            f"Trades     : {len(all_trades)}  PnL: ${total_net:+,.2f}\n"
            f"Time       : {now_str}"
        )
        logging.info(
            f"[WATCHER] HEARTBEAT — open={n_open}/{len(self.strategies)}  "
            f"capital={capital_pct:.0f}%  lag={lag:.0f}s  "
            f"trades={len(all_trades)}  pnl=${total_net:+,.2f}"
        )
        _safe_send(msg)
        self._last_heartbeat = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_with_retry(self) -> int:
        """
        Sync all SYNC_INTERVALS from Binance with retry + backoff.
        Returns inserted count for the strategy interval (used for logging).
        """
        strategy_inserted = 0
        for interval in SYNC_INTERVALS:
            for attempt, wait in enumerate(RETRY_BACKOFF):
                try:
                    inserted = self.loader.sync(symbol=self.symbol, interval=interval)
                    if interval == self.interval:
                        strategy_inserted = inserted
                    break
                except Exception as exc:
                    if attempt == len(RETRY_BACKOFF) - 1:
                        logging.info(f"[WATCHER] Binance fetch failed for {interval} after {MAX_RETRIES} attempts: {exc}")
                    else:
                        logging.info(f"[WATCHER] Binance fetch error {interval} (attempt {attempt+1}): {exc} — retrying in {wait}s")
                        time.sleep(wait)
        return strategy_inserted

    @staticmethod
    def _compute_lag(candle_ts: Optional[str]) -> float:
        """Return seconds between candle_ts and now. 0 if candle_ts is None."""
        if not candle_ts:
            return 0.0
        try:
            ts = datetime.strptime(candle_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - ts).total_seconds()
        except ValueError:
            return 0.0


# ------------------------------------------------------------------
# Module-level helper
# ------------------------------------------------------------------

def _safe_send(msg: str) -> None:
    """Send Telegram message — failures are logged but never crash execution."""
    try:
        send_message(msg)
    except Exception as exc:
        logging.info(f"[WATCHER] Telegram error (non-fatal): {exc}")
