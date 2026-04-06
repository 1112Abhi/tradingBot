# logger.py - Activity Logging Module

import os
from datetime import datetime, timedelta
from typing import List

import config


def log_activity(
    price: float,
    signal: str,
    action: str,
    timestamp: str = "",
) -> None:
    """
    Append a trading activity entry to the log file.

    Args:
        price:     Current asset price.
        signal:    Generated signal (e.g. "BUY", "NO_TRADE").
        action:    What was done (e.g. "alert_sent", "skipped").
        timestamp: ISO timestamp string; defaults to current UTC time.
    """
    ts = timestamp or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} | {price:.2f} | {signal} | {action}\n"
    with open(config.LOG_FILE, "a") as fh:
        fh.write(line)


def get_recent_logs(days: int = 1) -> List[str]:
    """
    Retrieve log entries from the last N days.

    Args:
        days: Number of past days to include (default 1).

    Returns:
        List of matching log line strings (stripped).
    """
    if not os.path.exists(config.LOG_FILE):
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    entries: List[str] = []

    with open(config.LOG_FILE, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ts_str = line.split(" | ")[0]
                ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
                if ts >= cutoff:
                    entries.append(line)
            except (ValueError, IndexError):
                continue  # skip malformed lines

    return entries


def purge_old_logs() -> None:
    """
    Remove log entries older than LOG_RETENTION_DAYS.
    Rewrites the log file in-place.
    """
    recent = get_recent_logs(days=config.LOG_RETENTION_DAYS)
    with open(config.LOG_FILE, "w") as fh:
        fh.write("\n".join(recent) + ("\n" if recent else ""))
