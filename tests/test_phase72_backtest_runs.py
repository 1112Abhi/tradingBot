# tests/test_phase72_backtest_runs.py - Phase 7.2 Backtest Runs & Trades

import pytest
from backtest.database import Database
import config
import tempfile
import os


class TestBacktestRunSchema:
    """Test backtest_runs table schema."""

    def test_schema_creates_runs_table(self, tmp_path):
        """Schema should create backtest_runs table."""
        db = Database(str(tmp_path / "test.db"))
        with db._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_runs'"
            )
            assert cursor.fetchone() is not None

    def test_schema_creates_trades_table(self, tmp_path):
        """Schema should create backtest_trades table."""
        db = Database(str(tmp_path / "test.db"))
        with db._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_trades'"
            )
            assert cursor.fetchone() is not None

    def test_schema_creates_trades_index(self, tmp_path):
        """Schema should create index on run_id in trades table."""
        db = Database(str(tmp_path / "test.db"))
        with db._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_trades_run'"
            )
            assert cursor.fetchone() is not None


class TestInsertRun:
    """Test inserting backtest run summaries."""

    def test_insert_single_run(self, tmp_path):
        """Insert a backtest run summary."""
        db = Database(str(tmp_path / "test.db"))

        metrics = {
            "total_bars": 365,
            "warmup_bars": 20,
            "tradeable_bars": 345,
            "initial_capital": 10000.0,
            "final_capital": 12000.0,
            "total_return_pct": 20.0,
            "total_trades": 10,
            "winning_trades": 6,
            "win_rate_pct": 60.0,
            "max_drawdown_pct": 5.0,
        }

        db.insert_run(
            run_id="run_001",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method="conservative",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-12-31T23:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        # Verify it was inserted
        run = db.get_run("run_001")
        assert run is not None
        assert run["symbol"] == "BTCUSDT"
        assert run["total_return_pct"] == 20.0

    def test_insert_multiple_runs(self, tmp_path):
        """Insert multiple backtest runs."""
        db = Database(str(tmp_path / "test.db"))

        for i in range(3):
            metrics = {
                "total_bars": 365,
                "warmup_bars": 20,
                "tradeable_bars": 345,
                "initial_capital": 10000.0,
                "final_capital": 10000.0 + i * 1000,
                "total_return_pct": i * 10.0,
                "total_trades": 10,
                "winning_trades": 6,
                "win_rate_pct": 60.0,
                "max_drawdown_pct": 5.0,
            }

            db.insert_run(
                run_id=f"run_{i:03d}",
                symbol="BTCUSDT",
                interval="1h",
                strategy="ema_crossover",
                aggregation_method=None,
                start_date="2024-01-01T00:00:00Z",
                end_date="2024-12-31T23:00:00Z",
                metrics=metrics,
                fee_pct=0.001,
            )

        # Verify all were inserted
        for i in range(3):
            run = db.get_run(f"run_{i:03d}")
            assert run is not None


class TestGetRun:
    """Test retrieving backtest runs."""

    def test_get_run_exists(self, tmp_path):
        """Retrieve an existing backtest run."""
        db = Database(str(tmp_path / "test.db"))

        metrics = {
            "total_bars": 365,
            "warmup_bars": 20,
            "tradeable_bars": 345,
            "initial_capital": 10000.0,
            "final_capital": 12500.0,
            "total_return_pct": 25.0,
            "total_trades": 15,
            "winning_trades": 9,
            "win_rate_pct": 60.0,
            "max_drawdown_pct": 8.0,
        }

        db.insert_run(
            run_id="test_run",
            symbol="ETHUSDT",
            interval="4h",
            strategy="rsi",
            aggregation_method="weighted",
            start_date="2024-06-01T00:00:00Z",
            end_date="2024-12-31T00:00:00Z",
            metrics=metrics,
            fee_pct=0.002,
        )

        run = db.get_run("test_run")
        assert run["run_id"] == "test_run"
        assert run["symbol"] == "ETHUSDT"
        assert run["interval"] == "4h"
        assert run["total_return_pct"] == 25.0
        assert run["winning_trades"] == 9

    def test_get_run_not_exists(self, tmp_path):
        """Get non-existent run returns None."""
        db = Database(str(tmp_path / "test.db"))
        run = db.get_run("nonexistent")
        assert run is None


class TestInsertTrade:
    """Test inserting individual trades."""

    def test_insert_single_trade(self, tmp_path):
        """Insert a single trade record."""
        db = Database(str(tmp_path / "test.db"))

        # Create a run first
        metrics = {
            "total_bars": 100,
            "warmup_bars": 20,
            "tradeable_bars": 80,
            "initial_capital": 10000.0,
            "final_capital": 10500.0,
            "total_return_pct": 5.0,
            "total_trades": 1,
            "winning_trades": 1,
            "win_rate_pct": 100.0,
            "max_drawdown_pct": 2.0,
        }

        db.insert_run(
            run_id="run_trade_test",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method=None,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-04T00:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        # Insert a trade
        trade = {
            "trade_num": 1,
            "entry_ts": "2024-01-01T10:00:00Z",
            "exit_ts": "2024-01-02T15:00:00Z",
            "entry_price": 42000.0,
            "exit_price": 43000.0,
            "pnl_dollar": 1000.0,
            "pnl_pct": 2.38,
            "exit_reason": "crossover",
        }

        db.insert_trade("run_trade_test", trade)

        # Verify
        trades = db.get_trades("run_trade_test")
        assert len(trades) == 1
        assert trades[0]["entry_price"] == 42000.0

    def test_insert_multiple_trades(self, tmp_path):
        """Insert multiple trades for same run."""
        db = Database(str(tmp_path / "test.db"))

        # Create a run
        metrics = {
            "total_bars": 365,
            "warmup_bars": 20,
            "tradeable_bars": 345,
            "initial_capital": 10000.0,
            "final_capital": 11500.0,
            "total_return_pct": 15.0,
            "total_trades": 3,
            "winning_trades": 2,
            "win_rate_pct": 66.67,
            "max_drawdown_pct": 5.0,
        }

        db.insert_run(
            run_id="run_multi_trade",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method=None,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-12-31T00:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        # Insert multiple trades
        for i in range(3):
            trade = {
                "trade_num": i + 1,
                "entry_ts": f"2024-01-{i+1:02d}T10:00:00Z",
                "exit_ts": f"2024-01-{i+2:02d}T15:00:00Z",
                "entry_price": 42000.0 + i * 500,
                "exit_price": 42500.0 + i * 500,
                "pnl_dollar": 500.0 if i < 2 else -300.0,
                "pnl_pct": 1.19 if i < 2 else -0.71,
                "exit_reason": "crossover" if i < 2 else "stoploss",
            }
            db.insert_trade("run_multi_trade", trade)

        # Verify
        trades = db.get_trades("run_multi_trade")
        assert len(trades) == 3


class TestGetTrades:
    """Test retrieving trades for a run."""

    def test_get_trades_ordered(self, tmp_path):
        """Trades should be returned in trade_num order."""
        db = Database(str(tmp_path / "test.db"))

        # Create run
        metrics = {
            "total_bars": 100,
            "warmup_bars": 20,
            "tradeable_bars": 80,
            "initial_capital": 10000.0,
            "final_capital": 10000.0,
            "total_return_pct": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }

        db.insert_run(
            run_id="order_test",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method=None,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-05T00:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        # Insert trades out of order
        for trade_num in [3, 1, 2]:
            trade = {
                "trade_num": trade_num,
                "entry_ts": "2024-01-01T10:00:00Z",
                "exit_ts": "2024-01-02T10:00:00Z",
                "entry_price": 42000.0,
                "exit_price": 42100.0,
                "pnl_dollar": 100.0,
                "pnl_pct": 0.24,
                "exit_reason": "crossover",
            }
            db.insert_trade("order_test", trade)

        # Verify they're ordered by trade_num
        trades = db.get_trades("order_test")
        trade_nums = [t["trade_num"] for t in trades]
        assert trade_nums == [1, 2, 3]

    def test_get_trades_empty_run(self, tmp_path):
        """Get trades for run with no trades."""
        db = Database(str(tmp_path / "test.db"))

        # Create run with no trades
        metrics = {
            "total_bars": 100,
            "warmup_bars": 20,
            "tradeable_bars": 80,
            "initial_capital": 10000.0,
            "final_capital": 10000.0,
            "total_return_pct": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }

        db.insert_run(
            run_id="no_trades",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method=None,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-05T00:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        trades = db.get_trades("no_trades")
        assert trades == []

    def test_get_trades_nonexistent_run(self, tmp_path):
        """Get trades for non-existent run."""
        db = Database(str(tmp_path / "test.db"))
        trades = db.get_trades("nonexistent")
        assert trades == []


class TestRunMetrics:
    """Test storing and retrieving backtest metrics."""

    def test_metrics_preserved(self, tmp_path):
        """All metrics should be preserved when stored and retrieved."""
        db = Database(str(tmp_path / "test.db"))

        metrics = {
            "total_bars": 500,
            "warmup_bars": 50,
            "tradeable_bars": 450,
            "initial_capital": 50000.0,
            "final_capital": 65000.0,
            "total_return_pct": 30.0,
            "total_trades": 25,
            "winning_trades": 16,
            "win_rate_pct": 64.0,
            "max_drawdown_pct": 12.5,
        }

        db.insert_run(
            run_id="metrics_test",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method="conservative",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-12-31T23:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        run = db.get_run("metrics_test")
        assert run["total_bars"] == 500
        assert run["warmup_bars"] == 50
        assert run["tradeable_bars"] == 450
        assert run["initial_capital"] == 50000.0
        assert run["final_capital"] == 65000.0
        assert run["total_return_pct"] == 30.0
        assert run["total_trades"] == 25
        assert run["winning_trades"] == 16
        assert run["win_rate_pct"] == 64.0
        assert run["max_drawdown_pct"] == 12.5


class TestTradeDetails:
    """Test storing and retrieving trade details."""

    def test_trade_details_preserved(self, tmp_path):
        """All trade details should be preserved."""
        db = Database(str(tmp_path / "test.db"))

        # Create run
        metrics = {
            "total_bars": 100,
            "warmup_bars": 20,
            "tradeable_bars": 80,
            "initial_capital": 10000.0,
            "final_capital": 10000.0,
            "total_return_pct": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }

        db.insert_run(
            run_id="trade_detail_test",
            symbol="BTCUSDT",
            interval="1h",
            strategy="ema_crossover",
            aggregation_method=None,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-05T00:00:00Z",
            metrics=metrics,
            fee_pct=0.001,
        )

        trade = {
            "trade_num": 1,
            "entry_ts": "2024-01-01T10:30:45Z",
            "exit_ts": "2024-01-02T14:15:30Z",
            "entry_price": 42123.45,
            "exit_price": 43567.89,
            "pnl_dollar": 1444.44,
            "pnl_pct": 3.43,
            "exit_reason": "take_profit",
        }

        db.insert_trade("trade_detail_test", trade)

        trades = db.get_trades("trade_detail_test")
        assert len(trades) == 1
        t = trades[0]
        assert t["entry_ts"] == "2024-01-01T10:30:45Z"
        assert t["exit_ts"] == "2024-01-02T14:15:30Z"
        assert t["entry_price"] == 42123.45
        assert t["exit_price"] == 43567.89
        assert t["pnl_dollar"] == 1444.44
        assert t["pnl_pct"] == 3.43
        assert t["exit_reason"] == "take_profit"


class TestConfigPhase72:
    """Test Phase 7.2 configuration constants."""

    def test_position_size_fraction_valid(self):
        """POSITION_SIZE_FRACTION should be between 0 and 1."""
        assert 0 < config.POSITION_SIZE_FRACTION <= 1
        assert isinstance(config.POSITION_SIZE_FRACTION, float)

    def test_backtest_min_window_positive(self):
        """BACKTEST_MIN_WINDOW should be positive."""
        assert isinstance(config.BACKTEST_MIN_WINDOW, int)
        assert config.BACKTEST_MIN_WINDOW > 0

    def test_backtest_min_window_reasonable(self):
        """BACKTEST_MIN_WINDOW should be >= SLOW_PERIOD + 1."""
        assert config.BACKTEST_MIN_WINDOW >= config.SLOW_PERIOD + 1
