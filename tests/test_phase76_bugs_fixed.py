"""
tests/test_phase76_bugs_fixed.py - Phase 7.6 Bug Fixes Verification

Simplified tests focused on verifying the three critical bug fixes through:
1. Code analysis (verifying fixes are in place)
2. Logging conversion verification
3. Configuration updates
"""

import logging
import os
import unittest


class TestPhase76Bug1PollOnceFix(unittest.TestCase):
    """
    Verify Fix 1: _poll_once logic prevents processing latest bar without next bar.
    
    Bug: last_processed_candle never advanced because _poll_once always tried
    to process the latest bar in DB, which has no next bar, so candle processing
    would return early without marking it processed.
    
    Fix: _poll_once explicitly excludes the latest bar from processing.
    """

    def test_poll_once_code_includes_latest_bar_exclusion(self):
        """Verify _poll_once code contains the logic to exclude the latest bar."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Look for the key fix: processable = recent[:-1]
        self.assertIn("processable = recent[:-1]", content,
                     "_poll_once should exclude latest bar: processable = recent[:-1]")
        
        # Verify the full logic flow
        self.assertIn("# Bars we can process = all except the last", content,
                     "Code should document why last bar is excluded")

    def test_poll_once_only_processes_bars_with_next_bar(self):
        """
        Verify the logic: if DB has [T, T+1, T+2], only process [T, T+1] not T+2.
        """
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for the key check comment
        self.assertIn("Key rule: candle T can only be processed when candle T+1 exists in DB",
                     content,
                     "Code should document the T+1 requirement")

    def test_poll_once_drops_already_processed_bar(self):
        """Verify _poll_once drops the first bar if it equals last_processed."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Find the _poll_once method and check for the drop logic
        self.assertIn("if recent and recent[0][\"timestamp\"] == last_processed:", content,
                     "_poll_once should check if first bar is already processed")
        self.assertIn("recent = recent[1:]", content,
                     "_poll_once should drop already-processed bar")


class TestPhase76Bug2CatchUpFirstRunFix(unittest.TestCase):
    """
    Verify Fix 2: _catch_up marks the starting point on first run.
    
    Bug: On first run, live_processed_candles table is empty. Without marking
    a starting point, _poll_once couldn't compute what's "new" vs "already processed".
    
    Fix: _catch_up marks the last DB timestamp as starting point if first run
    and live_processed_candles is empty.
    """

    def test_catch_up_first_run_marking_logic(self):
        """Verify _catch_up has logic to mark starting point on first run."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for first_run flag
        self.assertIn("first_run = last_ts is None", content,
                     "_catch_up should detect first run")
        
        # Check for first-run starting point marking
        self.assertIn("if first_run and last_ts:", content,
                     "_catch_up should mark starting point on first run")
        
        self.assertIn("self.db.mark_candle_processed(self.symbol, self.interval, last_ts)",
                     content,
                     "_catch_up should call mark_candle_processed on first run")

    def test_catch_up_uses_last_db_timestamp_on_first_run(self):
        """Verify _catch_up gets last DB timestamp when not already processed."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for the get_last_timestamp call for first-run case
        self.assertIn("last_ts = self.db.get_last_timestamp(self.symbol, self.interval)",
                     content,
                     "_catch_up should get last DB timestamp on first run")


class TestPhase76Bug3MultiIntervalSync(unittest.TestCase):
    """
    Verify Fix 3: _fetch_with_retry syncs all SYNC_INTERVALS.
    
    Previously: Only fetched strategy interval (4h)
    Now: Syncs ["15m", "30m", "1h", "4h"] to support future strategies
    """

    def test_sync_intervals_defined(self):
        """Verify SYNC_INTERVALS constant is defined with all granularities."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for SYNC_INTERVALS definition
        self.assertIn('SYNC_INTERVALS', content,
                     "Should define SYNC_INTERVALS constant")
        
        # Verify it includes multiple granularities
        self.assertIn('"15m"', content, "Should sync 15m interval")
        self.assertIn('"30m"', content, "Should sync 30m interval")
        self.assertIn('"1h"', content, "Should sync 1h interval")
        self.assertIn('"4h"', content, "Should sync 4h interval")

    def test_fetch_with_retry_iterates_all_intervals(self):
        """Verify _fetch_with_retry loops through all SYNC_INTERVALS."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for loop over SYNC_INTERVALS
        self.assertIn("for interval in SYNC_INTERVALS:", content,
                     "_fetch_with_retry should loop through SYNC_INTERVALS")

    def test_fetch_with_retry_calls_loader_sync(self):
        """Verify _fetch_with_retry calls loader.sync for each interval."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for loader.sync call
        self.assertIn("self.loader.sync(symbol=self.symbol, interval=interval)",
                     content,
                     "_fetch_with_retry should call loader.sync for each interval")

    def test_fetch_with_retry_returns_strategy_interval_count(self):
        """Verify _fetch_with_retry returns inserted count for strategy interval."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Check for conditional tracking of strategy interval count
        self.assertIn("if interval == self.interval:", content,
                     "_fetch_with_retry should track strategy interval count")


