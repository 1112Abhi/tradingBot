# ✅ Phase 6: Design Validation Checklist

**Purpose:** Validate Claude's multi-strategy design against ChatGPT's critical feedback

**Status:** Pending review

---

## 🔴 CRITICAL FIXES (Must implement)

### 1. Position Field in Market Data
**ChatGPT Says:** Add explicit `"position": str` to disambiguate entry_price

**Files to Check:**
- [ ] `strategy/base.py` - MarketData TypedDict definition
  - Must have: `position: str  # "LONG" or "NONE"`
  - Why: Can't just check `entry_price`, must know current position

**Example:**
```python
class MarketData(TypedDict):
    prices: List[float]
    entry_price: Optional[float]
    position: str  # ← ADD THIS
    symbol: str
    timestamp: str
```

---

### 2. "Any" Aggregation - SELL Priority
**ChatGPT Says:** SELL must dominate (risk-first design)

**Files to Check:**
- [ ] `aggregator.py` - `aggregate_any()` method
  - Current: `if any SELL: return SELL elif any BUY: return BUY`
  - ✅ This is correct (SELL has priority)

**Validation:**
```python
def test_any_sell_priority():
    signals = {"strat1": "BUY", "strat2": "SELL"}
    result = aggregate_any(signals)
    assert result == "SELL"  # ← Must pass
```

---

### 3. Weighted Aggregation - Normalization
**ChatGPT Says:** 
- Weights must sum to 1
- Scores must be in [-1, +1]
- Mapping: BUY=+1, NO_TRADE=0, SELL=-1

**Files to Check:**
- [ ] `aggregator.py` - `aggregate_weighted()` method
  - Must validate: `sum(weights.values()) == 1`
  - Must map signals: BUY→+1, NO_TRADE→0, SELL→-1
  - Must compute: `weighted_score = sum(w * score for w, score in ...)`

**Validation:**
```python
def test_weighted_normalization():
    weights = {"ema": 0.6, "rsi": 0.4}
    assert sum(weights.values()) == 1.0  # ← Must pass

def test_weighted_signal_mapping():
    assert signal_to_score("BUY") == 1
    assert signal_to_score("NO_TRADE") == 0
    assert signal_to_score("SELL") == -1

def test_weighted_score_in_range():
    # Any weighted sum of [-1, 0, 1] stays in [-1, 1]
    pass
```

---

### 4. Signal Semantics Documentation
**ChatGPT Says:** Define clearly in docstrings

**Files to Check:**
- [ ] `strategy/base.py` - Module or class docstring

**Required Text:**
```python
"""
Signal semantics:
- BUY: Enter long position (buy and hold)
- SELL: Exit long position (sell holdings, return to cash)
- NO_TRADE: Hold current position (do nothing)

Position state machine:
NONE ─(BUY)─→ LONG
      ↑         ↓
      └─(SELL)─┘

Rules:
- BUY only valid when position="NONE"
- SELL only valid when position="LONG"
- NO_TRADE doesn't change position
"""
```

---

## 🟡 SHOULD HAVES (Quality improvements)

### 5. Strategy Name Property
**ChatGPT Says:** Add `@property def name(self) -> str` to base class

**Files to Check:**
- [ ] `strategy/base.py` - BaseStrategy class
  - [ ] Has abstract property `name`
  - Example: EMA strategy returns `"ema_crossover"`

**Validation:**
```python
def test_strategy_has_name():
    strategy = EMAStrategy()
    assert strategy.name == "ema_crossover"
    assert isinstance(strategy.name, str)
```

---

### 6. Safe Fallback (No Strategies)
**ChatGPT Says:** If no strategies loaded, return NO_TRADE

**Files to Check:**
- [ ] `aggregator.py` - All aggregation methods
  - [ ] Handle empty `signals` dict
  - [ ] Return NO_TRADE if no strategies

**Validation:**
```python
def test_aggregate_empty_strategies():
    assert aggregate({}) == "NO_TRADE"  # ← Must pass

def test_aggregate_any_empty():
    assert aggregate_any({}) == "NO_TRADE"

def test_aggregate_unanimous_empty():
    assert aggregate_unanimous({}) == "NO_TRADE"
```

---

### 7. Telegram Breakdown Format
**ChatGPT Says:** Standardize output format

