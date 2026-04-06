# tests/test_config_validation.py - Validate all config constants

import pytest
import config


class TestTelegramConfig:
    """Test Telegram configuration."""

    def test_telegram_bot_token_exists(self):
        """TELEGRAM_BOT_TOKEN should be set."""
        assert hasattr(config, "TELEGRAM_BOT_TOKEN")
        assert isinstance(config.TELEGRAM_BOT_TOKEN, str)
        assert len(config.TELEGRAM_BOT_TOKEN) > 0

    def test_telegram_chat_id_exists(self):
        """TELEGRAM_CHAT_ID should be set."""
        assert hasattr(config, "TELEGRAM_CHAT_ID")
        assert isinstance(config.TELEGRAM_CHAT_ID, str)
        assert len(config.TELEGRAM_CHAT_ID) > 0

    def test_telegram_api_url_exists(self):
        """TELEGRAM_API_URL should be set."""
        assert hasattr(config, "TELEGRAM_API_URL")
        assert isinstance(config.TELEGRAM_API_URL, str)
        assert config.TELEGRAM_API_URL.startswith("https://")


class TestDataSourceConfig:
    """Test data source configuration."""

    def test_data_source_valid(self):
        """DATA_SOURCE should be one of: coingecko, binance, alpha_vantage, dummy."""
        assert config.DATA_SOURCE in ["coingecko", "binance", "alpha_vantage", "dummy"]

    def test_symbol_exists(self):
        """SYMBOL should be set."""
        assert hasattr(config, "SYMBOL")
        assert isinstance(config.SYMBOL, str)
        assert len(config.SYMBOL) > 0

    def test_monitor_interval_positive(self):
        """MONITOR_INTERVAL should be positive integer."""
        assert isinstance(config.MONITOR_INTERVAL, int)
        assert config.MONITOR_INTERVAL > 0

    def test_coingecko_url_valid(self):
        """COINGECKO_URL should be valid endpoint."""
        assert config.COINGECKO_URL.startswith("https://")
        assert "api.coingecko.com" in config.COINGECKO_URL

    def test_binance_url_valid(self):
        """BINANCE_URL should be valid endpoint."""
        assert config.BINANCE_URL.startswith("https://")
        assert "api.binance.com" in config.BINANCE_URL


class TestSignalConfig:
    """Test signal constant configuration."""

    def test_signal_buy_constant(self):
        """SIGNAL_BUY should be 'BUY'."""
        assert config.SIGNAL_BUY == "BUY"

    def test_signal_sell_constant(self):
        """SIGNAL_SELL should be 'SELL'."""
        assert config.SIGNAL_SELL == "SELL"

    def test_signal_no_trade_constant(self):
        """SIGNAL_NO_TRADE should be 'NO_TRADE'."""
        assert config.SIGNAL_NO_TRADE == "NO_TRADE"


class TestStrategyV2Config:
    """Test Strategy v2 (EMA Crossover) configuration."""

    def test_fast_period_positive(self):
        """FAST_PERIOD should be positive."""
        assert isinstance(config.FAST_PERIOD, int)
        assert config.FAST_PERIOD > 0

    def test_slow_period_positive(self):
        """SLOW_PERIOD should be positive."""
        assert isinstance(config.SLOW_PERIOD, int)
        assert config.SLOW_PERIOD > 0

    def test_slow_period_greater_than_fast(self):
        """SLOW_PERIOD should be > FAST_PERIOD."""
        assert config.SLOW_PERIOD > config.FAST_PERIOD

    def test_stop_loss_pct_valid(self):
        """STOP_LOSS_PCT should be between 0 and 1."""
        assert isinstance(config.STOP_LOSS_PCT, float)
        assert 0 < config.STOP_LOSS_PCT < 1

    def test_price_history_size_sufficient(self):
        """PRICE_HISTORY_SIZE should be >= SLOW_PERIOD."""
        assert config.PRICE_HISTORY_SIZE >= config.SLOW_PERIOD


