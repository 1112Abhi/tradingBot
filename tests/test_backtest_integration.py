# tests/test_backtest_integration.py - Integration tests for backtest system

import pytest
from backtest.database import Database
from backtest.data_loader import DataLoader
import config


class TestBacktestSystemIntegration:
    """Test end-to-end backtest system functionality."""

    def test_database_and_loader_integration(self, tmp_path):
        """Database and DataLoader should work together."""
        db = Database(str(tmp_path / "test.db"))
        loader = DataLoader(db=db)

        # Simulate fetching and storing data
        mock_data = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": "2024-01-01T00:00:00Z",
                "open": 42000.0,
                "high": 42500.0,
                "low": 41500.0,
                "close": 42200.0,
                "volume": 100.0,
                "mid": 42000.0,
            }
        ]

        inserted = db.insert_prices(mock_data)
        assert inserted == 1

        # Verify we can retrieve it
        prices = db.get_prices("BTCUSDT", "1h")
        assert len(prices) == 1
        assert prices[0]["symbol"] == "BTCUSDT"

    def test_loader_detects_existing_data(self, tmp_path):
        """DataLoader should detect previously synced data."""
        db = Database(str(tmp_path / "test.db"))
        loader = DataLoader(db=db)

        # Insert initial data
        initial_data = [
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
            for i in range(10)
        ]
        db.insert_prices(initial_data)

        # Verify last timestamp is detected
        last_ts = db.get_last_timestamp("BTCUSDT", "1h")
        assert last_ts is not None
        assert last_ts == "2024-01-01T09:00:00Z"

    def test_incremental_sync_workflow(self, tmp_path):
        """Test full incremental sync workflow."""
        db = Database(str(tmp_path / "test.db"))

        # First batch of data (simulating initial sync)
        batch1 = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 42000.0 + i,
                "high": 42500.0 + i,
                "low": 41500.0 + i,
                "close": 42200.0 + i,
                "volume": 100.0,
                "mid": 42000.0 + i,
            }
            for i in range(10)
        ]
        inserted1 = db.insert_prices(batch1)
        assert inserted1 == 10

        # Second batch (simulating incremental sync)
        batch2 = [
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 42000.0 + i,
                "high": 42500.0 + i,
                "low": 41500.0 + i,
                "close": 42200.0 + i,
                "volume": 100.0,
                "mid": 42000.0 + i,
            }
            for i in range(10, 15)
        ]
        inserted2 = db.insert_prices(batch2)
        assert inserted2 == 5

        # Verify total count
        total = db.count_prices("BTCUSDT", "1h")
        assert total == 15

    def test_multiple_symbols_independent(self, tmp_path):
        """Different symbols should be stored independently."""
        db = Database(str(tmp_path / "test.db"))

        # Insert BTC data
        btc_data = [
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
        db.insert_prices(btc_data)

        # Insert ETH data
        eth_data = [
            {
                "symbol": "ETHUSDT",
                "interval": "1h",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                "open": 2200.0,
                "high": 2250.0,
                "low": 2150.0,
                "close": 2220.0,
                "volume": 1000.0,
                "mid": 2200.0,
            }
            for i in range(5)
        ]
        db.insert_prices(eth_data)

        # Verify counts
        btc_count = db.count_prices("BTCUSDT", "1h")
        eth_count = db.count_prices("ETHUSDT", "1h")
        assert btc_count == 5
        assert eth_count == 5

    def test_multiple_intervals_independent(self, tmp_path):
        """Different intervals should be stored independently."""
        db = Database(str(tmp_path / "test.db"))

        # Insert 1h data
        data_1h = [
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
            for i in range(24)
        ]
        db.insert_prices(data_1h)

        # Insert 4h data (fewer bars, same timespan)
        data_4h = [
            {
                "symbol": "BTCUSDT",
                "interval": "4h",
                "timestamp": f"2024-01-01T{i*4:02d}:00:00Z",
                "open": 42000.0,
                "high": 42500.0,
                "low": 41500.0,
                "close": 42200.0,
                "volume": 400.0,
                "mid": 42000.0,
            }
            for i in range(6)
        ]
        db.insert_prices(data_4h)

        # Verify counts
        count_1h = db.count_prices("BTCUSDT", "1h")
        count_4h = db.count_prices("BTCUSDT", "4h")
        assert count_1h == 24
        assert count_4h == 6


class TestDataLoaderTimestampAccuracy:
    """Test timestamp conversion accuracy."""

    def test_timestamps_preserved_through_cycle(self):
        """Timestamps should be preserved through entire cycle."""
        original_timestamp = "2024-03-15T14:30:45Z"
        ms = DataLoader._iso_to_ms(original_timestamp)
        recovered_timestamp = DataLoader._ms_to_iso(ms)
        assert original_timestamp == recovered_timestamp

    def test_multiple_timestamps_ordered(self, tmp_path):
        """Multiple timestamps should maintain order."""
        db = Database(str(tmp_path / "test.db"))

        timestamps = [
            "2024-01-01T00:00:00Z",
            "2024-01-01T04:00:00Z",
            "2024-01-01T08:00:00Z",
            "2024-01-01T12:00:00Z",
            "2024-01-01T16:00:00Z",
            "2024-01-01T20:00:00Z",
        ]

        rows = [
            {
                "symbol": "BTCUSDT",
                "interval": "4h",
                "timestamp": ts,
                "open": 42000.0,
                "high": 42500.0,
                "low": 41500.0,
                "close": 42200.0,
                "volume": 100.0,
                "mid": 42000.0,
            }
            for ts in timestamps
        ]

        db.insert_prices(rows)
        retrieved = db.get_prices("BTCUSDT", "4h")
        retrieved_timestamps = [r["timestamp"] for r in retrieved]

        assert retrieved_timestamps == timestamps


class TestBacktestConfigUsage:
    """Test that config is properly used."""

    def test_backtest_db_referenced_correctly(self):
        """Database should use config.BACKTEST_DB."""
        assert hasattr(config, "BACKTEST_DB")
        assert config.BACKTEST_DB.endswith(".db")

    def test_backtest_capital_available(self):
        """Backtest capital should be available from config."""
        assert hasattr(config, "BACKTEST_CAPITAL")
        assert config.BACKTEST_CAPITAL > 0

    def test_binance_url_configured(self):
        """Binance URL should be configured."""
        assert hasattr(config, "BINANCE_KLINES_URL")
        assert "api.binance.com" in config.BINANCE_KLINES_URL
