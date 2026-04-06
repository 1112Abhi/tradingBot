# backtest/data_loader.py - Binance Historical Data Sync

import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import requests

import config
from backtest.database import Database


class DataLoader:
    """
    Fetches historical OHLCV data from Binance and stores it in SQLite.

    Design:
        - First sync: fetches BACKTEST_HISTORY_DAYS of data
        - Subsequent syncs: incremental (only bars newer than last stored)
        - Pagination: loops in 1000-bar chunks until caught up
        - Timestamps: Binance ms epoch → ISO 8601 UTC
        - Mid price: (high + low) / 2, stored as column
    """

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def sync(
        self,
        symbol: str = config.SYMBOL.upper().replace("-", "") + "USDT",
        interval: str = config.BACKTEST_INTERVAL,
    ) -> int:
        """
        Sync historical price data for a symbol+interval into the DB.

        Checks the last stored timestamp and fetches only new bars.
        On first run, fetches BACKTEST_HISTORY_DAYS of history.

        Args:
            symbol:   Binance pair (e.g. "BTCUSDT")
            interval: Candle interval (e.g. "1h")

        Returns:
            Number of newly inserted rows.
        """
        last_ts = self.db.get_last_timestamp(symbol, interval)

        if last_ts:
            # Incremental: start one interval after last stored bar
            start_ms = self._iso_to_ms(last_ts) + self._interval_ms(interval)
            print(f"[DataLoader] Incremental sync from {last_ts}")
        else:
            # First run: fetch full history window
            start_dt  = datetime.now(timezone.utc) - timedelta(days=config.BACKTEST_HISTORY_DAYS)
            start_ms  = int(start_dt.timestamp() * 1000)
            print(f"[DataLoader] First sync: fetching {config.BACKTEST_HISTORY_DAYS} days of {interval} data for {symbol}")

        rows      = self._fetch_all(symbol, interval, start_ms)
        inserted  = self.db.insert_prices(rows)

        total = self.db.count_prices(symbol, interval)
        print(f"[DataLoader] Inserted {inserted} new rows — total {total} bars in DB")
        return inserted

    # ------------------------------------------------------------------
    # Fetch + pagination
    # ------------------------------------------------------------------

    def _fetch_all(self, symbol: str, interval: str, start_ms: int) -> List[dict]:
        """
        Paginate Binance klines API until no more new bars are returned.

        Binance returns max 1000 candles per request. We advance start_ms
        to the bar after the last received candle and repeat until the
        response is empty or only contains the current (incomplete) bar.
        """
        now_ms  = int(datetime.now(timezone.utc).timestamp() * 1000)
        all_rows: List[dict] = []

        while start_ms < now_ms:
            batch = self._fetch_batch(symbol, interval, start_ms)
            if not batch:
                break

            all_rows.extend(batch)

            # Advance past the last bar received
            last_open_ms = self._iso_to_ms(batch[-1]["timestamp"])
            start_ms     = last_open_ms + self._interval_ms(interval)

            # Respect Binance rate limits
            if len(batch) == config.BINANCE_KLINES_LIMIT:
                time.sleep(0.2)

        return all_rows

    def _fetch_batch(
        self, symbol: str, interval: str, start_ms: int
    ) -> List[dict]:
        """
        Fetch one page (up to 1000 bars) from Binance klines endpoint.

        Binance kline fields (by index):
            0  open_time (ms), 1  open, 2  high, 3  low, 4  close,
            5  volume,         6  close_time, 7-11 unused
        """
        params = {
            "symbol":    symbol,
            "interval":  interval,
            "startTime": start_ms,
            "limit":     config.BINANCE_KLINES_LIMIT,
        }
        resp = requests.get(config.BINANCE_KLINES_URL, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        if not raw:
            return []

        rows = []
        for candle in raw:
            open_ms = int(candle[0])
            # Skip the current (incomplete) candle — its close_time is in future
            close_ms = int(candle[6])
            if close_ms > int(datetime.now(timezone.utc).timestamp() * 1000):
                break

            high = float(candle[2])
            low  = float(candle[3])
            rows.append({
                "symbol":    symbol,
                "interval":  interval,
                "timestamp": self._ms_to_iso(open_ms),
                "open":      float(candle[1]),
                "high":      high,
                "low":       low,
                "close":     float(candle[4]),
                "volume":    float(candle[5]),
                "mid":       round((high + low) / 2, 8),
            })

        return rows

    # ------------------------------------------------------------------
    # Timestamp helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ms_to_iso(ms: int) -> str:
        """Convert Binance millisecond epoch to ISO 8601 UTC string."""
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _iso_to_ms(iso: str) -> int:
        """Convert ISO 8601 UTC string to millisecond epoch."""
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def _interval_ms(interval: str) -> int:
        """Return milliseconds for a given Binance interval string."""
        units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
        return int(interval[:-1]) * units[interval[-1]] * 1000
