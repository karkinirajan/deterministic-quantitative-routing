import numpy as np
import pytest

from src.orchestrator.hooks import LifecycleHooks
from src.orchestrator.stability import calculate_hamming_distance, check_stability
from src.router.mock_router import MockSemanticRouter
from src.utils.data_loader import load_data
from src.utils.smoothing import smooth_regime


class TestHamming:
    def test_counts_differing_positions(self):
        assert calculate_hamming_distance(np.array([0, 1, 1, 0]), np.array([0, 0, 1, 1])) == 2
        assert calculate_hamming_distance(np.array([1, 1]), np.array([1, 1])) == 0
        assert calculate_hamming_distance(np.array([1, 1]), np.array([0, 0])) == 2

    def test_returns_a_plain_int(self):
        assert type(calculate_hamming_distance(np.array([0, 1]), np.array([1, 1]))) is int

    def test_lengths_must_match(self):
        with pytest.raises(ValueError, match="same length"):
            calculate_hamming_distance(np.array([0, 1]), np.array([0, 1, 1]))


class TestCheckStability:
    def test_the_threshold_is_one_percent_of_the_length_inclusive(self):
        assert check_stability(1, 100) is True  # 1 <= 1.0
        assert check_stability(2, 100) is False
        assert check_stability(0, 100) is True
        assert check_stability(5, 500) is True
        assert check_stability(6, 500) is False

    def test_the_percentage_can_be_changed(self):
        assert check_stability(10, 100, threshold_pct=0.1) is True
        assert check_stability(11, 100, threshold_pct=0.1) is False
        assert check_stability(1, 100, threshold_pct=0.0) is False
        assert check_stability(0, 100, threshold_pct=0.0) is True


class TestSmoothing:
    def test_majority_vote_of_a_window_of_three(self):
        assert smooth_regime(np.array([1, 1, 0, 1, 1])).tolist() == [1, 1, 1, 1, 1]
        assert smooth_regime(np.array([0, 0, 1, 0, 0])).tolist() == [0, 0, 0, 0, 0]

    def test_the_edges_use_a_window_of_two_and_need_both_to_agree(self):
        assert smooth_regime(np.array([1, 0, 0, 0, 1])).tolist() == [0, 0, 0, 0, 0]
        assert smooth_regime(np.array([1, 1, 0, 0, 0])).tolist() == [1, 1, 0, 0, 0]

    def test_a_pair_that_disagrees_becomes_zero(self):
        assert smooth_regime(np.array([0, 1, 0])).tolist() == [0, 0, 0]
        assert smooth_regime(np.array([1, 0, 1])).tolist() == [0, 1, 0]

    def test_a_wider_window(self):
        # window 5: the middle of 1 1 0 1 1 has four ones of five
        assert smooth_regime(np.array([1, 1, 0, 1, 1, 0, 0]), window=5)[2] == 1
        assert smooth_regime(np.array([0, 0, 1, 0, 0, 1, 1]), window=5)[2] == 0

    def test_input_shorter_than_the_window_is_returned_unchanged(self):
        assert smooth_regime(np.array([1, 0])).tolist() == [1, 0]
        assert smooth_regime(np.array([1, 0, 1])).tolist() == [0, 1, 0]  # equal to the window: smoothed

    def test_the_input_is_not_modified(self):
        regime = np.array([0, 1, 0, 1, 0])
        smooth_regime(regime)
        assert regime.tolist() == [0, 1, 0, 1, 0]

    def test_a_constant_regime_is_a_fixed_point(self):
        assert smooth_regime(np.ones(10, dtype=int)).tolist() == [1] * 10
        assert smooth_regime(np.zeros(10, dtype=int)).tolist() == [0] * 10


class TestHooks:
    def test_stop_at_the_iteration_limit(self):
        assert LifecycleHooks.stop_hook(5, 5, 100) is True
        assert LifecycleHooks.stop_hook(6, 5, 100) is True
        assert LifecycleHooks.stop_hook(4, 5, 100) is False

    def test_stop_when_converged(self):
        assert LifecycleHooks.stop_hook(1, 5, 0) is True
        assert LifecycleHooks.stop_hook(1, 5, 1) is False
        assert LifecycleHooks.stop_hook(1, 5, 3, threshold=3) is True
        assert LifecycleHooks.stop_hook(1, 5, 4, threshold=3) is False

    def test_pre_hook_passes_good_prices_and_rejects_bad_ones(self):
        LifecycleHooks.pre_tool_use("f", {}, np.array([1.0, 2.0]))
        with pytest.raises(ValueError, match="PreToolUse Hook Failed for f: Input array must have at least 2") as exc:
            LifecycleHooks.pre_tool_use("f", {}, np.array([1.0]))
        assert isinstance(exc.value.__cause__, ValueError)

    def test_post_hook_passes_good_results_and_rejects_bad_ones(self):
        LifecycleHooks.post_tool_use("f", np.array([0, 1]), 2)
        with pytest.raises(ValueError, match="PostToolUse Hook Failed for f: Output length") as exc:
            LifecycleHooks.post_tool_use("f", np.array([0, 1]), 3)
        assert isinstance(exc.value.__cause__, ValueError)