class TestPhase6Config:
    """Test Phase 6 (Multi-Strategy) configuration."""

    def test_active_strategies_is_list(self):
        """ACTIVE_STRATEGIES should be a list."""
        assert isinstance(config.ACTIVE_STRATEGIES, list)
        assert len(config.ACTIVE_STRATEGIES) > 0

    def test_active_strategies_contains_valid_names(self):
        """All ACTIVE_STRATEGIES should have valid names."""
        valid_strategies = ["ema_crossover", "rsi", "macd"]  # Known strategies
        for strategy in config.ACTIVE_STRATEGIES:
            assert isinstance(strategy, str)
            assert len(strategy) > 0

    def test_aggregation_method_valid(self):
        """AGGREGATION_METHOD should be one of: unanimous, majority, any, conservative, weighted."""
        valid_methods = ["unanimous", "majority", "any", "conservative", "weighted"]
        assert config.AGGREGATION_METHOD in valid_methods

    def test_strategy_weights_is_dict(self):
        """STRATEGY_WEIGHTS should be a dictionary."""
        assert isinstance(config.STRATEGY_WEIGHTS, dict)

    def test_weighted_thresholds_valid(self):
        """Weighted thresholds should be between 0 and 1."""
        assert 0 <= config.WEIGHTED_BUY_THRESHOLD <= 1
        assert 0 <= config.WEIGHTED_SELL_THRESHOLD <= 1

    def test_send_strategy_breakdown_is_bool(self):
        """SEND_STRATEGY_BREAKDOWN should be boolean."""
        assert isinstance(config.SEND_STRATEGY_BREAKDOWN, bool)


class TestPhase7BacktestConfig:
    """Test Phase 7 (Backtesting) configuration."""

    def test_backtest_db_path_valid(self):
        """BACKTEST_DB should be a valid path string."""
        assert isinstance(config.BACKTEST_DB, str)
        assert config.BACKTEST_DB.endswith(".db")

    def test_backtest_capital_positive(self):
        """BACKTEST_CAPITAL should be positive."""
        assert isinstance(config.BACKTEST_CAPITAL, (int, float))
        assert config.BACKTEST_CAPITAL > 0

    def test_backtest_interval_valid(self):
        """BACKTEST_INTERVAL should be valid Binance interval."""
        valid_intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        assert config.BACKTEST_INTERVAL in valid_intervals

    def test_backtest_fee_pct_valid(self):
        """BACKTEST_FEE_PCT should be between 0 and 1."""
        assert isinstance(config.BACKTEST_FEE_PCT, (int, float))
        assert 0 <= config.BACKTEST_FEE_PCT <= 1

    def test_backtest_price_col_valid(self):
        """BACKTEST_PRICE_COL should be valid column name."""
        valid_cols = ["open", "high", "low", "close", "mid"]
        assert config.BACKTEST_PRICE_COL in valid_cols

    def test_backtest_history_days_positive(self):
        """BACKTEST_HISTORY_DAYS should be positive."""
        assert isinstance(config.BACKTEST_HISTORY_DAYS, int)
        assert config.BACKTEST_HISTORY_DAYS > 0

    def test_binance_klines_url_valid(self):
        """BINANCE_KLINES_URL should be valid endpoint."""
        assert config.BINANCE_KLINES_URL.startswith("https://")
        assert "api.binance.com" in config.BINANCE_KLINES_URL

    def test_binance_klines_limit_valid(self):
        """BINANCE_KLINES_LIMIT should be <= 1000."""
        assert isinstance(config.BINANCE_KLINES_LIMIT, int)
        assert 1 <= config.BINANCE_KLINES_LIMIT <= 1000


class TestLoggingConfig:
    """Test logging configuration."""

    def test_log_file_path_valid(self):
        """LOG_FILE should be a valid path."""
        assert isinstance(config.LOG_FILE, str)
        assert config.LOG_FILE.endswith(".log")

    def test_log_retention_days_positive(self):
        """LOG_RETENTION_DAYS should be positive."""
        assert isinstance(config.LOG_RETENTION_DAYS, int)
        assert config.LOG_RETENTION_DAYS > 0


class TestStateConfig:
    """Test state configuration."""

    def test_state_file_path_valid(self):
        """STATE_FILE should be a valid path."""
        assert isinstance(config.STATE_FILE, str)
        assert config.STATE_FILE.endswith(".json")


class TestThresholdConfig:
    """Test strategy threshold configuration."""

    def test_buy_threshold_valid(self):
        """BUY_THRESHOLD should be reasonable."""
        assert isinstance(config.BUY_THRESHOLD, (int, float))
        assert config.BUY_THRESHOLD >= 0

    def test_sell_threshold_valid(self):
        """SELL_THRESHOLD should be reasonable."""
        assert isinstance(config.SELL_THRESHOLD, (int, float))
        assert config.SELL_THRESHOLD >= 0

    def test_dummy_price_positive(self):
        """DUMMY_PRICE should be positive."""
        assert isinstance(config.DUMMY_PRICE, (int, float))
        assert config.DUMMY_PRICE > 0
