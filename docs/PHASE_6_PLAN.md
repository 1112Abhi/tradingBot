# 🎯 Phase 6: Multi-Strategy Aggregation - Implementation Plan

**Status:** Design validated by ChatGPT ✅

---

## 📋 Current State (Claude Built)

Claude has designed:
- ✅ **Base strategy class** with `generate_signal(market_data)`
- ✅ **Market data schema** (prices, entry_price, position, symbol, timestamp)
- ✅ **Strategy factory** to load strategies dynamically
- ✅ **Aggregator module** with 5 methods: unanimous, majority, any, conservative, weighted
- ✅ **Multi-strategy monitor** (collect signals from each, aggregate, send)
- ✅ **Config for aggregation** (method, weights, thresholds)

---

## 🔴 ChatGPT's Critical Feedback

### Must Fix (Before Implementation):

1. **Add `position` field to market_data** ✅ (Claude did this)
   - Current: `"entry_price": float | None`
   - Better: Add `"position": str` ("LONG" or "NONE")
   - **Why:** SELL signal is only valid if position="LONG"

2. **Define signal semantics clearly**
   ```
   BUY = enter long position
   SELL = exit long position (or don't trade if no position)
   NO_TRADE = hold current position
   ```

3. **Fix "any" aggregation logic**
   - Current: "BUY if ≥1 BUY, SELL if ≥1 SELL"
   - Problem: What if both exist?
   - Fix: **SELL has priority** (risk-first design)
   ```python
   if any SELL:
       return SELL
   elif any BUY:
       return BUY
   else:
       return NO_TRADE
   ```

4. **Weighted aggregation normalization**
   - Constraint: `sum(weights) = 1`
   - Score range: `[-1, +1]`
   - Example:
     ```python
     weighted_score = sum(w * score for w, score in zip(weights, scores))
     # scores: BUY=+1, NO_TRADE=0, SELL=-1
     # if weighted_score ≥ 0.5 → BUY
     # if weighted_score ≤ -0.5 → SELL
     # else → NO_TRADE
     ```

5. **Add `name` property to strategies** ✅ (Claude likely did this)
   - Needed for: logging, telegram breakdown, weight lookup
   ```python
   @property
   def name(self) -> str:
       return "ema_crossover"
   ```

6. **Telegram breakdown format** (standardize)
   ```
   🧪 Strategy Signals:
   • EMA_CROSSOVER: BUY
   • RSI: NO_TRADE
   
   ⚙️ Aggregation: conservative
   🚨 FINAL SIGNAL: BUY
   ```

7. **Safe fallback** (if no strategies)
   ```python
   if not strategies:
       return SIGNAL_NO_TRADE
   ```

---

## ✅ Implementation Checklist

### Phase 6A: Fix & Validate Claude's Design

- [ ] Review `aggregator.py` for:
  - [ ] SELL priority in "any" method
  - [ ] Weighted normalization (weights sum to 1)
  - [ ] Score range [-1, 1] enforcement
  - [ ] Safe fallback for empty strategies

- [ ] Review `base.py` for:
  - [ ] Signal semantics documented
  - [ ] Position field in market_data
  - [ ] Strategy name property

- [ ] Review `strategy_factory.py` for:
  - [ ] Dynamic strategy loading
  - [ ] Error handling

### Phase 6B: Create First Strategy (EMA)

- [ ] Create `strategies/ema_crossover.py`
  - [ ] Inherit from base Strategy
  - [ ] Implement `generate_signal(market_data) → str`
  - [ ] Handle price history from market_data["prices"]
  - [ ] Use position tracking for SELL logic

### Phase 6C: Write Tests

- [ ] `tests/test_aggregator.py` (5 methods + edge cases)
- [ ] `tests/test_ema_strategy.py` (BUY/SELL/NO_TRADE + position logic)
- [ ] `tests/test_strategy_factory.py` (loading, fallback)

### Phase 6D: Integrate Into System

- [ ] Update `main.py` to use multi-strategy
- [ ] Update `monitor.py` (already done)
- [ ] Update config.py with aggregation settings
- [ ] Run full test suite (should be ≥59 tests)

### Phase 6E: Add RSI Strategy (Optional)

- [ ] Create `strategies/rsi.py`
- [ ] Add to `ACTIVE_STRATEGIES`
- [ ] Test aggregation with 2+ strategies

---

## 📁 File Structure (Claude's Design)

