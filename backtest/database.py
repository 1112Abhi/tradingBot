# backtest/database.py - SQLite Data Layer

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, List, Optional

import config


class Database:
    """
    SQLite wrapper for all backtest and live trading data.

    Tables (7.1):
        prices — historical OHLCV bars with precomputed mid price

    Tables (7.2):
        backtest_runs, backtest_trades

    Tables (7.6):
        live_processed_candles — idempotency log (one row per processed candle)
        live_position          — current open paper position (at most one row)
        live_trades            — completed paper trades
    """

    def __init__(self, db_path: str = config.BACKTEST_DB) -> None:
        self.db_path = db_path
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS prices (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol    TEXT    NOT NULL,
                    interval  TEXT    NOT NULL,
                    timestamp TEXT    NOT NULL,
                    open      REAL    NOT NULL,
                    high      REAL    NOT NULL,
                    low       REAL    NOT NULL,
                    close     REAL    NOT NULL,
                    volume    REAL    NOT NULL,
                    mid       REAL    NOT NULL,
                    UNIQUE(symbol, interval, timestamp)
                );

                CREATE INDEX IF NOT EXISTS idx_prices_lookup
                    ON prices(symbol, interval, timestamp);

                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id             TEXT    NOT NULL UNIQUE,
                    symbol             TEXT    NOT NULL,
                    interval           TEXT    NOT NULL,
                    strategy           TEXT    NOT NULL,
                    aggregation_method TEXT,
                    start_date         TEXT    NOT NULL,
                    end_date           TEXT    NOT NULL,
                    total_bars         INTEGER NOT NULL,
                    warmup_bars        INTEGER NOT NULL,
                    tradeable_bars     INTEGER NOT NULL,
                    initial_capital    REAL    NOT NULL,
                    final_capital      REAL    NOT NULL,
                    total_return_pct   REAL    NOT NULL,
                    total_trades       INTEGER NOT NULL,
                    winning_trades     INTEGER NOT NULL,
                    win_rate_pct       REAL    NOT NULL,
                    max_drawdown_pct   REAL    NOT NULL,
                    fee_pct            REAL    NOT NULL,
                    created_at         TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id       TEXT    NOT NULL REFERENCES backtest_runs(run_id),
                    trade_num    INTEGER NOT NULL,
                    entry_ts     TEXT    NOT NULL,
                    exit_ts      TEXT    NOT NULL,
                    entry_price  REAL    NOT NULL,
                    exit_price   REAL    NOT NULL,
                    pnl_dollar   REAL    NOT NULL,
                    pnl_pct      REAL    NOT NULL,
                    exit_reason  TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_trades_run
                    ON backtest_trades(run_id);
            """)
            # Phase 7.6: live trading tables
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS live_processed_candles (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol     TEXT    NOT NULL,
                    interval   TEXT    NOT NULL,
                    candle_ts  TEXT    NOT NULL,
                    processed_at TEXT  NOT NULL,
                    UNIQUE(symbol, interval, candle_ts)
                );

                CREATE TABLE IF NOT EXISTS live_position (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol         TEXT    NOT NULL,
                    interval       TEXT    NOT NULL,
                    strategy       TEXT    NOT NULL,
                    entry_candle_ts TEXT   NOT NULL,
                    entry_ts       TEXT    NOT NULL,
                    entry_price    REAL    NOT NULL,
                    position_value REAL    NOT NULL,
                    sl_price       REAL    NOT NULL,
                    tp_price       REAL    NOT NULL,
                    status         TEXT    NOT NULL DEFAULT 'OPEN',
                    trade_type     TEXT    NOT NULL,
                    UNIQUE(symbol, interval, strategy)
                );

                CREATE TABLE IF NOT EXISTS live_trades (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol          TEXT    NOT NULL,
                    interval        TEXT    NOT NULL,
                    strategy        TEXT    NOT NULL,
                    trade_type      TEXT    NOT NULL,
                    entry_candle_ts TEXT    NOT NULL,
                    entry_ts        TEXT    NOT NULL,
                    exit_ts         TEXT    NOT NULL,
                    entry_price     REAL    NOT NULL,
                    exit_price      REAL    NOT NULL,
                    position_value  REAL    NOT NULL,
                    gross_pnl       REAL    NOT NULL,
                    fees_paid       REAL    NOT NULL,
                    pnl_dollar      REAL    NOT NULL,
                    pnl_pct         REAL    NOT NULL,
                    exit_reason     TEXT    NOT NULL,
                    leverage_used   REAL    NOT NULL,
                    created_at      TEXT    NOT NULL,
                    UNIQUE(symbol, interval, strategy, entry_candle_ts)
                );

                CREATE INDEX IF NOT EXISTS idx_live_trades_symbol
                    ON live_trades(symbol, interval, strategy);
            """)

            # Migrations: add columns introduced after initial schema
            for migration in [
                "ALTER TABLE backtest_runs    ADD COLUMN sharpe_ratio    REAL DEFAULT 0.0",
                "ALTER TABLE backtest_runs    ADD COLUMN gross_pnl       REAL DEFAULT 0.0",
                "ALTER TABLE backtest_runs    ADD COLUMN total_fees_paid REAL DEFAULT 0.0",
                "ALTER TABLE backtest_trades  ADD COLUMN gross_pnl       REAL DEFAULT 0.0",
                "ALTER TABLE backtest_trades  ADD COLUMN fees_paid       REAL DEFAULT 0.0",
                "ALTER TABLE backtest_trades  ADD COLUMN leverage_used   REAL DEFAULT 1.0",
                "ALTER TABLE live_trades      ADD COLUMN strategy_mode   TEXT DEFAULT 'portfolio'",
            ]:
                try:
                    conn.execute(migration)
                except Exception:
                    pass  # Column already exists


    # ------------------------------------------------------------------
    # Price data — write
    # ------------------------------------------------------------------

    def insert_prices(self, rows: List[dict]) -> int:
        """
        Bulk insert price rows. Silently skips duplicates (INSERT OR IGNORE).

        Args:
            rows: List of dicts with keys:
                  symbol, interval, timestamp, open, high, low,
                  close, volume, mid

        Returns:
            Number of newly inserted rows.
        """
        if not rows:
            return 0

        sql = """
            INSERT OR IGNORE INTO prices
                (symbol, interval, timestamp, open, high, low, close, volume, mid)
            VALUES
                (:symbol, :interval, :timestamp, :open, :high, :low,
                 :close, :volume, :mid)
        """
        with self._connect() as conn:
            before = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            conn.executemany(sql, rows)
            after = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        return after - before

    # ------------------------------------------------------------------
    # Price data — read
    # ------------------------------------------------------------------

    def get_prices(
        self,
        symbol: str,
        interval: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        """
        Fetch price rows ordered oldest → newest.

        Args:
            symbol:   e.g. "BTCUSDT"
            interval: e.g. "1h"
            start:    ISO 8601 lower bound (inclusive), optional
            end:      ISO 8601 upper bound (inclusive), optional

        Returns:
            List of sqlite3.Row with all price columns.
        """
        sql  = "SELECT * FROM prices WHERE symbol=? AND interval=?"
        args: list = [symbol, interval]

        if start:
            sql += " AND timestamp >= ?"
            args.append(start)
        if end:
            sql += " AND timestamp <= ?"
            args.append(end)

        sql += " ORDER BY timestamp ASC"

        with self._connect() as conn:
            return conn.execute(sql, args).fetchall()

    def get_last_timestamp(self, symbol: str, interval: str) -> Optional[str]:
        """
        Return the most recent stored timestamp for a symbol+interval pair.
        Returns None if no data exists yet.
        """
        sql = """
            SELECT MAX(timestamp) FROM prices
            WHERE symbol=? AND interval=?
        """
        with self._connect() as conn:
            row = conn.execute(sql, [symbol, interval]).fetchone()
        return row[0] if row else None

    def count_prices(self, symbol: str, interval: str) -> int:
        """Return total stored bar count for a symbol+interval."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM prices WHERE symbol=? AND interval=?",
                [symbol, interval],
            ).fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Phase 7.2: Backtest runs and trades
    # ------------------------------------------------------------------

    def insert_run(
        self,
        run_id: str,
        symbol: str,
        interval: str,
        strategy: str,
        aggregation_method: Optional[str],
        start_date: str,
        end_date: str,
        metrics: dict,
        fee_pct: float,
    ) -> None:
        """
        Persist a completed backtest run summary.

        Args:
            run_id: Unique identifier for this run
            symbol: Trading pair (e.g. "BTCUSDT")
            interval: Candle interval (e.g. "1h")
            strategy: Strategy name
            aggregation_method: Aggregation method used (if multi-strategy)
            start_date: ISO 8601 start date
            end_date: ISO 8601 end date
            metrics: Dict with keys: total_bars, warmup_bars, tradeable_bars,
                     initial_capital, final_capital, total_return_pct,
                     total_trades, winning_trades, win_rate_pct, max_drawdown_pct
            fee_pct: Fee percentage
        """
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sql = """
            INSERT INTO backtest_runs (
                run_id, symbol, interval, strategy, aggregation_method,
                start_date, end_date, total_bars, warmup_bars, tradeable_bars,
                initial_capital, final_capital, gross_pnl, total_fees_paid,
                total_return_pct, total_trades, winning_trades, win_rate_pct,
                max_drawdown_pct, sharpe_ratio, fee_pct, created_at
            ) VALUES (
                :run_id, :symbol, :interval, :strategy, :aggregation_method,
                :start_date, :end_date, :total_bars, :warmup_bars, :tradeable_bars,
                :initial_capital, :final_capital, :gross_pnl, :total_fees_paid,
                :total_return_pct, :total_trades, :winning_trades, :win_rate_pct,
                :max_drawdown_pct, :sharpe_ratio, :fee_pct, :created_at
            )
        """
        with self._connect() as conn:
            conn.execute(sql, {
                "run_id":             run_id,
                "symbol":             symbol,
                "interval":           interval,
                "strategy":           strategy,
                "aggregation_method": aggregation_method,
                "start_date":         start_date,
                "end_date":           end_date,
                **metrics,
                # Defaults for columns added in later phases (backward compat)
                "sharpe_ratio":       metrics.get("sharpe_ratio",    0.0),
                "gross_pnl":          metrics.get("gross_pnl",       0.0),
                "total_fees_paid":    metrics.get("total_fees_paid",  0.0),
                "fee_pct":            fee_pct,
                "created_at":         created_at,
            })

    def insert_trade(self, run_id: str, trade: dict) -> None:
        """
        Persist a single trade record.

        Args:
            run_id: Run identifier (foreign key to backtest_runs)
            trade: Dict with keys: trade_num, entry_ts, exit_ts, entry_price,
                   exit_price, pnl_dollar, pnl_pct, exit_reason
        """
        sql = """
            INSERT INTO backtest_trades
                (run_id, trade_num, entry_ts, exit_ts, entry_price,
                 exit_price, gross_pnl, fees_paid, pnl_dollar, pnl_pct,
                 exit_reason, leverage_used)
            VALUES
                (:run_id, :trade_num, :entry_ts, :exit_ts, :entry_price,
                 :exit_price, :gross_pnl, :fees_paid, :pnl_dollar, :pnl_pct,
                 :exit_reason, :leverage_used)
        """
        row = {
            "run_id":        run_id,
            "gross_pnl":     trade.get("gross_pnl",     0.0),
            "fees_paid":     trade.get("fees_paid",      0.0),
            "leverage_used": trade.get("leverage_used",  1.0),
            **trade,
        }
        with self._connect() as conn:
            conn.execute(sql, row)

    def get_run(self, run_id: str) -> Optional[dict]:
        """
        Retrieve a backtest run summary by run_id.

        Returns: Dict with run details or None if not found
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE run_id=?", [run_id]
            ).fetchone()
        return dict(row) if row else None

    def get_trades(self, run_id: str) -> List[dict]:
        """
        Retrieve all trades for a given run_id, ordered by trade_num.

        Returns: List of trade dicts
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backtest_trades WHERE run_id=? ORDER BY trade_num",
                [run_id]
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase 7.6: Live / Paper Trading
    # ------------------------------------------------------------------

    def is_candle_processed(self, symbol: str, interval: str, candle_ts: str) -> bool:
        """Return True if this candle has already been processed (idempotency check)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM live_processed_candles WHERE symbol=? AND interval=? AND candle_ts=?",
                [symbol, interval, candle_ts],
            ).fetchone()
        return row is not None

    def mark_candle_processed(self, symbol: str, interval: str, candle_ts: str) -> None:
        """Record a candle as processed. Silently ignores duplicates."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO live_processed_candles
                   (symbol, interval, candle_ts, processed_at) VALUES (?,?,?,?)""",
                [symbol, interval, candle_ts, now],
            )

    def get_last_processed_candle(self, symbol: str, interval: str) -> Optional[str]:
        """Return timestamp of the most recently processed candle, or None."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT MAX(candle_ts) FROM live_processed_candles
                   WHERE symbol=? AND interval=?""",
                [symbol, interval],
            ).fetchone()
        return row[0] if row else None

    def open_live_position(self, pos: dict) -> None:
        """
        Persist a newly opened paper position.

        Args:
            pos: Dict with keys: symbol, interval, strategy, entry_candle_ts,
                 entry_ts, entry_price, position_value, sl_price, tp_price,
                 trade_type
        """
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO live_position
                   (symbol, interval, strategy, entry_candle_ts, entry_ts,
                    entry_price, position_value, sl_price, tp_price, status, trade_type)
                   VALUES
                   (:symbol, :interval, :strategy, :entry_candle_ts, :entry_ts,
                    :entry_price, :position_value, :sl_price, :tp_price, 'OPEN', :trade_type)
                """,
                pos,
            )

    def get_live_position(self, symbol: str, interval: str, strategy: str) -> Optional[dict]:
        """Return the current open position for symbol/interval/strategy, or None."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM live_position
                   WHERE symbol=? AND interval=? AND strategy=? AND status='OPEN'""",
                [symbol, interval, strategy],
            ).fetchone()
        return dict(row) if row else None

    def get_all_live_positions(self, symbol: str, interval: str) -> List[dict]:
        """Return all open positions for symbol/interval across all strategies."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM live_position
                   WHERE symbol=? AND interval=? AND status='OPEN'""",
                [symbol, interval],
            ).fetchall()
        return [dict(r) for r in rows]

    def close_live_position(self, symbol: str, interval: str, strategy: str) -> None:
        """Mark the current open position as CLOSED."""
        with self._connect() as conn:
            conn.execute(
                """UPDATE live_position SET status='CLOSED'
                   WHERE symbol=? AND interval=? AND strategy=? AND status='OPEN'""",
                [symbol, interval, strategy],
            )

    def insert_live_trade(self, trade: dict) -> None:
        """
        Persist a completed paper trade. Silently ignores duplicates (idempotent).

        Args:
            trade: Dict with keys: symbol, interval, strategy, trade_type,
                   entry_candle_ts, entry_ts, exit_ts, entry_price, exit_price,
                   position_value, gross_pnl, fees_paid, pnl_dollar, pnl_pct,
                   exit_reason, leverage_used, strategy_mode (optional, default 'portfolio')
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO live_trades
                   (symbol, interval, strategy, trade_type,
                    entry_candle_ts, entry_ts, exit_ts,
                    entry_price, exit_price, position_value,
                    gross_pnl, fees_paid, pnl_dollar, pnl_pct,
                    exit_reason, leverage_used, strategy_mode, created_at)
                   VALUES
                   (:symbol, :interval, :strategy, :trade_type,
                    :entry_candle_ts, :entry_ts, :exit_ts,
                    :entry_price, :exit_price, :position_value,
                    :gross_pnl, :fees_paid, :pnl_dollar, :pnl_pct,
                    :exit_reason, :leverage_used, :strategy_mode, :created_at)
                """,
                {**trade, "strategy_mode": trade.get("strategy_mode", "portfolio"), "created_at": now},
            )

    def get_all_open_positions(self) -> List[dict]:
        """Return all open positions across all symbols and strategies."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM live_position WHERE status='OPEN' ORDER BY entry_ts ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_live_trades(self, limit: int = 10) -> List[dict]:
        """Return the most recent completed live trades across all symbols/strategies."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM live_trades
                   ORDER BY exit_ts DESC LIMIT ?""",
                [limit],
            ).fetchall()
        return [dict(r) for r in rows]

    def get_live_trades(
        self,
        symbol: str,
        interval: str,
        strategy: str,
        trade_type: Optional[str] = None,
    ) -> List[dict]:
        """
        Retrieve completed paper trades, newest first.

        Args:
            trade_type: Filter to "live" or "catch_up"; None returns all.
        """
        sql  = """SELECT * FROM live_trades
                  WHERE symbol=? AND interval=? AND strategy=?"""
        args: list = [symbol, interval, strategy]
        if trade_type:
            sql += " AND trade_type=?"
            args.append(trade_type)
        sql += " ORDER BY entry_ts ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
