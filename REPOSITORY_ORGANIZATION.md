# Repository Organization Summary

**Date:** 1 April 2026  
**Status:** ✅ REORGANIZED - Clean architecture with Phase 7.6 complete  
**Total Tests:** 200+/200+ passing  
**Structure:** ✅ Implemented (root entry points, packages, scripts, docs)

---

## Directory Structure

```
tradingBot/

┌─ ROOT (Entry Points Only) ────────────────────────────────────────
│
├── 🚀 Entry Points (main application)
│   ├── config.py               — Central configuration constants
│   ├── logger.py               — Logging utility
│   ├── run_live.py             — Start Phase 7.6 live trading watcher
│   ├── backtest_runner.py      — CLI for backtesting
│   ├── monitor.py              — Live monitor (compat shim)
│   └── state.py                — Persistent state (compat shim)
│

├── 📦 PACKAGES (Implementation) ────────────────────────────────────
│
├── 📁 core/                    — Core trading logic + Phase 7.6 live watcher
│   ├── __init__.py
│   ├── candle_watcher.py       — Phase 7.6: Live trading loop (FIXED)
│   ├── main.py                 — Single price check (legacy)
│   ├── monitor.py              — Continuous monitoring (legacy)
│   ├── data_fetch.py           — Price fetching (legacy)
│   └── state.py                — Persistent state (legacy)
│
├── 📁 backtest/                — Phase 7 backtesting system
│   ├── __init__.py
│   ├── database.py             — SQLite persistence (Phase 7.1)
│   ├── data_loader.py          — Binance sync
│   ├── engine.py               — Backtesting loop (Phase 7.2)
│   └── metrics.py              — Performance metrics (Phase 7.2+)
│
├── 📁 strategy/                — Strategy framework
│   ├── __init__.py
│   ├── base.py                 — BaseStrategy ABC
│   ├── ema_crossover.py        — Dual EMA strategy with RSI filter
│   ├── risk_manager.py         — ATR-based position sizing (Phase 7.3)
│   ├── aggregator.py           — Multi-strategy aggregation
│   └── factory.py              — Strategy registry
│
├── 📁 telegram/                — Telegram integration
│   ├── __init__.py
│   ├── bot.py                  — Messaging interface
│   ├── commands.py             — Command handlers
│   └── listener.py             — Message listener
│
├── 📁 tests/                   — Test suite (200+ tests)
│   ├── test_phase76_bugs_fixed.py — Phase 7.6: Bug fix verification (NEW)
│   ├── test_backtest_*.py      — Data layer tests
│   ├── test_risk_manager.py    — Risk manager tests
│   ├── test_strategy*.py       — Strategy tests
│   ├── test_telegram*.py       — Telegram tests
│   └── ...
│

├── 📚 SCRIPTS (Run from project root) ──────────────────────────────
│
├── 📁 scripts/                 — Utility scripts
│   ├── analyze_backtest.py     — Analyze backtest results
│   ├── analyze_live.py         — Analyze live trades
│   ├── analyze_portfolio.py    — Portfolio analysis
│   ├── compare_strategies.py   — Compare strategy performance
│   ├── show_recent_runs.py     — Display recent backtest runs
│   │
│   └── 📁 research/            — One-off experiments & research
│       ├── validate_parameters.py — Phase 7.4: Grid search (27 configs)
│       ├── rsi_grid.py         — RSI parameter testing
│       ├── tp_grid.py          — Take-profit optimization
│       ├── fetch_3y_data.py    — Fetch 3-year data
│       └── ...
│

├── 📖 DOCUMENTATION ───────────────────────────────────────────────
│
├── README.md                   — Project overview & quick start
├── DOCUMENTATION_INDEX.md      — Master documentation index
├── REPOSITORY_ORGANIZATION.md  — This file (structure guide)
├── PHASE76_*.md                — Phase 7.6: Live trading + bug fixes (CURRENT)
├── PHASE76_BUG_FIXES.md        — Detailed bug fix analysis
│
├── 📁 docs/                    — Documentation archive
│   ├── PHASE74_IMPLEMENTATION.md   — Phase 7.4: Parameter grid
│   ├── PHASE75_EXECUTIVE_SUMMARY.md — Phase 7.5: Extended validation
│   ├── PHASE75_EXTENDED_VALIDATION.md — Technical validation
│   ├── [more phase docs]       — Phase 1-7 documentation
│   └── ...
│

├── 📦 UTILITIES & CONFIG ──────────────────────────────────────────
│
├── requirements.txt            — Python dependencies
├── pytest.ini                  — Pytest configuration
├── config.py                   — Centralized configuration
├── logger.py                   — Logging utility
│

├── 📊 DATA & LOGS ─────────────────────────────────────────────────
│
├── backtest.db                 — SQLite: Price history + backtest results
├── state.json                  — Persistent trading state
├── trading_bot.log             — Trading activity log
├── logs/                       — Log directory
│   ├── watcher.log             — Phase 7.6: Live watcher log (rotating)
│   └── ...
│

├── 🗂️ ARCHIVED & LEGACY ───────────────────────────────────────────
│
├── 📁 _old/                    — Archived implementation (reference only)
│   ├── claudeResponse/         — Claude's reference designs
│   ├── phase1-6 code           — Legacy code
│   ├── test_*.py (old)         — Old test files
│   └── ...
│
├── 📁 .archive/                — Old documentation
│   ├── TRADING_BOT_COMPLETE.md — Legacy completion report
│   └── ...
│

└── 🐍 ENVIRONMENT ─────────────────────────────────────────────────
    ├── venv_3.11/              — Python 3.11 virtual environment
    ├── .venv/                  — Alias (if needed)
    └── .pytest_cache/          — Pytest cache
```

