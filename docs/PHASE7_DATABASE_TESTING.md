# 🧪 How to Test Phase 7.1 Database

## Quick Test Methods

### **Method 1: Run Unit Tests (Recommended)**
```bash
cd /Users/abhi/jupyter_env/tradingBot

# Test only database
pytest tests/test_backtest_database.py -v

# Test database + data_loader + integration
pytest tests/test_backtest_database.py tests/test_backtest_data_loader.py tests/test_backtest_integration.py -v

# Test everything (77 Phase 7 tests)
pytest tests/test_backtest_database.py tests/test_backtest_data_loader.py tests/test_config_validation.py tests/test_backtest_integration.py -v
```

### **Method 2: Manual Python Script**
```bash
python manual_test_db.py
```

---

## What Gets Tested?

### ✅ **Database Initialization** (3 tests)
- File creation
- Schema creation (prices table)
- Index creation

### ✅ **Insert Prices** (4 tests)
- Single row insertion
- Multiple rows insertion
- Empty list handling
- Duplicate prevention (INSERT OR IGNORE)

### ✅ **Retrieve Prices** (5 tests)
- Empty table retrieval
- Chronological ordering
- Start date filtering
- End date filtering
- Combined filters

### ✅ **Last Timestamp** (2 tests)
- Empty table returns None
- Latest timestamp detection

### ✅ **Count Prices** (2 tests)
- Empty table count = 0
- Accurate count after inserts

---

## Test Coverage Summary

**Total Database Tests:** 15  
**Test File:** `tests/test_backtest_database.py`  
**Status:** ✅ All passing

```
TestDatabaseInit ..................... 3 tests ✅
TestInsertPrices ..................... 4 tests ✅
TestGetPrices ........................ 5 tests ✅
TestGetLastTimestamp ................. 2 tests ✅
TestCountPrices ...................... 2 tests ✅
─────────────────────────────────────────────
TOTAL ............................. 15 tests ✅
```

---

## Running Individual Test Cases

```bash
# Run specific test class
pytest tests/test_backtest_database.py::TestInsertPrices -v

# Run specific test method
pytest tests/test_backtest_database.py::TestInsertPrices::test_insert_single_row -v

# Run with detailed output
pytest tests/test_backtest_database.py -vv

# Run with coverage
pytest tests/test_backtest_database.py --cov=backtest.database

# Run with short summary
pytest tests/test_backtest_database.py -q
```

---

## Manual Testing in Python

```python
from backtest.database import Database
import tempfile
import os

# Create temporary database
with tempfile.TemporaryDirectory() as tmpdir:
    db = Database(os.path.join(tmpdir, "test.db"))
    
    # Insert price data
    rows = [{
        "symbol": "BTCUSDT",
        "interval": "1h",
        "timestamp": "2024-01-01T00:00:00Z",
        "open": 42000.0,
        "high": 42500.0,
        "low": 41500.0,
        "close": 42200.0,
        "volume": 100.0,
        "mid": 42000.0,
    }]
    
    inserted = db.insert_prices(rows)  # Returns: 1
    prices = db.get_prices("BTCUSDT", "1h")  # Returns: [row1]
    last_ts = db.get_last_timestamp("BTCUSDT", "1h")  # Returns: "2024-01-01T00:00:00Z"
    count = db.count_prices("BTCUSDT", "1h")  # Returns: 1
```

---

## Integration Tests

Test Database + DataLoader together:

```bash
pytest tests/test_backtest_integration.py -v
```

**Tests:**
- Database and loader integration
- Loader detects existing data
- Incremental sync workflow
- Multiple symbols independence
- Multiple intervals independence
- Timestamp accuracy
- Config usage

---

## Test All Phase 7 Components

```bash
# 77 total tests (database + loader + config + integration)
pytest tests/test_backtest_database.py tests/test_backtest_data_loader.py tests/test_config_validation.py tests/test_backtest_integration.py -v

# Summary
pytest tests/test_backtest_*.py tests/test_config_validation.py -q
```

