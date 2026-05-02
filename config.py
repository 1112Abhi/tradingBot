# config.py - Trading Bot Constants

# --- Telegram ---
TELEGRAM_BOT_TOKEN = "8457642819:AAF5X-dTreX8R6nf3Kb1uSc89p7mHGVDxyM"
TELEGRAM_CHAT_ID = "8747874143"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# --- Data Source ---
DATA_SOURCE = "coingecko"           # "coingecko" | "binance" | "alpha_vantage"
SYMBOL = "bitcoin"                  # CoinGecko: "bitcoin" | Binance: "BTCUSDT"
MONITOR_INTERVAL = 60               # seconds between price checks
ALPHA_VANTAGE_KEY = "your_key_here" # only needed for Alpha Vantage

# --- Strategy Thresholds ---
BUY_THRESHOLD = 90.0
SELL_THRESHOLD = 50.0

# --- Phase 1 fallback ---
DUMMY_PRICE = 100.0

# --- Signals ---
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_NO_TRADE = "NO_TRADE"

# --- Logging ---
LOG_FILE         = "trading_bot.log"
LOG_RETENTION_DAYS = 7
LOG_WATCHER_FILE = "logs/watcher.log"   # Phase 7.6 live watcher log

# --- State ---
STATE_FILE = "state.json"

# --- API URLs ---
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"

# --- Telegram Bot Listener ---
POLLING_INTERVAL = 2  # seconds between message polls
POLLING_TIMEOUT = 30  # long polling timeout
AVAILABLE_SYMBOLS = ["bitcoin", "ethereum", "cardano", "solana"]  # CoinGecko IDs

# --- Strategy v2: Dual EMA Crossover (Phase 5) ---
STRATEGY_VERSION = 2                # 1 = simple threshold, 2 = EMA crossover ← ACTIVE
FAST_PERIOD = 12                    # Fast EMA lookback (bars) - v2: was 5
SLOW_PERIOD = 26                    # Slow EMA lookback (bars) - v2: was 20
TREND_PERIOD = 50                   # Trend EMA lookback (bars) - NEW: for trend filter
STOP_LOSS_PCT = 0.05                # 5% drop from entry triggers forced SELL
PRICE_HISTORY_SIZE = 50             # Buffer size for EMA calculation - updated for EMA50

# --- Phase 6: Multi-Strategy Aggregation ---
ACTIVE_STRATEGIES = ["ema_crossover"]  # List of strategy names to load and run
AGGREGATION_METHOD = "conservative"     # unanimous|majority|any|conservative|weighted
STRATEGY_WEIGHTS = {}                   # e.g., {"ema_crossover": 1.0} (auto-normalized)
WEIGHTED_BUY_THRESHOLD = 0.5            # Score must be >= this to trigger BUY
WEIGHTED_SELL_THRESHOLD = 0.5           # Score must be <= -this to trigger SELL
SEND_STRATEGY_BREAKDOWN = True          # Include per-strategy signals in Telegram message

# --- Phase 7.1: Backtesting Data Layer ---
BACKTEST_DB = "backtest.db"             # SQLite database for price history
BACKTEST_CAPITAL = 10_000.0             # Starting capital for backtest
BACKTEST_INTERVAL = "1h"                # Candle interval (1h, 4h, 1d, etc.)
BACKTEST_FEE_PCT = 0.0005               # Taker fee: 0.05% per leg (Delta Exchange)
BACKTEST_PRICE_COL = "mid"              # Price column for engine: "mid", "close", etc.
BACKTEST_HISTORY_DAYS = 1095            # Days of history to fetch: 1095 days = 3 years
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"  # Binance klines endpoint
BINANCE_KLINES_LIMIT = 1000             # Max bars per Binance API request

# --- Phase 7.2: Backtesting Engine ---
POSITION_SIZE_FRACTION = 0.10           # Fraction of capital per trade (10%)
BACKTEST_MIN_WINDOW = 27                # Minimum bars before engine starts signalling (>= SLOW_PERIOD+1)

# --- Phase 7.3: Risk Manager (Asymmetric Exits) ---
# V3: Replace signal-only exit with asymmetric stop/take-profit
ASYMMETRIC_STOP_LOSS_PCT = 0.02         # 2% stop loss (v3: tighter than v2's 5%)
ASYMMETRIC_TAKE_PROFIT_PCT = 0.05       # 5% take profit (1:2.5 reward/risk ratio)

# --- V4+: Stop/TP Optimization Grid ---
# Test variants: 1.5/4.5, 2/6, 2/5
BACKTEST_STOP_LOSS_PCT = 0.015          # Default: 1.5% (tight) - change for variants
BACKTEST_TAKE_PROFIT_PCT = 0.060        # Default: 6.0% (optimised via tp_grid.py)

# --- Phase 7.5: Realistic Execution ---
SLIPPAGE_RATE      = 0.0002            # Slippage: 0.02% (buy higher, sell lower)
LEVERAGE           = 1.0               # Leverage multiplier (1.0 = no leverage)

# --- Phase 7.3: ATR-based Risk Manager ---
RISK_PER_TRADE       = 0.01             # Risk 1% of capital per trade
MAX_CAPITAL_FRACTION = 0.20             # Hard cap: max 20% of capital per position
ATR_PERIOD           = 14               # ATR lookback period (bars)
ATR_REFERENCE_PCT    = 0.01             # "Normal" ATR as fraction of price (1% for BTC 4h)

# --- V5: RSI Entry Filter ---
RSI_PERIOD = 14                         # RSI lookback period
RSI_BUY_MIN = 40                        # BUY blocked if RSI below this (no momentum)
RSI_BUY_MAX = 65                        # BUY blocked if RSI above this (overbought)

# --- Phase 8: Portfolio Allocation ---
PORTFOLIO_MAX_POSITIONS        = 2      # Max concurrent open positions across all strategies
PORTFOLIO_TOTAL_FRACTION       = 0.50   # Max 50% of capital deployed at once
PORTFOLIO_PER_STRATEGY_FRACTION= 0.25   # Max 25% of capital per strategy

# --- Phase 9: Sentiment ---
import os as _os
ALPHAVANTAGE_API_KEY = _os.getenv("ALPHAVANTAGE_API_KEY", "1D3Z2OL8C77GODLY")