```
/strategiesBased System:
├── config.py (aggregation settings)
├── strategy/
│   ├── base.py (ABC for all strategies)
│   ├── ema_crossover.py (EMA implementation)
│   └── rsi.py (RSI implementation - Phase 6+)
├── aggregator.py (5 aggregation methods)
├── strategy_factory.py (dynamic loading)
├── monitor.py (multi-strategy monitor)
├── main.py (orchestrator)
├── tests/
│   ├── test_aggregator.py
│   ├── test_ema_strategy.py
│   └── test_strategy_factory.py
└── docs/
    └── PHASE_6_DESIGN.md (this doc)
```

---

## 🧪 Test Examples

### Aggregation Tests
```python
# test_aggregator.py

def test_unanimous_all_buy():
    signals = {"ema": "BUY", "rsi": "BUY"}
    assert aggregate(signals) == "BUY"

def test_unanimous_not_all_same():
    signals = {"ema": "BUY", "rsi": "NO_TRADE"}
    assert aggregate(signals) == "NO_TRADE"

def test_any_sell_priority():
    signals = {"ema": "BUY", "rsi": "SELL"}
    assert aggregate(signals) == "SELL"  # SELL takes priority

def test_conservative_requires_buy_majority():
    signals = {"ema": "BUY", "rsi": "BUY", "macd": "NO_TRADE"}
    assert aggregate(signals) == "BUY"  # 2/3 = majority

def test_weighted_normalization():
    weights = {"ema": 0.6, "rsi": 0.4}
    signals = {"ema": "BUY", "rsi": "SELL"}  # +1, -1
    score = 0.6 * 1 + 0.4 * (-1) = 0.2
    assert aggregate(signals, weights) == "NO_TRADE"  # between thresholds
```

### Strategy Tests
```python
# test_ema_strategy.py

def test_ema_buy_signal():
    market_data = {
        "prices": [100.0]*20 + [10.0]*9 + [200.0],
        "entry_price": None,
        "position": "NONE",
        "symbol": "bitcoin",
        "timestamp": "2026-03-28T...",
    }
    strategy = EMAStrategy()
    assert strategy.generate_signal(market_data) == "BUY"

def test_sell_ignored_when_no_position():
    market_data = {
        "prices": [200.0, 5.0],  # Crash
        "entry_price": None,
        "position": "NONE",  # No position
        "symbol": "bitcoin",
        "timestamp": "2026-03-28T...",
    }
    strategy = EMAStrategy()
    signal = strategy.generate_signal(market_data)
    # Should not force SELL if position=NONE
    assert signal != "SELL" or signal == "NO_TRADE"
```

---

## 📊 Decision Table: Aggregation Methods

| Method | Best For | Risk Level | Trades Often? |
|--------|----------|-----------|--------------|
| **unanimous** | High confidence | Low | Rarely |
| **majority** | Medium confidence | Medium | Sometimes |
| **any** | Aggressive | High | Very often |
| **conservative** | Balanced | Low-Medium | Moderate |
| **weighted** | Custom tuning | Depends | Custom |

---

## 🔄 Signal Flow (Multi-Strategy)

```
Real Price (CoinGecko)
       ↓
market_data = {
    prices: [66801, 66850, 67000, ...],
    entry_price: 100.0,
    position: "LONG",
    symbol: "bitcoin",
    timestamp: "2026-03-28T12:34:56Z"
}
       ↓
Strategy 1 (EMA) → "BUY"
Strategy 2 (RSI) → "NO_TRADE"
Strategy 3 (MACD) → "BUY"
       ↓
Aggregator (conservative method)
       ↓
2/3 BUY → "BUY" signal
       ↓
Check position logic
       ↓
Send Telegram alert (if signal changed)
       ↓
Log activity
       ↓
Save state (signal, price, position)
```

---

## 🧠 Position State Machine

```
NONE ──(BUY signal)──→ LONG
       ↑                 ↓
       └─(SELL signal)───┘
```

Rules:
- BUY when position=NONE → move to LONG + send alert
- SELL when position=LONG → move to NONE + send alert
- NO_TRADE → stay in current position (no action)
- SELL when position=NONE → ignore (no position to sell)

---

## 📤 Next Action

Based on Claude's response + ChatGPT's feedback:

### Must Do Before Coding:
1. Validate Claude's aggregator has SELL priority in "any" method
2. Confirm market_data has position field
3. Verify weights normalize to 1 in weighted method
4. Check strategy.name property exists

### Then Code:
1. Copy Claude's base, aggregator, factory files
2. Implement EMA strategy
3. Write tests
4. Integrate + validate all 59+ tests still pass

---

## 🚀 Success Criteria

- ✅ All 59+ tests passing
- ✅ 2+ strategies working
- ✅ Aggregation methods tested
- ✅ Position state tracked
- ✅ Telegram breakdown working
- ✅ No regressions from Phase 5

---

**This is now a production-grade multi-strategy system!** 🔥

