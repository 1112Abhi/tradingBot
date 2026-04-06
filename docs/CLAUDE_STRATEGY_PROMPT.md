# 💬 Suggested Claude Prompt for Phase 5+ Development

## Context
ChatGPT suggested a **structured approach** to strategy development. This document frames how to use Claude effectively based on ChatGPT's insights.

---

## 🎯 ChatGPT's Key Points

✅ **Don't ask:** "Give me a profitable strategy"  
✅ **DO ask:** "Here's my system, design a SIMPLE testable strategy"

This ensures Claude understands:
- Your infrastructure is ready
- You need learning + validation, not optimization
- Code must be testable and simple

---

## 📋 Proposed Claude Prompt (Strategy Phase)

```text
I have a fully functional trading bot with:

Infrastructure:
- Real-time price monitoring (CoinGecko API)
- Telegram alerts (real bot deployed)
- State management (JSON persistence)
- Activity logging with date filtering
- 33 unit tests (all passing)
- Config-driven design

Current Signal Logic:
- BUY: price > 90.0
- NO_TRADE: price ≤ 90.0

Now I want to design a SIMPLE baseline strategy for system validation and backtesting.

Requirements:
1. Clear entry condition (with reasoning)
2. Clear exit condition
3. Optional stop loss
4. Minimal parameters (≤ 3)
5. NO complex indicators (just price + moving averages max)
6. Deterministic (reproducible results)
7. Easy to test and backtest

Purpose:
- Learn how strategy performs in real data
- Find system bottlenecks
- NOT for immediate live trading

Deliverable:
1. Strategy description (2-3 sentences)
2. Entry/exit logic
3. Parameter defaults
4. Implementation in Python (for strategy.py)
5. How to test it

Don't optimize for profitability - just validate the system works.
```

---

## 🔄 Modified Responsibility Model

Based on ChatGPT's feedback:

| Task | Who | Why |
|------|-----|-----|
| Designs strategy | Claude | Expertise in market logic |
| Implements code | Claude | Fast + clean |
| **Writes ALL tests** | **YOU** | Ensures correctness + understanding |
| Validates tests pass | YOU | Safety net |
| Integrates into bot | YOU | System ownership |

---

## ✅ Why This Approach Works

1. **Claude focuses on strategy logic** (what it's best at)
2. **You validate it works** (prevents garbage-in)
3. **Tests catch edge cases** (safety)
4. **System is testable** (proof of concept)

---

## 🧪 After Claude Responds

1. **Read the strategy carefully**
   - Do you understand WHY it works?
   - Can you explain entry/exit conditions?

2. **Extract the implementation**
   - Copy strategy logic
   - Update `strategy.py` 

3. **Write tests** (you + Copilot)
   - Test entry conditions
   - Test exit conditions
   - Test with edge cases (very high/low prices)

4. **Run full test suite**
   ```bash
   pytest tests/ -v
   ```

5. **Come back if:**
   - Tests fail
   - Logic doesn't make sense
   - Edge cases break

---

## 📊 Example Test Cases for New Strategy

After Claude gives strategy, you should write tests like:

```python
# tests/test_strategy_v2.py

def test_entry_signal_valid():
    """Test entry condition triggers correctly."""
    # Based on Claude's logic
    
def test_exit_signal_valid():
    """Test exit condition triggers correctly."""
    
def test_stop_loss_triggered():
    """Test stop loss activates."""
    
def test_multiple_signals_sequence():
    """Test realistic price sequence."""
    
def test_edge_case_zero_price():
    """Test boundary conditions."""
    
def test_edge_case_very_high_price():
    """Test extreme values."""
```

---

## 🚀 Next Steps

1. **Send Claude the prompt** (above)
2. **Get strategy response**
3. **Come back with:**
   - Claude's strategy
   - Your understanding
   - Tests you wrote
   - Test results

---

## ⚠️ Red Flags (Watch For)

Claude might suggest:
- ❌ Too many parameters (hard to tune)
- ❌ Complex indicators (no libraries needed yet)
- ❌ Untestable logic (data-dependent)

**If so:** Push back! Ask for simpler version.

---

## 💡 ChatGPT's Critical Insight

> Your options idea (monthly selling + hedge) is MORE valuable than generic indicators.

Consider:
- Phase 5: Simple baseline (follow Claude)
- Phase 6: Options strategy (your proprietary idea)

---

## 📝 After Strategy is Ready

Once you have working strategy:

1. Backtest it against historical data
2. Paper trade for 1-2 weeks
3. Document performance
4. Iterate or move to options idea

---

**Ready to send Claude the prompt?** 🚀
