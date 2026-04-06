# 🚀 ChatGPT/Claude Quick Start - Phase 3

## Current Project State

```
Trading Bot - Phase 1-2 Complete ✅
├── Environment: Python 3.11.15 + pytest
├── Telegram: Live integration working
├── Code: Type hints, clean architecture
├── Tests: 11/11 passing
└── Next: Real data + live monitoring
```

## Quick Copy-Paste for ChatGPT

### Context Prompt

```
I'm building a trading bot in Python. Here's the current status:

ENVIRONMENT:
- Python 3.11.15 in venv_3.11/
- pytest for testing
- Dependencies: requests, pytest

CURRENT STRUCTURE:
- config.py: All constants (bot token, chat ID, threshold)
- telegram_bot.py: Real Telegram API integration
- data_fetch.py: Currently returns dummy price (100.0)
- strategy.py: Generate BUY/NO_TRADE signals
- main.py: Orchestrates pipeline

TESTS:
- 11/11 passing (mocked requests)
- pytest.ini configured
- Tests in tests/ folder

NEXT TASK (Phase 3):
Implement real price monitoring:

1. Update data_fetch.py to fetch from CoinGecko API
2. Create monitor.py for live price monitoring loop
3. Create logger.py to log activities to file
4. Create state.py to prevent duplicate alerts
5. Write tests for new modules

Guidelines:
- Keep functions simple (< 20 lines)
- Use type hints
- Mock APIs in tests
- Add docstrings
- Use config.py for all constants
- Don't write tests (I'll do that)

Full requirements: See PHASE_3_INSTRUCTIONS.md in the repo
```

---

## File Locations

```
/Users/abhi/jupyter_env/tradingBot/
├── venv_3.11/              # Python 3.11 virtual env
├── config.py               # Update: Add real data config
├── telegram_bot.py         # ✅ Done
├── data_fetch.py           # Update: Real API
├── strategy.py             # ✅ Done
├── main.py                 # ✅ Done
├── monitor.py              # Create: New
├── logger.py               # Create: New
├── state.py                # Create: New
├── tests/
│   ├── test_telegram.py    # ✅ Done
│   ├── test_data_fetch.py  # ✅ Done
│   ├── test_strategy.py    # ✅ Done
│   ├── test_monitor.py     # Create: New
│   └── test_logger.py      # Create: New
└── PHASE_3_INSTRUCTIONS.md # Full requirements
```

---

## How to Test After Claude Implements

```bash
# 1. Enter virtual environment
source venv_3.11/bin/activate

# 2. Install any new dependencies (if needed)
pip install -r requirements.txt

# 3. Run all tests
pytest -v

# 4. Test monitor for 60 seconds
python -c "from monitor import watch_price; watch_price('bitcoin', 60)"

# 5. Check logs
cat trading_bot.log

# 6. Check state
cat state.json
```

---

## Key Design Decisions

✅ **CoinGecko API**: Free, no auth required
✅ **Monitor Loop**: Simple fetch → check → alert cycle
✅ **State Tracking**: Prevent duplicate "BUY" alerts
✅ **Logging**: Lightweight text file (not database yet)
✅ **Mocked Tests**: Don't hit real API during testing

---

## When Stuck

1. Check PHASE_3_INSTRUCTIONS.md for full details
2. Look at existing code in telegram_bot.py (pattern to follow)
3. Tests should mock `requests.post()` and `data_fetch.fetch_price()`
4. All imports at top of file
5. Type hints on all function signatures

---

## Success Looks Like

```bash
$ pytest -v
======================== 16/16 passed in 2.5s ========================

$ python main.py
Current price: $42,500
Signal: BUY
[TELEGRAM] ✅ Message sent successfully

$ cat trading_bot.log
2026-03-28 15:30:45 | Price: 42500.0 | Signal: BUY | Action: Alert sent
```
