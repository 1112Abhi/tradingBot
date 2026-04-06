# 🤖 Phase 3 Instructions - Real Trading Data & Live Monitoring

## Current Status

✅ **Phase 1-2 Complete:**
- Core modules implemented (telegram_bot, data_fetch, strategy, main)
- Real Telegram integration working
- All 11 tests passing
- Message successfully sent to Telegram chat

---

## Phase 3 Goals

Build a **live trading bot** that:
1. Fetches real price data (not dummy 100.0)
2. Monitors price in real-time
3. Triggers alerts when price crosses threshold
4. Logs all activities

---

## New Requirements

### 1. Real Data Source
Currently using dummy price (100.0). Choose one:
- **CoinGecko API** (free, no auth) - Recommended
- **Binance API** (free, no auth)
- **Alpha Vantage** (stocks, requires free API key)

### 2. Live Monitoring
Need new module: `monitor.py`
- Function: `watch_price(symbol, interval_seconds)`
- Continuously fetches price at intervals
- Compares to threshold
- Sends alert if signal changes

### 3. Configuration Updates
Add to `config.py`:
```python
# Data source config
DATA_SOURCE = "coingecko"  # or "binance", "alpha_vantage"
SYMBOL = "bitcoin"  # or "BTC", "AAPL", etc.
MONITOR_INTERVAL = 60  # seconds between checks
```

### 4. Logging Module
New module: `logger.py`
- Log all price checks to file: `trading_bot.log`
- Format: timestamp | price | signal | action
- Keep last 7 days of logs

### 5. State Management
New module: `state.py`
- Track last signal sent (avoid duplicate alerts)
- Store last price checked
- Persist to `state.json` file

---

## Files to Implement

| File | Purpose | Priority |
|------|---------|----------|
| `data_fetch.py` (update) | Real API instead of dummy | HIGH |
| `monitor.py` | Live monitoring loop | HIGH |
| `logger.py` | Activity logging | MEDIUM |
| `state.py` | Signal tracking | MEDIUM |
| `tests/test_monitor.py` | Monitor tests | MEDIUM |
| `tests/test_logger.py` | Logger tests | LOW |

---

## Implementation Steps

### Step 1: Update data_fetch.py
```python
def fetch_price(symbol: str, source: str) -> float:
    """
    Fetch real price from API.
    
    Args:
        symbol: Asset symbol (e.g., "bitcoin", "BTC")
        source: Data source ("coingecko", "binance", etc.)
    
    Returns:
        Float price or raises exception
    """
    # Implement CoinGecko API call for Phase 3
    # Returns real price data
```

### Step 2: Create monitor.py
```python
def watch_price(symbol: str, duration_seconds: int = None) -> None:
    """
    Monitor price continuously and send alerts.
    
    Args:
        symbol: Asset to monitor
        duration_seconds: How long to monitor (None = infinite)
    """
    # Loop: fetch → check signal → send alert → log
    # Run until duration expires or user stops
```

### Step 3: Create logger.py
```python
def log_activity(timestamp: str, price: float, signal: str, action: str) -> None:
    """Write activity to trading_bot.log file."""
    
def get_recent_logs(days: int = 1) -> list:
    """Retrieve recent log entries."""
```

### Step 4: Create state.py
```python
def get_state() -> dict:
    """Load state from state.json."""
    
def save_state(last_signal: str, last_price: float) -> None:
    """Save state to prevent duplicate alerts."""
    
def should_send_alert(new_signal: str, last_signal: str) -> bool:
    """Determine if alert is needed (signal changed)."""
```

---

## Testing Strategy

- Mock external API calls in tests
- Test price change detection
- Test state persistence
- Test logging output

Example:
```python
def test_watch_price_detects_buy_signal():
    """Test that buy signal is detected when price > threshold."""
    # Mock fetch_price to return 95.0
    # Run watch_price for one iteration
    # Verify Telegram message was sent
```

---

## Configuration Notes

```python
# config.py additions needed

# Real data
DATA_SOURCE = "coingecko"
SYMBOL = "bitcoin"
MONITOR_INTERVAL = 60  # seconds

# Optional: Add API keys if needed
ALPHA_VANTAGE_KEY = "your_key_here"  # Only if using stocks

# Thresholds
BUY_THRESHOLD = 90.0  # Still used
SELL_THRESHOLD = 50.0  # New: for SELL signals (Phase 3+)
```

---

## Success Criteria

✅ Fetch real price data (not dummy)
✅ Detect price changes and trigger signals
✅ Send Telegram alerts only when signal changes
✅ Log all activities to file
✅ All tests passing
✅ Monitor can run indefinitely without crashing
✅ State persists between restarts

---

## Commands to Test

```bash
# Run monitor for 5 minutes
python -c "from monitor import watch_price; watch_price('bitcoin', 300)"

# View recent logs
python -c "from logger import get_recent_logs; print(get_recent_logs(1))"

# Check current state
cat state.json
```

---

## Notes for AI Assistant

- Use CoinGecko API (free, no authentication)
- Keep monitor loop simple (fetch → check → alert → sleep)
- Add error handling for network failures
- Tests should mock all external API calls
- Logging should be lightweight (don't hammer disk)

---

## Next Phase (Phase 4)

Once Phase 3 complete:
- Add database for historical prices
- Implement multiple symbols monitoring
- Add web dashboard to view logs
- Advanced strategies (moving averages, etc.)