---


## Code Organization by Responsibility

### 🎯 Trading Phases

| Phase | Status | Components | Purpose |
|-------|--------|-----------|---------|
| **1** | ✅ | `telegram_bot.py` | Telegram integration |
| **2** | ✅ | `telegram_commands.py` | Command handling |
| **3** | ✅ | `monitor.py`, `state.py`, `logger.py` | Monitoring & alerts |
| **4** | ✅ | `data_fetch.py` | Multi-source price fetching |
| **5** | ✅ | `strategy.py` | EMA crossover strategy |
| **6** | ✅ | `aggregator.py`, `strategy_factory.py`, `strategy/` | Multi-strategy |
| **7.1** | ✅ | `backtest/database.py`, `backtest/data_loader.py` | Data layer |
| **7.2** | ✅ | `backtest/engine.py`, `backtest/metrics.py`, `backtest_runner.py` | Engine layer |
| **7.3** | ⏳ | (Risk manager) | Position sizing |
| **7.4** | ⏳ | (Live mode) | Production trading |

---

## Layered Architecture

### Layer 1: Data (SQLite + Binance)
```
┌─ backtest/database.py       [prices table + run/trade tables]
└─ backtest/data_loader.py    [Binance sync + incremental updates]
```

### Layer 2: Strategy
```
┌─ strategy/base.py           [ABC + MarketData interface]
├─ strategy/ema_crossover.py  [Concrete implementation]
├─ strategy_factory.py        [Registry pattern]
└─ aggregator.py              [Multi-strategy voting]
```

### Layer 3: Execution
```
┌─ backtest/engine.py         [Backtesting loop]
├─ backtest/metrics.py        [Performance metrics]
├─ monitor.py                 [Live monitoring]
└─ telegram_bot.py            [Alert dispatch]
```

### Layer 4: Configuration & State
```
┌─ config.py                  [Global configuration]
├─ state.py                   [Persistent state]
└─ logger.py                  [Activity logging]
```

---

## File Naming Conventions

### Main Production Code
- `{name}.py` — Production files (no prefix or suffix)
- e.g., `monitor.py`, `strategy.py`, `aggregator.py`

### Organized Modules
- `{module}/{name}.py` — Organized by responsibility
- e.g., `backtest/engine.py`, `strategy/base.py`

