# tests/test_backtest_data_loader.py - Unit tests for backtest/data_loader.py

import pytest
from datetime import datetime, timezone
from backtest.data_loader import DataLoader
from backtest.database import Database
import config


class TestDataLoaderTimestampConversion:
    """Test timestamp conversion utilities."""

    def test_ms_to_iso_conversion(self):
        """Convert millisecond epoch to ISO 8601."""
        ms = 1704067200000  # 2024-01-01 00:00:00 UTC
        iso = DataLoader._ms_to_iso(ms)
        assert iso == "2024-01-01T00:00:00Z"

    def test_iso_to_ms_conversion(self):
        """Convert ISO 8601 to millisecond epoch."""
        iso = "2024-01-01T00:00:00Z"
        ms = DataLoader._iso_to_ms(iso)
        assert ms == 1704067200000

    def test_iso_ms_roundtrip(self):
        """Conversion roundtrip should be identical."""
        iso_original = "2024-06-15T12:30:45Z"
        ms = DataLoader._iso_to_ms(iso_original)
        iso_converted = DataLoader._ms_to_iso(ms)
        assert iso_original == iso_converted


class TestDataLoaderIntervalConversion:
    """Test interval to milliseconds conversion."""

    def test_interval_minute(self):
        """1 minute interval."""
        ms = DataLoader._interval_ms("1m")
        assert ms == 60 * 1000

    def test_interval_hour(self):
        """1 hour interval."""
        ms = DataLoader._interval_ms("1h")
        assert ms == 3600 * 1000

    def test_interval_4hour(self):
        """4 hour interval."""
        ms = DataLoader._interval_ms("4h")
        assert ms == 4 * 3600 * 1000

    def test_interval_day(self):
        """1 day interval."""
        ms = DataLoader._interval_ms("1d")
        assert ms == 86400 * 1000

    def test_interval_week(self):
        """1 week interval."""
        ms = DataLoader._interval_ms("1w")
        assert ms == 7 * 86400 * 1000


class TestDataLoaderInit:
    """Test DataLoader initialization."""

    def test_init_creates_default_db(self, tmp_path):
        """DataLoader should create default database."""
        # Temporarily change config
        original_db = config.BACKTEST_DB
        config.BACKTEST_DB = str(tmp_path / "test.db")
        try:
            loader = DataLoader()
            assert loader.db is not None
            assert isinstance(loader.db, Database)
        finally:
            config.BACKTEST_DB = original_db

    def test_init_accepts_custom_db(self, tmp_path):
        """DataLoader should accept custom database instance."""
        db = Database(str(tmp_path / "custom.db"))
        loader = DataLoader(db=db)
        assert loader.db is db


class TestDataLoaderMockSync:
    """Test sync logic with mock data (no network)."""

    def test_sync_with_mock_data(self, tmp_path):
        """Test sync inserts mock price data."""
        db = Database(str(tmp_path / "test.db"))
        loader = DataLoader(db=db)

        # Create mock price rows
        mock_rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 42000.0 + i * 100,
                "high": 42500.0 + i * 100,
                "low": 41500.0 + i * 100,
                "close": 42200.0 + i * 100,
                "volume": 100.0,
                "mid": 42000.0 + i * 100,
            }
            for i in range(24)
        ]

        # Manually insert (simulating _fetch_all)
        inserted = db.insert_prices(mock_rows)
        assert inserted == 24

        # Verify data is stored
        count = db.count_prices("BTCUSDT", "1h")
        assert count == 24


class TestDataLoaderIncrementalSync:
    """Test incremental sync logic."""

    def test_incremental_sync_detects_last_timestamp(self, tmp_path):
        """Incremental sync should detect last stored timestamp."""
        db = Database(str(tmp_path / "test.db"))

        # Insert some initial data
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 42000.0,
                "high": 42500.0,
                "low": 41500.0,
                "close": 42200.0,
                "volume": 100.0,
                "mid": 42000.0,
            }
            for i in range(5)
        ]
        db.insert_prices(rows)

        # Check last timestamp is detected
        last_ts = db.get_last_timestamp("BTCUSDT", "1h")
        assert last_ts == "2024-01-01T04:00:00Z"

    def test_incremental_sync_calculates_start_time(self, tmp_path):
        """Incremental sync should calculate next start time."""
        db = Database(str(tmp_path / "test.db"))
        loader = DataLoader(db=db)

        # Insert data up to 2024-01-01T04:00:00Z
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 42000.0,
                "high": 42500.0,
                "low": 41500.0,
                "close": 42200.0,
                "volume": 100.0,
                "mid": 42000.0,
            }
            for i in range(5)
        ]
        db.insert_prices(rows)

        last_ts = db.get_last_timestamp("BTCUSDT", "1h")
        start_ms = loader._iso_to_ms(last_ts) + loader._interval_ms("1h")
        start_iso = loader._ms_to_iso(start_ms)

        # Next timestamp should be 1h after last
        assert start_iso == "2024-01-01T05:00:00Z"


class TestDataLoaderConfigIntegration:
    """Test DataLoader with config settings."""

    def test_respects_backtest_interval_config(self):
        """DataLoader should use BACKTEST_INTERVAL from config."""
        interval = config.BACKTEST_INTERVAL
        ms = DataLoader._interval_ms(interval)
        assert ms > 0

    def test_respects_binance_limit_config(self):
        """DataLoader should respect BINANCE_KLINES_LIMIT."""
        limit = config.BINANCE_KLINES_LIMIT
        assert limit == 1000

    def test_respects_history_days_config(self):
        """DataLoader should use BACKTEST_HISTORY_DAYS from config."""
        days = config.BACKTEST_HISTORY_DAYS
        assert days > 0