class TestDataLoader:
    def test_the_series_is_the_one_it_always_was(self):
        prices = load_data("BTC")
        assert len(prices) == 100
        # seed 42, N(0, 0.02) steps from 100: the first step is 0.4967141530112327 * 0.02
        assert prices[0] == pytest.approx(100.99342830602247)
        assert prices[1] == pytest.approx(100.99342830602247 * (1 - 0.1382643011711547 * 0.02))

    def test_it_is_the_same_for_every_symbol_and_timeframe(self):
        assert load_data("A").tolist() == load_data("B", timeframe="1h").tolist()

    def test_limit_sets_the_length_and_a_shorter_series_is_a_prefix(self):
        assert len(load_data("A", limit=7)) == 7
        assert load_data("A", limit=7).tolist() == load_data("A", limit=100)[:7].tolist()

    def test_limit_below_two_is_refused(self):
        with pytest.raises(ValueError, match="at least 2"):
            load_data("A", limit=1)
        assert len(load_data("A", limit=2)) == 2

    def test_it_does_not_touch_numpys_global_generator(self):
        np.random.seed(123)
        expected = np.random.random()
        np.random.seed(123)
        load_data("A")
        assert np.random.random() == expected


class TestMockRouter:
    router = MockSemanticRouter()

    def steps(self, query):
        blueprint = self.router.parse_intent(query)
        return [(s.function_name, s.args) for s in blueprint.steps], blueprint.composition

    def test_trend(self):
        assert self.steps("Show me the trend") == ([("sma_crossover", {"short_window": 20, "long_window": 50})], "AND")

    def test_volatility_and_squeeze(self):
        expected = ([("bollinger_squeeze", {"window": 20, "num_std": 2.0})], "AND")
        assert self.steps("volatility?") == expected
        assert self.steps("any squeeze?") == expected

    def test_momentum_and_rsi(self):
        expected = ([("rsi_overbought", {"threshold": 70}), ("rsi_oversold", {"threshold": 30})], "OR")
        assert self.steps("momentum") == expected
        assert self.steps("what is the RSI") == expected

    def test_combine(self):
        assert self.steps("combine them") == ([("sma_crossover", {}), ("rsi_oversold", {})], "AND")

    def test_anything_else_defaults_to_the_crossover(self):
        assert self.steps("hello") == ([("sma_crossover", {})], "AND")
        assert self.steps("") == ([("sma_crossover", {})], "AND")

    def test_matching_ignores_case(self):
        assert self.steps("TREND")[0][0][0] == "sma_crossover"
        assert self.steps("VoLaTiLiTy")[0][0][0] == "bollinger_squeeze"

    def test_the_first_matching_rule_wins(self):
        assert self.steps("trend and volatility")[0][0][0] == "sma_crossover"
        assert self.steps("volatility and momentum")[0][0][0] == "bollinger_squeeze"
        assert self.steps("momentum, combine")[0][0][0] == "rsi_overbought"

    def test_the_descriptions(self):
        descriptions = {
            "trend": "Trend following strategy using SMA Crossover (20/50)",
            "volatility": "Volatility strategy using Bollinger Band Squeeze",
            "momentum": "Momentum strategy using RSI (Overbought or Oversold)",
            "combine": "Combined strategy: SMA Crossover AND RSI Oversold",
            "anything else": "Default: SMA Crossover",
        }
        for query, text in descriptions.items():
            assert self.router.parse_intent(query).description == text

    def test_every_blueprint_is_for_btc_daily_with_a_description(self):
        for query in ["trend", "volatility", "momentum", "combine", "other"]:
            blueprint = self.router.parse_intent(query)
            assert blueprint.assets == ["BTC"] and blueprint.timeframe == "1d" and blueprint.description

    def test_every_function_it_names_exists_in_the_registry(self):
        from src.orchestrator.engine import Orchestrator

        orchestrator = Orchestrator(self.router)
        for query in ["trend", "volatility", "momentum", "combine", "other"]:
            for step in self.router.parse_intent(query).steps:
                assert step.function_name in orchestrator.registry