### Test Files
- `test_{name}.py` — Individual test files in root (older tests)
- `tests/test_{name}.py` — Organized test suite
- e.g., `tests/test_phase72_backtest_runs.py`

### Documentation
- `{PHASE}_{TOPIC}.md` — Phase documentation in docs/
- e.g., `docs/PHASE72_IMPLEMENTATION.md`

### Configuration
- `config.py` — Main configuration
- `pytest.ini` — Test runner configuration
- `requirements.txt` — Python dependencies

---

## Key Design Decisions

### ✅ Separation of Concerns
- **Data layer:** `backtest/` handles all persistence
- **Strategy layer:** `strategy/` handles all signal generation
- **Execution layer:** `monitor.py`, `engine.py` handle execution
- **Configuration:** `config.py` centralizes all constants

### ✅ Import Organization
- Relative imports within modules: `from backtest.database import Database`
- Absolute imports from root: `from strategy_factory import get_strategies`
- Clear module boundaries prevent circular dependencies

### ✅ Testing Strategy
- Unit tests in `tests/` with pytest fixtures
- 153 passing tests covering all phases
- No `__pycache__` or `.pyc` files in version control

### ✅ Documentation
- Markdown docs in `docs/` for reference
- Claude's reference in `claudeResponse/` for validation
- Inline comments for complex logic
- Docstrings on all public functions

### ✅ Database Schema
- SQLite in `backtest.db` for persistence
- `prices` table for historical data (Phase 7.1)
- `backtest_runs` table for run summaries (Phase 7.2)
- `backtest_trades` table for trade records (Phase 7.2)
- Proper indexes and foreign keys

---

## Clean-up Opportunities

### Consider Later (Non-blocking)
- Move `test_*.py` files from root to `tests/` (old tests still work from root)
- Archive `claudeResponse/` after development stabilizes
- Consolidate phase documentation into DOCUMENTATION_INDEX.md

### No Issues
- ✅ No circular imports
- ✅ No hardcoded paths
- ✅ No duplicate logic
- ✅ Clean module boundaries

---

## Running Tests

```bash
# All tests (153 passing)
pytest tests/ -v

# Phase 7.2 tests only
pytest tests/test_phase72_backtest_runs.py -v

# Quick check
pytest tests/ -q
```

---

## Running Live Trading

```bash
# Single price check
python main.py

# Continuous monitoring (every 60 seconds)
python monitor.py

# Telegram listener (background)
python bot_listener.py &
```

---

## Running Backtests

```bash
# Sync data + run backtest
python backtest_runner.py --symbol BTCUSDT --interval 1h --sync --mode both

# Backtest only (use cached data)
python backtest_runner.py --symbol BTCUSDT --interval 1h --mode per

# Query results
sqlite3 backtest.db "SELECT * FROM backtest_runs;"
```

---

## Implementation Status

✅ **REORGANIZATION COMPLETE**
- Moved `core/` — All live trading code (main, monitor, data_fetch, state)
- Moved `telegram/` — All Telegram integration (bot, commands, listener)  
- Moved `strategy/` — Aggregator and factory now here
- Archived `_old/` — Old files and legacy code for reference
- Updated imports — All 153 tests passing
- Zero production dependencies on `_old/`

✅ **Well-Organized:**
- Clear layer separation (data → strategy → execution)
- Consistent naming conventions
- Logical module grouping
- Root directory clean (only config, logger, backtest_runner, docs)
- Comprehensive documentation
- 153 passing tests
- No technical debt

✅ **Production-Ready:**
- All import paths work correctly
- No circular dependencies
- Configuration centralized
- Tests automated
- Both live and backtest modes functional
- Zero dependencies on archived code

✅ **Extensible:**
- Easy to add new modules in `core/`, `telegram/`, `strategy/`
- Easy to add new strategies (via `strategy/` + factory)
- Easy to add new phases (new directories or files)
- Clear interfaces (TypedDict + ABC patterns)
- Database schema supports future expansion

**Status:** Clean architecture implemented. Ready for Phase 7.3 (Risk Manager) 🚀