**Results:**
```
test_backtest_database.py ......... 15 tests ✅
test_backtest_data_loader.py ...... 18 tests ✅
test_config_validation.py ......... 36 tests ✅
test_backtest_integration.py ...... 10 tests ✅
─────────────────────────────────────────────
TOTAL ........................ 77 tests ✅
```

---

## Database Schema Verification

```python
from backtest.database import Database

db = Database("backtest.db")

# Check if schema exists
with db._connect() as conn:
    # Check tables
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    
    # Check indexes
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    print(f"Indexes: {[i[0] for i in indexes]}")
```

---

## Performance Testing

```python
from backtest.database import Database
import time

db = Database("backtest.db")

# Generate 1000 rows
rows = [
    {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "timestamp": f"2024-01-01T{i//24:02d}:{i%24:02d}:00Z",
        "open": 42000.0 + i,
        "high": 42500.0 + i,
        "low": 41500.0 + i,
        "close": 42200.0 + i,
        "volume": 100.0,
        "mid": 42000.0 + i,
    }
    for i in range(1000)
]

# Time insertion
start = time.time()
inserted = db.insert_prices(rows)
elapsed = time.time() - start

print(f"Inserted {inserted} rows in {elapsed:.3f}s")
print(f"Rate: {inserted/elapsed:.0f} rows/sec")

# Time retrieval
start = time.time()
prices = db.get_prices("BTCUSDT", "1h")
elapsed = time.time() - start

print(f"Retrieved {len(prices)} rows in {elapsed:.3f}s")
print(f"Rate: {len(prices)/elapsed:.0f} rows/sec")
```

---

## Expected Output

```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.2, pluggy-1.6.0

tests/test_backtest_database.py::TestDatabaseInit::test_database_creates_file PASSED
tests/test_backtest_database.py::TestDatabaseInit::test_schema_creates_prices_table PASSED
tests/test_backtest_database.py::TestDatabaseInit::test_schema_creates_index PASSED
tests/test_backtest_database.py::TestInsertPrices::test_insert_single_row PASSED
tests/test_backtest_database.py::TestInsertPrices::test_insert_multiple_rows PASSED
tests/test_backtest_database.py::TestInsertPrices::test_insert_empty_list PASSED
tests/test_backtest_database.py::TestInsertPrices::test_insert_duplicate_ignored PASSED
tests/test_backtest_database.py::TestGetPrices::test_get_prices_empty PASSED
tests/test_backtest_database.py::TestGetPrices::test_get_prices_ordered PASSED
tests/test_backtest_database.py::TestGetPrices::test_get_prices_with_start_filter PASSED
tests/test_backtest_database.py::TestGetPrices::test_get_prices_with_end_filter PASSED
tests/test_backtest_database.py::TestGetLastTimestamp::test_get_last_timestamp_empty PASSED
tests/test_backtest_database.py::TestGetLastTimestamp::test_get_last_timestamp_with_data PASSED
tests/test_backtest_database.py::TestCountPrices::test_count_prices_empty PASSED
tests/test_backtest_database.py::TestCountPrices::test_count_prices_with_data PASSED

============================== 15 passed in 0.08s ==============================
```

---

## Troubleshooting

**Problem:** Tests fail  
**Solution:** Run `pytest --tb=long` to see full error traces

**Problem:** Database locked  
**Solution:** Delete `backtest.db` and re-create: `rm backtest.db`

**Problem:** Import errors  
**Solution:** Verify `backtest/__init__.py` exists and contains correct exports

---

## ✅ Database is Working If:

- ✅ All 15 database tests pass
- ✅ `insert_prices()` returns correct count
- ✅ `get_prices()` returns rows in order
- ✅ `get_last_timestamp()` returns newest timestamp
- ✅ `count_prices()` matches inserted count
- ✅ Duplicates are silently ignored
- ✅ Filtering by start/end timestamps works

**Current Status:** ✅ All tests passing (15/15)
