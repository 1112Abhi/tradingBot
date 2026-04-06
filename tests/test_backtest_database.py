# tests/test_backtest_database.py - Unit tests for backtest/database.py

import os
import pytest
import sqlite3
from backtest.database import Database
import config


class TestDatabaseInit:
    """Test database initialization and schema."""

    def test_database_creates_file(self, tmp_path):
        """Database should create a new SQLite file."""
        db_file = tmp_path / "test.db"
        db = Database(str(db_file))
        assert db_file.exists()

    def test_schema_creates_prices_table(self, tmp_path):
        """Schema initialization should create prices table."""
        db = Database(str(tmp_path / "test.db"))
        with db._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
            )
            assert cursor.fetchone() is not None

    def test_schema_creates_index(self, tmp_path):
        """Schema initialization should create lookup index."""
        db = Database(str(tmp_path / "test.db"))
        with db._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_prices_lookup'"
            )
            assert cursor.fetchone() is not None


class TestInsertPrices:
    """Test price insertion logic."""

    def test_insert_single_row(self, tmp_path):
        """Insert a single price row."""
        db = Database(str(tmp_path / "test.db"))
        rows = [{
            "symbol": "BTCUSDT",
            "interval": "1h",
            "timestamp": "2024-01-01T00:00:00Z",
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
            "mid": 100.0,
        }]
        inserted = db.insert_prices(rows)
        assert inserted == 1

    def test_insert_multiple_rows(self, tmp_path):
        """Insert multiple price rows."""
        db = Database(str(tmp_path / "test.db"))
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 95.0 + i,
                "close": 102.0 + i,
                "volume": 1000.0,
                "mid": 100.0 + i,
            }
            for i in range(5)
        ]
        inserted = db.insert_prices(rows)
        assert inserted == 5

    def test_insert_empty_list(self, tmp_path):
        """Insert empty list should return 0."""
        db = Database(str(tmp_path / "test.db"))
        inserted = db.insert_prices([])
        assert inserted == 0

    def test_insert_duplicate_ignored(self, tmp_path):
        """Duplicate rows should be silently ignored."""
        db = Database(str(tmp_path / "test.db"))
        row = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "timestamp": "2024-01-01T00:00:00Z",
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
            "mid": 100.0,
        }
        # Insert same row twice
        inserted1 = db.insert_prices([row])
        inserted2 = db.insert_prices([row])
        assert inserted1 == 1
        assert inserted2 == 0  # Duplicate ignored


class TestGetPrices:
    """Test price retrieval."""

    def test_get_prices_empty(self, tmp_path):
        """Get prices from empty table."""
        db = Database(str(tmp_path / "test.db"))
        prices = db.get_prices("BTCUSDT", "1h")
        assert prices == []

    def test_get_prices_ordered(self, tmp_path):
        """Prices should be returned in chronological order."""
        db = Database(str(tmp_path / "test.db"))
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000.0,
                "mid": 100.0,
            }
            for i in range(3)
        ]
        db.insert_prices(rows)
        prices = db.get_prices("BTCUSDT", "1h")
        timestamps = [p["timestamp"] for p in prices]
        assert timestamps == sorted(timestamps)

    def test_get_prices_with_start_filter(self, tmp_path):
        """Get prices with start timestamp filter."""
        db = Database(str(tmp_path / "test.db"))
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000.0,
                "mid": 100.0,
            }
            for i in range(5)
        ]
        db.insert_prices(rows)
        prices = db.get_prices("BTCUSDT", "1h", start="2024-01-01T02:00:00Z")
        assert len(prices) == 3
        assert prices[0]["timestamp"] == "2024-01-01T02:00:00Z"

    def test_get_prices_with_end_filter(self, tmp_path):
        """Get prices with end timestamp filter."""
        db = Database(str(tmp_path / "test.db"))
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000.0,
                "mid": 100.0,
            }
            for i in range(5)
        ]
        db.insert_prices(rows)
        prices = db.get_prices("BTCUSDT", "1h", end="2024-01-01T02:00:00Z")
        assert len(prices) == 3
        assert prices[-1]["timestamp"] == "2024-01-01T02:00:00Z"


class TestGetLastTimestamp:
    """Test last timestamp retrieval."""

    def test_get_last_timestamp_empty(self, tmp_path):
        """Last timestamp should be None for empty table."""
        db = Database(str(tmp_path / "test.db"))
        last_ts = db.get_last_timestamp("BTCUSDT", "1h")
        assert last_ts is None

    def test_get_last_timestamp_with_data(self, tmp_path):
        """Last timestamp should return newest timestamp."""
        db = Database(str(tmp_path / "test.db"))
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000.0,
                "mid": 100.0,
            }
            for i in range(5)
        ]
        db.insert_prices(rows)
        last_ts = db.get_last_timestamp("BTCUSDT", "1h")
        assert last_ts == "2024-01-01T04:00:00Z"


class TestCountPrices:
    """Test price counting."""

    def test_count_prices_empty(self, tmp_path):
        """Count should be 0 for empty table."""
        db = Database(str(tmp_path / "test.db"))
        count = db.count_prices("BTCUSDT", "1h")
        assert count == 0

    def test_count_prices_with_data(self, tmp_path):
        """Count should match number of inserted rows."""
        db = Database(str(tmp_path / "test.db"))
        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000.0,
                "mid": 100.0,
            }
            for i in range(10)
        ]
        db.insert_prices(rows)
        count = db.count_prices("BTCUSDT", "1h")
        assert count == 10
