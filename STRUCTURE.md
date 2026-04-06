# Trading Bot Repository Structure

**Quick Navigation**

```
Root Entry Points
├── config.py                   ← Configuration constants
├── run_live.py                 ← Start Phase 7.6 live watcher
├── backtest_runner.py          ← Run backtests
└── logger.py, monitor.py       ← Utilities

Packages
├── core/                       ← Live trading logic (Phase 7.6)
├── backtest/                   ← Backtesting engine (Phase 7.1-7.5)
├── strategy/                   ← EMA + RSI strategies
├── telegram/                   ← Telegram alerts
└── tests/                      ← 200+ test cases

Scripts (run from root)
└── scripts/
    ├── analyze_backtest.py
    ├── analyze_live.py
    └── research/               ← Experiments & grid searches

Documentation
├── README.md                   ← Project overview
├── REPOSITORY_ORGANIZATION.md  ← Full structure (this level)
├── PHASE76_*.md                ← Current phase (live trading)
└── docs/                       ← Phase 1-7 archives
```

**Key Files**

| File | Purpose |
|------|---------|
| `config.py` | Central configuration |
| `run_live.py` | Start live trading watcher |
| `backtest_runner.py` | Run backtests |
| `core/candle_watcher.py` | Phase 7.6: Live trading loop |
| `backtest/engine.py` | Phase 7.2: Backtesting engine |
| `strategy/ema_crossover.py` | Strategy: Dual EMA + RSI |
| `tests/test_phase76_bugs_fixed.py` | Phase 7.6 verification (17 tests) |

**Recent Updates**

- ✅ Phase 7.6 Bug Fixes (3 critical bugs fixed)
- ✅ Multi-interval data sync (15m, 30m, 1h, 4h)
- ✅ File logging to `logs/watcher.log`
- ✅ Tests: 17/17 passing

**Learn More**

- [Full structure](REPOSITORY_ORGANIZATION.md)
- [Phase 7.6 live trading](PHASE76_EXECUTIVE_SUMMARY.md)
- [Phase 7.6 bug fixes](PHASE76_BUG_FIXES.md)
- [Documentation index](DOCUMENTATION_INDEX.md)
