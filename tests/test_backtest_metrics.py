"""
tests/test_backtest_metrics.py - Backtest metrics tests

Tests for:
  - compute_metrics(): Full metrics pipeline
  - _compute_max_drawdown(): Peak-to-trough calculation
  - _compute_sharpe(): Annualised Sharpe ratio with volume adjustment
"""

import pytest
from backtest.metrics import compute_metrics, _compute_max_drawdown, _compute_sharpe


class TestComputeMaxDrawdown:
    """Test maximum drawdown calculation."""

    def test_no_trades_returns_zero(self):
        """No trades → drawdown is 0%."""
        dd = _compute_max_drawdown([], initial_capital=10000.0)
        assert dd == 0.0

    def test_all_winners_no_drawdown(self):
        """All winning trades → 0% drawdown."""
        trades = [
            {"pnl_dollar": 100.0},
            {"pnl_dollar": 50.0},
            {"pnl_dollar": 75.0},
        ]
        dd = _compute_max_drawdown(trades, initial_capital=10000.0)
        assert dd == 0.0

    def test_single_losing_trade(self):
        """Single loss creates drawdown."""
        trades = [{"pnl_dollar": -500.0}]  # 5% loss
        dd = _compute_max_drawdown(trades, initial_capital=10000.0)
        assert dd == pytest.approx(5.0, rel=1e-6)

    def test_drawdown_after_peak(self):
        """Drawdown is measured from peak (not initial capital)."""
        trades = [
            {"pnl_dollar": +1000.0},  # Peak: $11,000
            {"pnl_dollar": -500.0},   # Trough: $10,500
        ]
        dd = _compute_max_drawdown(trades, initial_capital=10000.0)
        # From peak (11,000) to trough (10,500): 500/11,000 ≈ 4.545%
        assert dd == pytest.approx(500 / 11000 * 100, rel=1e-6)

    def test_multiple_peaks_worst_drawdown(self):
        """Worst drawdown from any peak is returned."""
        trades = [
            {"pnl_dollar": +2000.0},   # Peak 1: $12,000
            {"pnl_dollar": -1000.0},   # Trough 1: $11,000 (8.3% DD)
            {"pnl_dollar": +5000.0},   # Peak 2: $16,000
            {"pnl_dollar": -3000.0},   # Trough 2: $13,000 (18.75% DD)
        ]
        dd = _compute_max_drawdown(trades, initial_capital=10000.0)
        # Worst is 3000 from peak of 16000 = 18.75%
        assert dd == pytest.approx(3000 / 16000 * 100, rel=1e-6)

    def test_recovery_after_drawdown(self):
        """Drawdown doesn't reset until new peak is reached."""
        trades = [
            {"pnl_dollar": -5000.0},   # Draw from 10k to 5k: 50% DD
            {"pnl_dollar": +2000.0},   # Recover to 7k: still 50% DD from peak
            {"pnl_dollar": +5000.0},   # Recover to 12k: new peak, DD resets
            {"pnl_dollar": -1000.0},   # 1k from 12k ≈ 8.3% DD
        ]
        dd = _compute_max_drawdown(trades, initial_capital=10000.0)
        # Peak was 10k, lowest was 5k = 50% DD
        assert dd == pytest.approx(50.0, rel=1e-6)

    def test_large_initial_capital(self):
        """Drawdown percentage is calculated on loss amount, not capital."""
        # For a $1000 loss on $10,000 → 10% drawdown
        trades = [
            {"pnl_dollar": -1000.0},
        ]
        dd_small = _compute_max_drawdown(trades, initial_capital=10000.0)
        # For a $1000 loss on $1,000,000 → 0.1% drawdown
        dd_large = _compute_max_drawdown(trades, initial_capital=1000000.0)
        # Drawdown % depends on the loss relative to capital
        assert dd_small == pytest.approx(10.0, rel=1e-6)
        assert dd_large == pytest.approx(0.1, rel=1e-6)


