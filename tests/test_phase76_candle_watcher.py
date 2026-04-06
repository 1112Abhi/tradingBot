"""
tests/test_phase76_candle_watcher.py - Phase 7.6 Candle Watcher Bug Fixes

Tests for the three critical fixes:
1. _poll_once: last_processed_candle advancement (exclude last bar without next)
2. _catch_up: First-run initialization (mark starting point in DB)
3. _fetch_with_retry: Multi-interval sync (sync all intervals)
4. Logging: All print() converted to logging.info()
"""

import logging
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import config
from backtest.database import Database
from core.candle_watcher import CandleWatcher, SYNC_INTERVALS


class TestPhase76PollOnceFix(unittest.TestCase):
    """Test Fix 1: _poll_once only processes bars that have a next bar."""

    def setUp(self):
        """Create temporary DB and CandleWatcher instance."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        self.db = Database(db_path=self.temp_db.name)
        self.symbol = "BTCUSDT"
        self.interval = "4h"
        
        # Create watcher (strategy is initialized internally)
        self.watcher = CandleWatcher(
            symbol=self.symbol,
            interval=self.interval,
            db=self.db,
        )

    def tearDown(self):
        """Clean up."""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def _insert_bars(self, timestamps: list) -> None:
        """Insert bars with given timestamps (OHLCV data mocked)."""
        with self.db._connect() as conn:
            for ts in timestamps:
                conn.execute("""
                    INSERT INTO prices 
                    (symbol, interval, timestamp, open, high, low, close, volume, mid)
                    VALUES (?, ?, ?, 100, 101, 99, 100.5, 1000, 100)
                """, (self.symbol, self.interval, ts))
            conn.commit()

    def test_poll_once_processes_only_bars_with_next_bar(self):
        """
        Scenario: last_processed=T, DB has [T, T+1, T+2]
        Expected: Only T+1 is processed (T+2 skipped — no T+3 yet)
        """
        base = datetime(2026, 3, 30, 0, 0, 0, tzinfo=timezone.utc)
        ts_t = base.isoformat(timespec='seconds').replace('+00:00', 'Z')
        ts_t1 = (base + timedelta(hours=4)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        ts_t2 = (base + timedelta(hours=8)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        
        # Insert bars
        self._insert_bars([ts_t, ts_t1, ts_t2])
        
        # Mark T as last processed
        self.db.mark_candle_processed(self.symbol, self.interval, ts_t)
        
        # Mock _fetch_with_retry to return 0 (no new bars)
        self.watcher._fetch_with_retry = MagicMock(return_value=0)
        
        # Mock _process_candle to track calls
        processed_timestamps = []
        original_process = self.watcher._process_candle
        def track_process(ts, trade_type):
            processed_timestamps.append(ts)
            # Don't actually process to avoid DB issues in unit test
        self.watcher._process_candle = track_process
        
        # Run _poll_once
        self.watcher._poll_once()
        
        # Verify only T+1 was processed (not T+2)
        self.assertEqual(processed_timestamps, [ts_t1])

    def test_poll_once_with_single_bar_no_processing(self):
        """
        Scenario: DB has only latest bar (no next bar exists)
        Expected: No bars processed
        """
        base = datetime(2026, 3, 30, 0, 0, 0, tzinfo=timezone.utc)
        ts_latest = base.isoformat(timespec='seconds').replace('+00:00', 'Z')
        
        # Insert single bar
        self._insert_bars([ts_latest])
        
        # Mock _fetch_with_retry
        self.watcher._fetch_with_retry = MagicMock(return_value=0)
        
        # Mock _process_candle
        processed_timestamps = []
        self.watcher._process_candle = lambda ts, trade_type: processed_timestamps.append(ts)
        
        # Run _poll_once (DB has no last_processed, so it should be None)
        self.watcher._poll_once()
        
        # Verify no bars processed
        self.assertEqual(processed_timestamps, [])


class TestPhase76CatchUpFirstRunFix(unittest.TestCase):
    """Test Fix 2: _catch_up marks starting point on first run."""

    def setUp(self):
        """Create temporary DB and CandleWatcher instance."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        self.db = Database(db_path=self.temp_db.name)
        self.symbol = "BTCUSDT"
        self.interval = "4h"
        
        # Create watcher (strategy is initialized internally)
        self.watcher = CandleWatcher(
            symbol=self.symbol,
            interval=self.interval,
            db=self.db,
        )

    def tearDown(self):
        """Clean up."""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def _insert_bars(self, timestamps: list) -> None:
        """Insert bars with given timestamps."""
        with self.db._connect() as conn:
            for ts in timestamps:
                conn.execute("""
                    INSERT INTO prices 
                    (symbol, interval, timestamp, open, high, low, close, volume, mid)
                    VALUES (?, ?, ?, 100, 101, 99, 100.5, 1000, 100)
                """, (self.symbol, self.interval, ts))
            conn.commit()

    def test_first_run_catch_up_marks_starting_point(self):
        """
        Scenario: First run, live_processed_candles is empty, DB has bars
        Expected: Last DB timestamp is marked as processed so _poll_once can detect future candles
        """
        base = datetime(2026, 3, 30, 0, 0, 0, tzinfo=timezone.utc)
        ts_t = base.isoformat(timespec='seconds').replace('+00:00', 'Z')
        ts_t1 = (base + timedelta(hours=4)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        
        # Insert bars
        self._insert_bars([ts_t, ts_t1])
        
        # Verify no last_processed initially (first run)
        last_processed_before = self.db.get_last_processed_candle(self.symbol, self.interval)
        self.assertIsNone(last_processed_before, "Should be no last_processed on first run")
        
        # Mock _fetch_with_retry to return 0
        self.watcher._fetch_with_retry = MagicMock(return_value=0)
        
        # Mock _process_candle (to avoid processing, since there are no missed candles)
        self.watcher._process_candle = MagicMock()
        
        # Run _catch_up
        self.watcher._catch_up()
        
        # Verify last_processed was marked (should be ts_t1, the last in DB)
        last_processed_after = self.db.get_last_processed_candle(self.symbol, self.interval)
        self.assertEqual(last_processed_after, ts_t1, 
                         "First run should mark last DB timestamp as starting point")

    def test_catch_up_with_existing_last_processed(self):
        """
        Scenario: Not first run, last_processed = T, DB has [T, T+1, T+2]
        Expected: Bars T+1 and T+2 are processed, last_processed updated to T+2
        """
        base = datetime(2026, 3, 30, 0, 0, 0, tzinfo=timezone.utc)
        ts_t = base.isoformat(timespec='seconds').replace('+00:00', 'Z')
        ts_t1 = (base + timedelta(hours=4)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        ts_t2 = (base + timedelta(hours=8)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        
        # Insert bars and mark T as last_processed
        self._insert_bars([ts_t, ts_t1, ts_t2])
        self.db.mark_candle_processed(self.symbol, self.interval, ts_t)
        
        # Mock _fetch_with_retry
        self.watcher._fetch_with_retry = MagicMock(return_value=0)
        
        # Track processed bars
        processed = []
        def track_process(ts, trade_type):
            processed.append((ts, trade_type))
            self.db.mark_candle_processed(self.symbol, self.interval, ts)
        self.watcher._process_candle = track_process
        
        # Run _catch_up
        self.watcher._catch_up()
        
        # Verify T+1 and T+2 were processed as catch_up
        self.assertEqual(len(processed), 2)
        self.assertEqual(processed[0][0], ts_t1)
        self.assertEqual(processed[1][0], ts_t2)
        self.assertEqual(processed[0][1], "catch_up")
        self.assertEqual(processed[1][1], "catch_up")


class TestPhase76MultiIntervalSync(unittest.TestCase):
    """Test Fix 3: _fetch_with_retry syncs all SYNC_INTERVALS."""

    def setUp(self):
        """Create temporary DB and CandleWatcher instance."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        self.db = Database(db_path=self.temp_db.name)
        self.symbol = "BTCUSDT"
        self.interval = "4h"
        
        # Create watcher (strategy is initialized internally)
        self.watcher = CandleWatcher(
            symbol=self.symbol,
            interval=self.interval,
            db=self.db,
        )

    def tearDown(self):
        """Clean up."""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_fetch_with_retry_calls_loader_sync_for_all_intervals(self):
        """
        Verify _fetch_with_retry calls loader.sync() for each interval in SYNC_INTERVALS.
        """
        sync_calls = []
        def mock_sync(symbol, interval):
            sync_calls.append((symbol, interval))
            return 1

        self.watcher.loader.sync = mock_sync

        # Call the real _fetch_with_retry
        self.watcher._fetch_with_retry()
        
        # Verify loader.sync was called for each interval in SYNC_INTERVALS
        expected_calls = [(self.symbol, interval) for interval in SYNC_INTERVALS]
        self.assertEqual(sync_calls, expected_calls,
                        f"Expected syncs for {SYNC_INTERVALS}, got {sync_calls}")

    def test_fetch_with_retry_returns_strategy_interval_count(self):
        """
        Verify _fetch_with_retry returns the inserted count for the strategy interval.
        """
        # Mock loader.sync to return different counts per interval
        intervals_to_counts = {
            "15m": 10,
            "30m": 5,
            "1h": 3,
            "4h": 1,  # Strategy interval, should be returned
        }
        
        def mock_sync(symbol, interval):
            return intervals_to_counts.get(interval, 0)
        
        self.watcher.loader.sync = mock_sync
        
        # Call _fetch_with_retry
        from core.candle_watcher import CandleWatcher as RealWatcher
        result = RealWatcher._fetch_with_retry(self.watcher)
        
        # Verify returns count for strategy interval (4h)
        self.assertEqual(result, 1, "Should return inserted count for strategy interval (4h)")


class TestPhase76LoggingConversion(unittest.TestCase):
    """Test Fix 2: All print() converted to logging.info()."""

    def setUp(self):
        """Create temporary DB and CandleWatcher instance."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        self.db = Database(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up."""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_candle_watcher_uses_logging(self):
        """
        Verify candle_watcher.py uses logging.info() instead of print().
        This test reads the source file and checks for print( occurrences.
        """
        import os
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Should not contain print( outside of comments
        lines_with_print = []
        for i, line in enumerate(content.split('\n'), 1):
            # Skip comments
            code_part = line.split('#')[0]
            if 'print(' in code_part:
                lines_with_print.append((i, line.strip()))
        
        self.assertEqual(len(lines_with_print), 0,
                        f"Found print() calls in candle_watcher.py (should use logging):\n"
                        f"{lines_with_print}")

    def test_run_live_has_logging_setup(self):
        """
        Verify run_live.py has _setup_logging() that configures file handler.
        """
        import os
        run_live_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "run_live.py"
        )
        
        with open(run_live_file, 'r') as f:
            content = f.read()
        
        # Check for key logging setup components
        self.assertIn("TimedRotatingFileHandler", content,
                     "run_live.py should import TimedRotatingFileHandler")
        self.assertIn("_setup_logging", content,
                     "run_live.py should define _setup_logging()")
        self.assertIn("config.LOG_WATCHER_FILE", content,
                     "run_live.py should use config.LOG_WATCHER_FILE")


class TestPhase76ConfigUpdated(unittest.TestCase):
    """Test that config.py has LOG_WATCHER_FILE constant."""

    def test_config_has_log_watcher_file(self):
        """Verify LOG_WATCHER_FILE is defined in config."""
        self.assertTrue(hasattr(config, 'LOG_WATCHER_FILE'),
                       "config.py should have LOG_WATCHER_FILE constant")
        self.assertEqual(config.LOG_WATCHER_FILE, "logs/watcher.log",
                        "LOG_WATCHER_FILE should be 'logs/watcher.log'")


class TestPhase76IntegrationScenarios(unittest.TestCase):
    """Integration tests for full Phase 7.6 workflows."""

    def setUp(self):
        """Create temporary DB and CandleWatcher instance."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        self.db = Database(db_path=self.temp_db.name)
        self.symbol = "BTCUSDT"
        self.interval = "4h"
        
        # Create watcher (strategy is initialized internally)
        self.watcher = CandleWatcher(
            symbol=self.symbol,
            interval=self.interval,
            db=self.db,
        )

    def tearDown(self):
        """Clean up."""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def _insert_bars(self, timestamps: list) -> None:
        """Insert bars with given timestamps."""
        with self.db._connect() as conn:
            for ts in timestamps:
                conn.execute("""
                    INSERT INTO prices 
                    (symbol, interval, timestamp, open, high, low, close, volume, mid)
                    VALUES (?, ?, ?, 100, 101, 99, 100.5, 1000, 100)
                """, (self.symbol, self.interval, ts))
            conn.commit()

    def test_first_run_then_poll_workflow(self):
        """
        Integration: First run (catch_up) → poll → new candle arrives → poll processes it.
        """
        base = datetime(2026, 3, 30, 0, 0, 0, tzinfo=timezone.utc)
        
        # ─── First run: DB has T and T+1 ─────────────────────
        ts_t = base.isoformat(timespec='seconds').replace('+00:00', 'Z')
        ts_t1 = (base + timedelta(hours=4)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        self._insert_bars([ts_t, ts_t1])
        
        # Mock _fetch_with_retry
        self.watcher._fetch_with_retry = MagicMock(return_value=0)
        self.watcher._process_candle = MagicMock()
        
        # Run first catch_up
        self.watcher._catch_up()
        
        # Verify last_processed is set to ts_t1 (first-run starting point)
        last_processed = self.db.get_last_processed_candle(self.symbol, self.interval)
        self.assertEqual(last_processed, ts_t1)
        
        # ─── Second poll: T+2 arrives — but needs T+3 to be processable ─
        ts_t2 = (base + timedelta(hours=8)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        self._insert_bars([ts_t2])

        processed_in_poll = []
        def track_process(ts, trade_type):
            processed_in_poll.append((ts, trade_type))
            self.db.mark_candle_processed(self.symbol, self.interval, ts)

        self.watcher._process_candle = track_process
        self.watcher._fetch_with_retry = MagicMock(return_value=1)

        # Run poll_once — T+2 cannot be processed yet (no T+3 exists)
        self.watcher._poll_once()
        self.assertEqual(len(processed_in_poll), 0)

        # ─── Third poll: T+3 arrives — now T+2 can be processed ──────
        ts_t3 = (base + timedelta(hours=12)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        self._insert_bars([ts_t3])
        self.watcher._fetch_with_retry = MagicMock(return_value=1)
        self.watcher._poll_once()

        self.assertEqual(len(processed_in_poll), 1)
        self.assertEqual(processed_in_poll[0][0], ts_t2)
        self.assertEqual(processed_in_poll[0][1], "live")


if __name__ == '__main__':
    # Set up logging to capture logs in tests
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
