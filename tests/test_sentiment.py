# tests/test_sentiment.py — Tests for the sentiment module
#
# All external API calls are mocked — tests run offline.

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ── fear_greed ──────────────────────────────────────────────────────────────

class TestFearGreed(unittest.TestCase):

    def setUp(self):
        # Clear module cache between tests
        import sentiment.fear_greed as fg
        fg._cache = None

    def test_score_to_signal_extreme_fear(self):
        # Crowd very bearish → negative crowd sentiment
        from sentiment.fear_greed import score_to_signal
        self.assertEqual(score_to_signal(10), -1.0)
        self.assertEqual(score_to_signal(24), -1.0)

    def test_score_to_signal_fear(self):
        from sentiment.fear_greed import score_to_signal
        self.assertEqual(score_to_signal(25), -0.5)
        self.assertEqual(score_to_signal(44), -0.5)

    def test_score_to_signal_neutral(self):
        from sentiment.fear_greed import score_to_signal
        self.assertEqual(score_to_signal(45), 0.0)
        self.assertEqual(score_to_signal(55), 0.0)

    def test_score_to_signal_greed(self):
        from sentiment.fear_greed import score_to_signal
        self.assertEqual(score_to_signal(56), 0.5)
        self.assertEqual(score_to_signal(74), 0.5)

    def test_score_to_signal_extreme_greed(self):
        # Crowd very bullish → positive crowd sentiment → skip MR entry
        from sentiment.fear_greed import score_to_signal
        self.assertEqual(score_to_signal(75), 1.0)
        self.assertEqual(score_to_signal(100), 1.0)

    @patch("sentiment.fear_greed.requests.get")
    def test_fetch_returns_value_and_label(self, mock_get):
        mock_get.return_value.json.return_value = {
            "data": [{"value": "26", "value_classification": "Fear"}]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from sentiment.fear_greed import fetch
        value, label = fetch()
        self.assertEqual(value, 26)
        self.assertEqual(label, "Fear")

    @patch("sentiment.fear_greed.requests.get")
    def test_fetch_caches_result(self, mock_get):
        mock_get.return_value.json.return_value = {
            "data": [{"value": "30", "value_classification": "Fear"}]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from sentiment.fear_greed import fetch
        fetch()
        fetch()  # second call should use cache
        self.assertEqual(mock_get.call_count, 1)

    @patch("sentiment.fear_greed.requests.get")
    def test_fetch_raises_on_error(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        from sentiment.fear_greed import fetch
        with self.assertRaises(RuntimeError):
            fetch()


# ── funding_rate ────────────────────────────────────────────────────────────

class TestFundingRate(unittest.TestCase):

    def setUp(self):
        import sentiment.funding_rate as fr
        fr._cache = {}

    def test_score_to_signal_crowded_long(self):
        # Longs paying shorts → crowd bullish → positive crowd sentiment
        from sentiment.funding_rate import score_to_signal
        self.assertEqual(score_to_signal(0.001), 0.8)

    def test_score_to_signal_mild_long(self):
        from sentiment.funding_rate import score_to_signal
        self.assertEqual(score_to_signal(0.0003), 0.3)

    def test_score_to_signal_neutral(self):
        from sentiment.funding_rate import score_to_signal
        self.assertEqual(score_to_signal(0.0001), 0.0)
        self.assertEqual(score_to_signal(-0.00005), 0.0)

    def test_score_to_signal_mild_short(self):
        from sentiment.funding_rate import score_to_signal
        self.assertEqual(score_to_signal(-0.0002), -0.3)

    def test_score_to_signal_crowded_short(self):
        # Shorts paying longs → crowd bearish → negative crowd sentiment
        from sentiment.funding_rate import score_to_signal
        self.assertEqual(score_to_signal(-0.001), -0.8)

    @patch("sentiment.funding_rate.requests.get")
    def test_fetch_returns_rate_and_label(self, mock_get):
        mock_get.return_value.json.return_value = [
            {"fundingRate": "-0.00003143", "symbol": "BTCUSDT", "fundingTime": 0}
        ]
        mock_get.return_value.raise_for_status = MagicMock()

        from sentiment.funding_rate import fetch
        rate, label = fetch("BTCUSDT")
        self.assertAlmostEqual(rate, -0.00003143, places=8)
        self.assertEqual(label, "neutral")

    @patch("sentiment.funding_rate.requests.get")
    def test_fetch_labels_crowded_long(self, mock_get):
        mock_get.return_value.json.return_value = [
            {"fundingRate": "0.001", "symbol": "BTCUSDT", "fundingTime": 0}
        ]
        mock_get.return_value.raise_for_status = MagicMock()

        from sentiment.funding_rate import fetch
        _, label = fetch("BTCUSDT")
        self.assertEqual(label, "crowded_long")


# ── deribit ─────────────────────────────────────────────────────────────────

class TestDeribit(unittest.TestCase):

    def setUp(self):
        import sentiment.deribit as d
        d._cache = {}

    def test_dvol_signal_high_fear(self):
        # High DVOL = panic = crowd bearish → negative crowd sentiment
        from sentiment.deribit import dvol_signal
        self.assertAlmostEqual(dvol_signal(85), -0.8)

    def test_dvol_signal_low_vol(self):
        # Low DVOL = complacency = crowd bullish → positive crowd sentiment
        from sentiment.deribit import dvol_signal
        self.assertAlmostEqual(dvol_signal(40), 0.3)

    def test_dvol_signal_neutral(self):
        from sentiment.deribit import dvol_signal
        self.assertAlmostEqual(dvol_signal(60), 0.0)

    def test_put_call_signal_heavy_puts(self):
        # Heavy puts = crowd hedging/bearish → negative crowd sentiment
        from sentiment.deribit import put_call_signal
        self.assertAlmostEqual(put_call_signal(1.5), -0.6)

    def test_put_call_signal_fomo_calls(self):
        # FOMO calls = crowd bullish → positive crowd sentiment
        from sentiment.deribit import put_call_signal
        self.assertAlmostEqual(put_call_signal(0.3), 0.6)

    def test_put_call_signal_neutral(self):
        from sentiment.deribit import put_call_signal
        self.assertAlmostEqual(put_call_signal(0.6), 0.0)

    @patch("sentiment.deribit._fetch_put_call_ratio")
    @patch("sentiment.deribit._fetch_dvol")
    def test_fetch_returns_tuple(self, mock_dvol, mock_pc):
        mock_dvol.return_value = 46.1   # 46.1 < 50 → "low_vol"
        mock_pc.return_value   = 0.50

        from sentiment.deribit import fetch
        dvol, pc, label = fetch("BTC")
        self.assertAlmostEqual(dvol, 46.1)
        self.assertAlmostEqual(pc,   0.50)
        self.assertEqual(label, "low_vol")


# ── aggregator ───────────────────────────────────────────────────────────────

class TestAggregator(unittest.TestCase):

    def _mock_sources(self, fg_val=26, fg_label="Fear", funding=-0.00003,
                      dvol=46.0, pc=0.50, news_score=-0.1):
        """Patch all sentiment sources with fixed values."""
        patches = [
            patch("sentiment.fear_greed.fetch",    return_value=(fg_val, fg_label)),
            patch("sentiment.funding_rate.fetch",  return_value=(funding, "neutral")),
            patch("sentiment.deribit.fetch",       return_value=(dvol, pc, "neutral")),
            patch("sentiment.news.fetch",          return_value=(news_score, "Somewhat-Bearish")),
        ]
        return patches

    def test_composite_in_fear_scenario(self):
        """F&G=26 (Fear) → crowd bearish → composite negative → MR entry allowed."""
        patches = self._mock_sources(fg_val=26, fg_label="Fear", funding=0.0,
                                     dvol=60.0, pc=0.7, news_score=0.0)
        started = [p.start() for p in patches]
        try:
            from sentiment import aggregator
            result = aggregator.fetch("BTCUSDT")
            self.assertLess(result.composite, 0)
            self.assertFalse(result.should_skip_mr_entry())
        finally:
            for p in patches:
                p.stop()

    def test_composite_in_greed_scenario(self):
        """F&G=85 (Extreme Greed) + crowded long funding → crowd bullish → skip MR."""
        patches = self._mock_sources(fg_val=85, fg_label="Extreme Greed",
                                     funding=0.001, dvol=40.0, pc=0.3, news_score=0.4)
        started = [p.start() for p in patches]
        try:
            from sentiment import aggregator
            result = aggregator.fetch("BTCUSDT")
            self.assertGreater(result.composite, 0)
            self.assertTrue(result.should_skip_mr_entry())
        finally:
            for p in patches:
                p.stop()

    def test_partial_failure_still_returns_result(self):
        """If one source fails, composite is computed from remaining sources."""
        with patch("sentiment.fear_greed.fetch", return_value=(26, "Fear")), \
             patch("sentiment.funding_rate.fetch", side_effect=RuntimeError("timeout")), \
             patch("sentiment.deribit.fetch", return_value=(46.0, 0.50, "neutral")), \
             patch("sentiment.news.fetch", return_value=(0.0, "Neutral")):
            from sentiment import aggregator
            result = aggregator.fetch("BTCUSDT")
            self.assertIn("funding_rate", result.errors)
            self.assertNotIn("fear_greed", result.errors)
            # composite still valid from remaining sources
            self.assertIsInstance(result.composite, float)

    def test_mr_sizing_multiplier_extreme_fear(self):
        """Extreme fear scenario → crowd very bearish → composite < -0.2 → 1.2x size."""
        # F&G=10 (Extreme Fear) → -1.0, funding=-0.001 (crowded short) → -0.8,
        # dvol=90 (panic) → -0.8, pc=1.5 (heavy puts) → -0.6, news=-0.5 → -0.5
        # All negative → composite very negative → 1.2x multiplier
        patches = self._mock_sources(fg_val=10, fg_label="Extreme Fear",
                                     funding=-0.001, dvol=90.0, pc=1.5, news_score=-0.5)
        started = [p.start() for p in patches]
        try:
            from sentiment import aggregator
            result = aggregator.fetch("BTCUSDT")
            self.assertLess(result.composite, -0.2)
            mult = result.mr_sizing_multiplier()
            self.assertGreaterEqual(mult, 1.0)
        finally:
            for p in patches:
                p.stop()

    def test_summary_contains_composite(self):
        patches = self._mock_sources()
        started = [p.start() for p in patches]
        try:
            from sentiment import aggregator
            result = aggregator.fetch("BTCUSDT")
            self.assertIn("composite=", result.summary())
        finally:
            for p in patches:
                p.stop()


# ── MR strategy with sentiment ───────────────────────────────────────────────

class TestMRWithSentiment(unittest.TestCase):

    def _prices(self, n=60, end_low=True):
        """Generate price series that will trigger RSI < 35 and price < EMA50."""
        import random
        random.seed(42)
        prices = [100.0]
        for _ in range(n - 1):
            prices.append(prices[-1] * (0.998 if end_low else 1.002))
        return prices

    def test_sentiment_disabled_by_default(self):
        """use_sentiment=False means sentiment is never checked."""
        from strategy.mean_reversion import MeanReversionStrategy
        s = MeanReversionStrategy()
        self.assertFalse(s.use_sentiment)

    def test_sentiment_blocks_entry_when_greedy(self):
        """When sentiment says skip, generate_signal returns NO_TRADE even if RSI oversold."""
        from strategy.mean_reversion import MeanReversionStrategy
        import config

        s = MeanReversionStrategy(use_sentiment=True, symbol="BTCUSDT")

        # Build a price series that genuinely triggers RSI < 35 and price < EMA50
        # Declining prices over 60 bars
        prices = [10000.0]
        for _ in range(59):
            prices.append(prices[-1] * 0.985)  # strong decline to get RSI very low

        with patch.object(s, "_sentiment_blocks_entry", return_value=True):
            signal = s.generate_signal({"prices": prices, "position": None})
        self.assertEqual(signal, config.SIGNAL_NO_TRADE)

    def test_sentiment_allows_entry_in_fear(self):
        """When sentiment allows, entry proceeds normally if RSI oversold."""
        from strategy.mean_reversion import MeanReversionStrategy
        import config

        s = MeanReversionStrategy(use_sentiment=True, symbol="BTCUSDT")

        prices = [10000.0]
        for _ in range(59):
            prices.append(prices[-1] * 0.985)

        with patch.object(s, "_sentiment_blocks_entry", return_value=False):
            signal = s.generate_signal({"prices": prices, "position": None})
        self.assertEqual(signal, config.SIGNAL_BUY)

    def test_sentiment_fails_open(self):
        """If sentiment API errors, entry is still allowed (fail open)."""
        from strategy.mean_reversion import MeanReversionStrategy
        import config

        s = MeanReversionStrategy(use_sentiment=True, symbol="BTCUSDT")

        prices = [10000.0]
        for _ in range(59):
            prices.append(prices[-1] * 0.985)

        with patch("sentiment.aggregator.fetch", side_effect=Exception("API down")):
            signal = s.generate_signal({"prices": prices, "position": None})
        self.assertEqual(signal, config.SIGNAL_BUY)


if __name__ == "__main__":
    unittest.main()
