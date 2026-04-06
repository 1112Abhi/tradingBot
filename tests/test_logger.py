# tests/test_logger.py

import os
import pytest
from datetime import datetime, timedelta
from logger import log_activity, get_recent_logs, purge_old_logs
import config


def test_log_activity_creates_file():
    """Test that log activity creates the log file."""
    if os.path.exists(config.LOG_FILE):
        os.remove(config.LOG_FILE)
    
    log_activity(100.5, "BUY", "alert_sent")
    assert os.path.exists(config.LOG_FILE)


def test_get_recent_logs_filters_by_date():
    """Test that get_recent_logs filters by days."""
    if os.path.exists(config.LOG_FILE):
        os.remove(config.LOG_FILE)
    
    # Log from 10 days ago
    old_time = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_activity(100.0, "BUY", "alert_sent", timestamp=old_time)
    
    # Log from today
    log_activity(105.0, "NO_TRADE", "skipped")
    
    recent = get_recent_logs(days=1)
    assert len(recent) == 1
    assert "105.00" in recent[0]


def test_purge_old_logs_removes_old_entries():
    """Test that purge removes entries older than retention days."""
    if os.path.exists(config.LOG_FILE):
        os.remove(config.LOG_FILE)
    
    old_time = (datetime.utcnow() - timedelta(days=config.LOG_RETENTION_DAYS + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_activity(100.0, "BUY", "alert_sent", timestamp=old_time)
    log_activity(105.0, "NO_TRADE", "skipped")
    
    purge_old_logs()
    
    with open(config.LOG_FILE, "r") as f:
        content = f.read()
    
    assert "100.00" not in content
    assert "105.00" in content