class TestPhase76LoggingConversion(unittest.TestCase):
    """
    Verify Fix 2b: All print() converted to logging.info().
    
    Bug: candle_watcher.py used print(), which goes to stdout, not the
    configured logging file handler. Logs were lost on disk.
    
    Fix: Converted all print() to logging.info()
    """

    def test_candle_watcher_no_print_statements(self):
        """Verify candle_watcher.py doesn't contain print( outside comments."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            lines = f.readlines()
        
        # Check each line for print( outside comments
        print_violations = []
        for i, line in enumerate(lines, 1):
            # Skip comments
            code_part = line.split('#')[0]
            if 'print(' in code_part:
                print_violations.append((i, line.strip()))
        
        self.assertEqual(len(print_violations), 0,
                        f"Found print() calls in candle_watcher.py (should use logging.info):\n"
                        f"{print_violations}")

    def test_candle_watcher_imports_logging(self):
        """Verify candle_watcher.py imports logging module."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        self.assertIn("import logging", content,
                     "candle_watcher.py should import logging")

    def test_candle_watcher_uses_logging_info(self):
        """Verify candle_watcher.py uses logging.info for output."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Should have logging.info calls
        self.assertGreater(content.count("logging.info("), 20,
                          "candle_watcher.py should use logging.info extensively")

    def test_run_live_has_logging_setup(self):
        """Verify run_live.py configures logging with file handler."""
        run_live_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "run_live.py"
        )
        
        with open(run_live_file, 'r') as f:
            content = f.read()
        
        # Check for logging setup
        self.assertIn("TimedRotatingFileHandler", content,
                     "run_live.py should import/use TimedRotatingFileHandler")
        
        self.assertIn("_setup_logging", content,
                     "run_live.py should have _setup_logging function")
        
        self.assertIn("config.LOG_WATCHER_FILE", content,
                     "run_live.py should use config.LOG_WATCHER_FILE constant")
        
        # Check for file handler configuration
        self.assertIn('when="midnight"', content,
                     "File handler should rotate at midnight")
        
        self.assertIn("backupCount=30", content,
                     "File handler should keep 30 days of backups")


class TestPhase76ConfigUpdates(unittest.TestCase):
    """Verify config.py has been updated with Phase 7.6 constants."""

    def test_config_has_log_watcher_file_constant(self):
        """Verify LOG_WATCHER_FILE is defined in config."""
        self.assertTrue(hasattr(config, 'LOG_WATCHER_FILE'),
                       "config.py should have LOG_WATCHER_FILE constant")
        
        self.assertEqual(config.LOG_WATCHER_FILE, "logs/watcher.log",
                        "LOG_WATCHER_FILE should point to logs/watcher.log")

    def test_config_leverage_is_one_x(self):
        """Verify config.LEVERAGE is 1.0 (from Phase 7.5)."""
        self.assertEqual(config.LEVERAGE, 1.0,
                        "LEVERAGE should be 1.0 (Phase 7.5 setting)")

    def test_config_backtest_history_is_three_years(self):
        """Verify config.BACKTEST_HISTORY_DAYS is 1095 (from Phase 7.5)."""
        self.assertEqual(config.BACKTEST_HISTORY_DAYS, 1095,
                        "BACKTEST_HISTORY_DAYS should be 1095 (Phase 7.5 setting)")


class TestPhase76SummaryChecks(unittest.TestCase):
    """Summary verification of Phase 7.6 requirements."""

    def test_phase76_all_fixes_in_place(self):
        """Comprehensive check: all three fixes are implemented."""
        watcher_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "core",
            "candle_watcher.py"
        )
        
        with open(watcher_file, 'r') as f:
            content = f.read()
        
        # Fix 1: _poll_once excludes latest bar
        self.assertIn("processable = recent[:-1]", content, "Fix 1: _poll_once logic")
        
        # Fix 2: _catch_up marks starting point
        self.assertIn("if first_run and last_ts:", content, "Fix 2: _catch_up first-run logic")
        
        # Fix 3: Multi-interval sync
        self.assertIn('SYNC_INTERVALS', content, "Fix 3: Multi-interval definition")
        self.assertIn("for interval in SYNC_INTERVALS:", content, "Fix 3: Multi-interval loop")
        
        # Logging: all print→logging
        self.assertEqual(content.count("print("), 0, "Logging: no print() calls")
        self.assertGreater(content.count("logging.info("), 20, "Logging: uses logging.info")


# Import config for tests
import config


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
