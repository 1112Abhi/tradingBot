# 🤖 Trading Bot

A Python trading bot with live Telegram integration, multi-strategy EMA crossover analysis, and comprehensive backtesting engine with ATR-based risk management.

**Status:** Phase 7.6 Complete | 200+ Tests Passing | Production Ready | Bug Fixes Applied

## 📊 Current Capabilities

- ✅ **Live Trading:** Real-time candle watcher with paper trading (Phase 7.6)
- ✅ **Multi-Strategy:** Aggregate signals from multiple EMA configurations (Phase 6)
- ✅ **Backtesting:** Full historical simulation with persistent results (Phase 7.2)
- ✅ **Risk Management:** ATR-based dynamic position sizing (Phase 7.3)
- ✅ **Metrics:** Annualised Sharpe ratio + max drawdown calculation (Phase 7.3)
- ✅ **Parameter Validation:** Grid search across symbols & SL/TP configurations (Phase 7.4)
- ✅ **Extended Validation:** 3-year backtest with 1x leverage (Phase 7.5)
- ✅ **Bug Fixes:** Live trading polling, logging, and first-run initialization (Phase 7.6)

```
trading_bot/
├── core/                       # Live trading modules
│   ├── main.py                 # Orchestrator
│   ├── monitor.py              # Price monitoring loop
│   ├── data_fetch.py           # Data sources (Coingecko, Binance, Alpha Vantage)
│   └── state.py                # State management
├── telegram/                   # Telegram bot integration
│   ├── bot.py                  # Bot setup
│   ├── commands.py             # Command handlers
│   └── listener.py             # Message polling
├── strategy/                   # Strategy implementations
│   ├── base.py                 # Base strategy interface
│   ├── ema_crossover.py        # EMA(12,26) with EMA(50) trend filter
│   ├── risk_manager.py         # ATR-based position sizing [NEW Phase 7.3]
│   ├── aggregator.py           # Multi-strategy signal aggregation
│   └── factory.py              # Strategy factory pattern
├── backtest/                   # Backtesting engine
│   ├── database.py             # SQLite persistence layer
│   ├── data_loader.py          # Historical data loading
│   ├── engine.py               # Simulation engine (state machine)
│   └── metrics.py              # Performance metrics (Sharpe, DD) [Updated Phase 7.3]
├── tests/                      # pytest suite (195 tests)
├── docs/                       # Documentation
├── venv_3.11/                  # Python 3.11 virtual environment
├── config.py                   # All constants and configuration
├── requirements.txt            # Dependencies
└── backtest.db                 # SQLite database (auto-created)

## 🚀 Quick Start

### Setup
```bash
# Activate virtual environment
source venv_3.11/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run
```bash
# Execute the trading bot pipeline
python main.py

# Run tests
pytest -v
```

## 📊 Current Status

✅ **Phase 1-2 Complete** — Live Telegram integration (11 tests)
✅ **Phase 3 Complete** — Real price data & monitoring loop (15 tests)
✅ **Phase 4 Complete** — Multi-source data support (10 tests)
✅ **Phase 5 Complete** — EMA strategy framework (22 tests)
✅ **Phase 6 Complete** — Multi-strategy aggregation (59 tests)
✅ **Phase 7.1 Complete** — Backtesting data layer (25 tests)
✅ **Phase 7.2 Complete** — Backtesting engine (17 tests)
✅ **Phase 7.3 Complete** — ATR risk manager + Sharpe metrics (51 new tests)

**Total:** 195/195 tests passing | Live trading ready

## 🔧 Core Modules

| Module | Purpose | Phase |
|--------|---------|-------|
| `core/main.py` | Orchestrator | 1 |
| `core/monitor.py` | Real-time price loop | 3 |
| `core/data_fetch.py` | Price data sources | 4 |
| `strategy/ema_crossover.py` | EMA(12,26) + EMA(50) trend filter | 5 |
| `strategy/aggregator.py` | Multi-strategy voting | 6 |
| `strategy/risk_manager.py` | ATR-based position sizing | **7.3** |
| `backtest/engine.py` | Historical simulation | 7.2 |
| `backtest/metrics.py` | Performance metrics (Sharpe, DD) | **7.3** |
| `backtest/database.py` | SQLite persistence | 7.1 |
| `telegram/bot.py` | Telegram messaging | 2 |

## 📖 Documentation

**Quick Navigation:**
- **Getting started?** → [docs/QUICK_START.md](docs/QUICK_START.md) (5 min)
- **Phase 7.2 (Backtesting)?** → [docs/PHASE72_IMPLEMENTATION.md](docs/PHASE72_IMPLEMENTATION.md)
- **Phase 7.3 (Risk Manager)?** → [docs/PHASE73_IMPLEMENTATION.md](docs/PHASE73_IMPLEMENTATION.md) ⭐ NEW
- **Full documentation index** → [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
- **Repository structure** → [REPOSITORY_ORGANIZATION.md](REPOSITORY_ORGANIZATION.md)

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_telegram.py -v

# Run with coverage
pytest --cov
```

## ⚙️ Configuration

Edit `config.py` to customize:
- Telegram credentials (bot token, chat ID)
- Price thresholds
- Data source (CoinGecko, Binance, etc.)
- Monitoring interval

## 📝 Notes

- All code uses type hints
- Tests mock external APIs (no real API calls during testing)
- Modular design — each module is independently testable
- Configuration-driven — no hardcoded values

## 🤝 Contributing

1. Update code in root modules
2. Add/update tests in `tests/`
3. Update documentation in `docs/`
4. Run `pytest -v` to verify
