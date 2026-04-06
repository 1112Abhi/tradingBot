# 🤖 Claude Instructions - Trading Bot Phase 1

## Context

We are building a minimal Python trading bot following TDD-lite principles.

See `PROJECT_SETUP.md` for full project structure and design principles.

---

## Current Task

Implement **Phase 1 modules** one by one:

### 1️⃣ `telegram_bot.py` 
- **Function**: `send_message(text)` 
- **Purpose**: Send message to Telegram
- **Input**: String message
- **Output**: Boolean (success/failure)
- **Note**: Mock API for Phase 1, no real token needed yet

### 2️⃣ `data_fetch.py`
- **Function**: `fetch_price()`
- **Purpose**: Fetch current price
- **Output**: Float (dummy price initially)
- **Note**: Returns 100 for Phase 1

### 3️⃣ `strategy.py`
- **Function**: `generate_signal(price)`
- **Purpose**: Generate buy/sell signal
- **Logic**: 
  - If price > 90 → return "BUY"
  - Else → return "NO_TRADE"
- **Output**: String

### 4️⃣ `main.py`
- **Purpose**: Orchestrate all modules
- **Flow**: Fetch → Analyze → Alert
- **Output**: Sends Telegram message with signal

---

## Implementation Guidelines

✅ **DO:**
- Keep each function under 15 lines
- Use `config.py` for constants
- Add type hints (`def func(x: int) -> str:`)
- Mock external APIs (Telegram)
- Return simple data types

❌ **DON'T:**
- Over-engineer or add extra features
- Hardcode values (use config.py)
- Create complex error handling
- Use classes for Phase 1

---

## Note on Testing

**⚠️ Tests are written by the developer (not Claude), following this pattern:**
- Keep tests simple: 1 test file per module in `tests/`
- Test edge cases: empty input, invalid types, boundary conditions
- Use pytest syntax for consistency

**The developer handles**: test writing, pytest execution, validation

---

## Development Workflow (Claude focus)

1. **Implement function** (minimal code with type hints)
2. **Add docstring** (clear parameter/return docs)
3. **Use config.py** for all constants
4. **Follow existing patterns** in the repo

No need to write tests — developer will create them separately.

---

## Success Criteria

✅ All tests pass: `pytest`
✅ `main.py` runs without errors
✅ Code is modular and testable
✅ No hardcoded values

---

## Notes

- This is **Phase 1 only** (minimal working pipeline)
- Focus on correctness over optimization
- Each function should be independently testable
- Use mock for Telegram API

**When stuck**: Check `PROJECT_SETUP.md` for reference implementation details.