class TestComputeSharpe:
    """Test annualised Sharpe ratio calculation."""

    def test_fewer_than_two_trades_returns_zero(self):
        """Fewer than 2 trades → Sharpe = 0."""
        sharpe = _compute_sharpe([], tradeable_bars=100, interval="1h")
        assert sharpe == 0.0

        sharpe = _compute_sharpe([{"pnl_pct": 1.0}], tradeable_bars=100, interval="1h")
        assert sharpe == 0.0

    def test_zero_variance_returns_zero(self):
        """All trades with same return → std=0, Sharpe=0."""
        trades = [{"pnl_pct": 1.5} for _ in range(10)]
        sharpe = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        assert sharpe == 0.0

    def test_positive_returns_positive_sharpe(self):
        """Positive returns → positive Sharpe."""
        trades = [
            {"pnl_pct": 2.0},
            {"pnl_pct": 3.0},
            {"pnl_pct": 1.5},
        ]
        sharpe = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        assert sharpe > 0.0

    def test_negative_returns_negative_sharpe(self):
        """Negative returns → negative Sharpe."""
        trades = [
            {"pnl_pct": -2.0},
            {"pnl_pct": -3.0},
            {"pnl_pct": -1.5},
        ]
        sharpe = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        assert sharpe < 0.0

    def test_annualisation_factor_1h(self):
        """Sharpe is annualised using bars_per_year for 1h interval."""
        trades = [
            {"pnl_pct": 1.0},
            {"pnl_pct": 2.0},
        ]
        # 1h interval: 8760 bars per year
        # 2 trades / 100 bars * 8760 bars/year = 175.2 trades/year
        sharpe = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        assert sharpe > 0.0

    def test_annualisation_factor_1d(self):
        """Sharpe is annualised using bars_per_year for 1d interval."""
        trades = [
            {"pnl_pct": 1.0},
            {"pnl_pct": 2.0},
        ]
        # 1d interval: 365 bars per year
        # Different annualisation gives different Sharpe
        sharpe_1h = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        sharpe_1d = _compute_sharpe(trades, tradeable_bars=100, interval="1d")
        # 1h has more bars per year → higher annualisation → higher Sharpe
        assert sharpe_1h > sharpe_1d

    def test_sharpe_with_mixed_returns(self):
        """Sharpe handles mix of positive and negative returns."""
        trades = [
            {"pnl_pct": 3.0},
            {"pnl_pct": -1.0},
            {"pnl_pct": 2.0},
            {"pnl_pct": -0.5},
        ]
        sharpe = _compute_sharpe(trades, tradeable_bars=50, interval="1h")
        # Mean ≈ 0.875, should have some value
        assert isinstance(sharpe, float)

    def test_sharpe_high_frequency_annualized(self):
        """Higher frequency (more bars/year) → higher annualisation."""
        trades = [
            {"pnl_pct": 1.0},
            {"pnl_pct": 2.0},
        ]
        sharpe_1m = _compute_sharpe(trades, tradeable_bars=100, interval="1m")
        sharpe_1h = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        # 1m has more bars/year → higher annualisation
        assert sharpe_1m > sharpe_1h

    def test_sharpe_rounded_to_4_decimals(self):
        """Sharpe ratio is rounded to 4 decimal places."""
        trades = [
            {"pnl_pct": 1.234567},
            {"pnl_pct": 2.345678},
        ]
        sharpe = _compute_sharpe(trades, tradeable_bars=100, interval="1h")
        # Check that it's a float with 4 decimals
        assert isinstance(sharpe, float)
        assert len(str(sharpe).split(".")[1]) <= 4