**Files to Check:**
- [ ] `aggregator.py` - `format_breakdown()` function
  - Should output:
    ```
    🧪 Strategy Signals:
    • ema_crossover: BUY
    • rsi: NO_TRADE
    
    ⚙️ Aggregation: conservative
    🚨 FINAL SIGNAL: BUY
    ```

**Validation:**
```python
def test_breakdown_format():
    result = format_breakdown(
        {"ema": "BUY", "rsi": "NO_TRADE"},
        final_signal="BUY",
        method="conservative"
    )
    assert "🧪 Strategy Signals:" in result
    assert "ema: BUY" in result
    assert "rsi: NO_TRADE" in result
    assert "🚨 FINAL SIGNAL: BUY" in result
```

---

### 8. Position Tracking in State
**ChatGPT Says:** Save position to state.json (implied)

**Files to Check:**
- [ ] `state.py` - `save_state()` and `get_state()`
  - [ ] Track `position` field
  - [ ] Persist to state.json

**Validation:**
```python
def test_save_position_state():
    save_state("BUY", 100.0, position="LONG")
    state = get_state()
    assert state["position"] == "LONG"
```

---

## 📋 Validation Script

Run this to check all items:

```bash
# Create test file
cat > validate_phase6.py << 'EOF'
import config
from strategy.base import MarketData
from aggregator import aggregate, format_breakdown
from strategy_factory import get_strategies

print("=" * 60)
print("🔍 PHASE 6 DESIGN VALIDATION")
print("=" * 60)

# 1. Check MarketData has position
print("\n✓ Check 1: MarketData schema")
try:
    md = MarketData(prices=[100], entry_price=100, position="LONG", symbol="btc", timestamp="2026-03-28T...")
    print("  ✅ MarketData has 'position' field")
except:
    print("  ❌ MarketData missing 'position' field")

# 2. Check SELL priority in any
print("\n✓ Check 2: SELL priority in 'any' aggregation")
result = aggregate({"s1": "BUY", "s2": "SELL"}, method="any")
if result == "SELL":
    print("  ✅ SELL has priority")
else:
    print(f"  ❌ Expected SELL, got {result}")

# 3. Check weighted normalization
print("\n✓ Check 3: Weighted normalization")
weights = config.STRATEGY_WEIGHTS or {}
if weights:
    total = sum(weights.values())
    if abs(total - 1.0) < 0.001:
        print(f"  ✅ Weights sum to {total}")
    else:
        print(f"  ❌ Weights sum to {total}, expected 1.0")
else:
    print("  ⚠️  No weights configured (OK for first run)")

# 4. Check empty strategies
print("\n✓ Check 4: Safe fallback (empty strategies)")
result = aggregate({})
if result == "NO_TRADE":
    print("  ✅ Empty strategies returns NO_TRADE")
else:
    print(f"  ❌ Expected NO_TRADE, got {result}")

# 5. Check strategy names
print("\n✓ Check 5: Strategy name property")
strategies = get_strategies()
for s in strategies:
    if hasattr(s, 'name'):
        print(f"  ✅ {s.name} has name property")
    else:
        print(f"  ❌ Strategy missing name property")

# 6. Check breakdown format
print("\n✓ Check 6: Telegram breakdown format")
breakdown = format_breakdown({"ema": "BUY", "rsi": "NO_TRADE"}, "BUY")
if "🧪" in breakdown and "Strategy Signals" in breakdown:
    print("  ✅ Breakdown format looks good")
else:
    print("  ❌ Breakdown format missing emojis/structure")

print("\n" + "=" * 60)
print("✅ VALIDATION COMPLETE")
print("=" * 60)
EOF

python validate_phase6.py
```

---

## 🧩 Review Files

**Priority Order:**
1. `strategy/base.py` - Check MarketData, signal semantics, name property
2. `aggregator.py` - Check all 5 methods, SELL priority, normalization, format
3. `strategy_factory.py` - Check error handling
4. `state.py` - Check position persistence
5. `monitor copy.py` - Check integration

---

## ✅ Sign-Off Checklist

When all items complete:
- [ ] Position field in market_data
- [ ] SELL priority in "any"
- [ ] Weighted normalization validated
- [ ] Signal semantics documented
- [ ] Strategy name property exists
- [ ] Safe fallback for empty
- [ ] Telegram format standardized
- [ ] Position tracking in state
- [ ] All 8 items in validation script pass
- [ ] No regressions from Phase 5

**Then proceed to Phase 6 implementation!** 🚀