class TestComputeMetrics:
    """Test full metrics computation pipeline."""

    def test_metrics_no_trades(self):
        """Metrics with no trades."""
        metrics = compute_metrics(
            trades=[],
            initial_capital=10000.0,
            final_capital=10000.0,
            total_bars=100,
            warmup_bars=14,
            interval="1h",
        )
        assert metrics["total_trades"] == 0
        assert metrics["winning_trades"] == 0
        assert metrics["win_rate_pct"] == 0.0
        assert metrics["total_return_pct"] == 0.0
        assert metrics["max_drawdown_pct"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0

    def test_metrics_all_wins(self):
        """Metrics with all winning trades."""
        trades = [
            {"pnl_dollar": 100.0, "pnl_pct": 1.0},
            {"pnl_dollar": 200.0, "pnl_pct": 2.0},
        ]
        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=10300.0,
            total_bars=100,
            warmup_bars=14,
            interval="1h",
        )
        assert metrics["total_trades"] == 2
        assert metrics["winning_trades"] == 2
        assert metrics["win_rate_pct"] == 100.0
        assert metrics["total_return_pct"] == 3.0
        assert metrics["max_drawdown_pct"] == 0.0

    def test_metrics_mixed_trades(self):
        """Metrics with mix of wins and losses."""
        trades = [
            {"pnl_dollar": 100.0, "pnl_pct": 1.0},   # Win
            {"pnl_dollar": -50.0, "pnl_pct": -0.5},  # Loss
            {"pnl_dollar": 150.0, "pnl_pct": 1.5},   # Win
        ]
        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=10200.0,
            total_bars=200,
            warmup_bars=14,
            interval="1h",
        )
        assert metrics["total_trades"] == 3
        assert metrics["winning_trades"] == 2
        assert metrics["win_rate_pct"] == pytest.approx(66.67, rel=1e-2)
        assert metrics["total_return_pct"] == 2.0

    def test_metrics_return_calculation(self):
        """Return is calculated as (final - initial) / initial."""
        initial = 10000.0
        final = 11500.0
        metrics = compute_metrics(
            trades=[],
            initial_capital=initial,
            final_capital=final,
            total_bars=100,
            warmup_bars=14,
            interval="1h",
        )
        expected_return = (final - initial) / initial * 100
        assert metrics["total_return_pct"] == pytest.approx(expected_return, rel=1e-6)

    def test_metrics_tradeable_bars(self):
        """Tradeable bars = total - warmup."""
        metrics = compute_metrics(
            trades=[],
            initial_capital=10000.0,
            final_capital=10000.0,
            total_bars=1000,
            warmup_bars=50,
            interval="1h",
        )
        assert metrics["total_bars"] == 1000
        assert metrics["warmup_bars"] == 50
        assert metrics["tradeable_bars"] == 950

    def test_metrics_includes_sharpe_ratio(self):
        """Metrics includes annualised Sharpe ratio."""
        trades = [
            {"pnl_dollar": 100.0, "pnl_pct": 1.0},
            {"pnl_dollar": 50.0, "pnl_pct": 0.5},
        ]
        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=10150.0,
            total_bars=200,
            warmup_bars=14,
            interval="1h",
        )
        assert "sharpe_ratio" in metrics
        assert isinstance(metrics["sharpe_ratio"], float)

    def test_metrics_rounding(self):
        """Metrics are rounded appropriately."""
        trades = [
            {"pnl_dollar": 123.456, "pnl_pct": 1.23456},
            {"pnl_dollar": 234.567, "pnl_pct": 2.34567},
        ]
        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=10357.89,
            total_bars=100,
            warmup_bars=14,
            interval="1h",
        )
        # Check rounding to 2 decimal places where expected
        assert metrics["win_rate_pct"] == 100.0
        assert len(str(metrics["total_return_pct"]).split(".")[1]) <= 2

    def test_metrics_realistic_backtest_scenario(self):
        """Test with realistic backtest scenario (V4 baseline)."""
        # Simulate V4: 27 trades, 9 wins, +2.84% return
        winning_trades = [
            {"pnl_dollar": d, "pnl_pct": d / 10000 * 100}
            for d in [150, 120, 180, 90, 200, 140, 160, 110, 130]
        ]
        losing_trades = [
            {"pnl_dollar": d, "pnl_pct": d / 10000 * 100}
            for d in [-80, -60, -50, -70, -40, -65, -45, -75, -55, -85, -70, -50, -60, -55, -65, -75, -45, -40]
        ]
        trades = winning_trades + losing_trades

        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=10284.37,
            total_bars=2189,
            warmup_bars=50,
            interval="4h",
        )

        assert metrics["total_trades"] == 27
        assert metrics["winning_trades"] == 9
        assert metrics["win_rate_pct"] == pytest.approx(33.3, rel=1e-2)
        assert metrics["total_return_pct"] == pytest.approx(2.84, rel=1e-2)
        assert metrics["tradeable_bars"] == 2139


class TestMetricsEdgeCases:
    """Edge cases and boundary conditions."""

    def test_metrics_extreme_loss(self):
        """Metrics handle massive drawdown."""
        trades = [{"pnl_dollar": -9000.0, "pnl_pct": -90.0}]
        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=1000.0,
            total_bars=100,
            warmup_bars=14,
            interval="1h",
        )
        assert metrics["max_drawdown_pct"] == pytest.approx(90.0, rel=1e-6)

    def test_metrics_extreme_gain(self):
        """Metrics handle massive gains."""
        trades = [{"pnl_dollar": 90000.0, "pnl_pct": 900.0}]
        metrics = compute_metrics(
            trades=trades,
            initial_capital=10000.0,
            final_capital=100000.0,
            total_bars=100,
            warmup_bars=14,
            interval="1h",
        )
        assert metrics["total_return_pct"] == pytest.approx(900.0, rel=1e-6)

    def test_metrics_single_bar_backtest(self):
        """Metrics with minimal bars (edge case)."""
        metrics = compute_metrics(
            trades=[],
            initial_capital=10000.0,
            final_capital=10000.0,
            total_bars=1,
            warmup_bars=0,
            interval="1h",
        )
        assert metrics["tradeable_bars"] == 1
        assert metrics["total_bars"] == 1
