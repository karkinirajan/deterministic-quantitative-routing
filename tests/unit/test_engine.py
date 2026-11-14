import numpy as np
import pytest

from src.orchestrator import engine as engine_module
from src.orchestrator.engine import LOOKBACK, BlueprintError, Orchestrator
from src.router.interface import MAX_ASSETS, MAX_STEPS, ExecutionBlueprint, FunctionCall
from tests.conftest import StubRouter, blueprint, orchestrator_for

A = np.array([0, 0, 1, 1])
B = np.array([0, 1, 0, 1])


def compose(method, *arrays):
    return Orchestrator(StubRouter(blueprint("sma_crossover")))._compose(list(arrays), method)


class TestCompose:
    def test_and(self):
        assert compose("AND", A, B).tolist() == [0, 0, 0, 1]

    def test_or(self):
        assert compose("OR", A, B).tolist() == [0, 1, 1, 1]

    def test_xor(self):
        assert compose("XOR", A, B).tolist() == [0, 1, 1, 0]

    def test_sum(self):
        assert compose("SUM", A, B).tolist() == [0, 1, 1, 2]

    def test_average_is_the_mean_rounded_and_a_tie_rounds_to_zero(self):
        # means 0, .5, .5, 1: the two ties (one input says 1, one says 0) round to 0
        assert compose("AVERAGE", A, B).tolist() == [0, 0, 0, 1]

    def test_average_of_three_is_a_strict_majority(self):
        c = np.array([1, 1, 1, 0])
        # means 1/3, 2/3, 2/3, 2/3
        assert compose("AVERAGE", A, B, c).tolist() == [0, 1, 1, 1]

    def test_average_is_the_mean_of_all_inputs_not_a_running_pair(self):
        # a running pairwise average would weigh the last input by 1/2: ((1 + 1)/2 + 0)/2 = .5 -> 0 here, but the mean is 2/3 -> 1
        ones = np.array([1, 1])
        assert compose("AVERAGE", ones, ones, np.array([0, 0])).tolist() == [1, 1]
        assert compose("AVERAGE", np.array([0, 0]), ones, ones).tolist() == [1, 1]
        assert compose("AVERAGE", ones, np.array([0, 0]), np.array([0, 0])).tolist() == [0, 0]

    def test_average_of_four_with_two_ones_is_a_tie(self):
        a, b, c, d = np.array([1]), np.array([1]), np.array([0]), np.array([0])
        assert compose("AVERAGE", a, b, c, d).tolist() == [0]
        assert compose("AVERAGE", a, b, np.array([1]), d).tolist() == [1]

    def test_logic_gates_and_average_return_ints(self):
        for method in ("AND", "OR", "XOR", "SUM", "AVERAGE"):
            assert compose(method, A, B).dtype.kind == "i", method

    def test_three_inputs_fold_left_to_right(self):
        c = np.array([1, 1, 1, 0])
        assert compose("AND", A, B, c).tolist() == [0, 0, 0, 0]
        assert compose("OR", A, B, c).tolist() == [1, 1, 1, 1]
        assert compose("SUM", A, B, c).tolist() == [1, 2, 2, 2]
        assert compose("XOR", A, B, c).tolist() == [1, 0, 0, 0]
        assert compose("AVERAGE", A, B, c).tolist() == [0, 1, 1, 1]

    def test_a_single_result_is_returned_as_is(self):
        assert compose("AND", A) is A
        assert compose("NO-SUCH-METHOD", A) is A

    def test_nothing_composes_to_an_empty_array(self):
        assert compose("AND").tolist() == []

    def test_an_unknown_method_is_a_blueprint_error(self):
        with pytest.raises(BlueprintError, match="Unknown composition method: MEDIAN"):
            compose("MEDIAN", A, B)


class TestExecuteErrors:
    def test_an_unknown_function(self):
        with pytest.raises(BlueprintError, match="'no_such_function' is not in the registry"):
            orchestrator_for("no_such_function").execute("q")

    def test_a_long_function_name_is_cut_in_the_message(self):
        with pytest.raises(BlueprintError) as exc:
            orchestrator_for("x" * 500).execute("q")
        assert len(str(exc.value)) < 100

    def test_no_steps(self):
        with pytest.raises(BlueprintError, match="no steps"):
            orchestrator_for().execute("q")

    def test_an_unknown_argument(self):
        with pytest.raises(BlueprintError, match="sma_crossover:.*unexpected keyword"):
            orchestrator_for(("sma_crossover", {"bogus": 1})).execute("q")

    def test_a_rejected_value(self):
        with pytest.raises(BlueprintError, match="sma_crossover: short_window must be at least 1"):
            orchestrator_for(("sma_crossover", {"short_window": 0})).execute("q")

    def test_a_rejected_type(self):
        with pytest.raises(BlueprintError, match="sma_crossover: long_window must be an integer"):
            orchestrator_for(("sma_crossover", {"long_window": "50"})).execute("q")

    def test_the_cause_is_chained(self):
        with pytest.raises(BlueprintError) as exc:
            orchestrator_for(("sma_crossover", {"short_window": 0})).execute("q")
        assert isinstance(exc.value.__cause__, ValueError)

    def test_a_blueprint_error_is_a_value_error(self):
        assert issubclass(BlueprintError, ValueError)

    def test_a_failure_inside_a_function_that_is_not_a_value_or_type_error_is_not_a_blueprint_error(self):
        def boom(prices):
            raise ZeroDivisionError("internal")

        with pytest.raises(ZeroDivisionError):
            orchestrator_for("boom", boom=boom).execute("q")


class TestAssets:
    @pytest.mark.parametrize(
        "asset",
        ["A-B-C", "-A", "A-", "-", "A--B", "BTC USD", "A B-C", "../etc", "A/B", "A;B", "", "x" * 21, "-".join(["A", ""])],
    )
    def test_bad_asset_names_are_refused(self, asset):
        with pytest.raises(BlueprintError, match="must be a symbol or SYMBOL-SYMBOL"):
            orchestrator_for("sma_crossover", assets=[asset]).execute("q")

    @pytest.mark.parametrize("asset", [".A", "_A", "A-.B", "A-_B", ".."])
    def test_a_symbol_starts_with_a_letter_or_digit(self, asset):
        with pytest.raises(BlueprintError, match="must be a symbol"):
            orchestrator_for("sma_crossover", assets=[asset]).execute("q")

    @pytest.mark.parametrize("asset", ["BTC", "A", "btc.usd", "ES_F", "9", "x" * 20, "BTC-ETH", "A.B-C_D"])
    def test_good_asset_names_are_accepted(self, asset):
        assert len(orchestrator_for("sma_crossover", assets=[asset]).execute("q")["regime"]) == LOOKBACK

    def test_the_message_cuts_a_long_name(self):
        with pytest.raises(BlueprintError) as exc:
            orchestrator_for("sma_crossover", assets=["!" * 500]).execute("q")
        assert len(str(exc.value)) < 150

    def test_no_assets_means_btc(self, monkeypatch):
        seen = []
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: seen.append(symbol) or np.arange(limit, dtype=float))
        orchestrator_for("sma_crossover").execute("q")
        assert seen == ["BTC"]

    def test_a_plain_symbol_loads_that_symbol_with_the_lookback(self, monkeypatch):
        calls = []
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: calls.append((symbol, limit)) or np.arange(limit, dtype=float))
        orchestrator_for("sma_crossover", assets=["ETH"]).execute("q")
        assert calls == [("ETH", LOOKBACK)]

    def test_a_spread_is_the_difference_of_the_two_series(self, monkeypatch):
        series = {"A": np.arange(LOOKBACK, dtype=float) + 10.0, "B": np.arange(LOOKBACK, dtype=float)}
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: series[symbol])
        captured = []

        def spy(prices):
            captured.append(prices.copy())
            return np.zeros(len(prices), dtype=int)

        orchestrator_for("spy", assets=["A-B"], spy=spy).execute("q")
        assert len(captured) == 1
        assert np.all(captured[0] == 10.0)

    def test_the_order_of_a_spread_matters(self, monkeypatch):
        series = {"A": np.full(LOOKBACK, 5.0), "B": np.full(LOOKBACK, 2.0)}
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: series[symbol])
        captured = []
        orchestrator_for("spy", assets=["B-A"], spy=lambda p: captured.append(p.copy()) or np.zeros(len(p), dtype=int)).execute("q")
        assert np.all(captured[0] == -3.0)

    def test_every_asset_is_executed(self, monkeypatch):
        loaded = []
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: loaded.append(symbol) or np.arange(limit, dtype=float))
        orchestrator_for("sma_crossover", assets=["A", "B", "C"]).execute("q")
        assert loaded == ["A", "B", "C"]


class TestExecuteComposition:
    def test_steps_compose_within_an_asset(self):
        orch = orchestrator_for("a", "b", composition="XOR", a=lambda p: A.repeat(25), b=lambda p: B.repeat(25))
        result = orch.execute("q")["regime"]
        assert result == [0] * 25 + [1] * 25 + [1] * 25 + [0] * 25

    def test_assets_compose_across_assets_with_the_same_method(self):
        outputs = iter([np.repeat([1, 1, 0, 0], 25), np.repeat([1, 0, 1, 0], 25), np.repeat([1, 1, 1, 1], 25)])
        orch = orchestrator_for("f", assets=["A", "B", "C"], composition="SUM", f=lambda p: next(outputs))
        regime = orch.execute("q")["regime"]
        assert regime[0] == 3 and regime[25] == 2 and regime[50] == 2 and regime[75] == 1

    def test_one_asset_with_one_step_is_returned_directly(self):
        regime = orchestrator_for("a", a=lambda p: np.repeat([0, 1], 50)).execute("q")["regime"]
        assert regime == [0] * 50 + [1] * 50

    def test_the_result_carries_the_blueprint_and_provenance(self):
        result = orchestrator_for("sma_crossover", assets=["A"]).execute("q")
        assert result["blueprint"]["steps"][0]["function_name"] == "sma_crossover"
        assert result["blueprint"]["assets"] == ["A"]
        assert result["provenance"] == "Executed via Quant Library Orchestrator v1.1 (Multi-Asset)"
        assert set(result) == {"regime", "blueprint", "provenance"}

    def test_a_list_of_plain_ints(self):
        regime = orchestrator_for("sma_crossover").execute("q")["regime"]
        assert all(type(v) is int for v in regime)

    def test_the_router_receives_the_query(self):
        class Spy:
            def parse_intent(self, query):
                self.query = query
                return blueprint("sma_crossover")

        spy = Spy()
        Orchestrator(spy).execute("show me the trend")
        assert spy.query == "show me the trend"


class TestHooksInExecution:
    def test_invalid_input_data_fails_the_pre_hook(self, monkeypatch):
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: np.full(limit, np.nan))
        with pytest.raises(ValueError, match="PreToolUse Hook Failed for sma_crossover"):
            orchestrator_for("sma_crossover").execute("q")

    def test_the_pre_hook_failure_is_not_a_blueprint_error(self, monkeypatch):
        monkeypatch.setattr(engine_module, "load_data", lambda symbol, limit: np.full(limit, np.nan))
        with pytest.raises(ValueError) as exc:
            orchestrator_for("sma_crossover").execute("q")
        assert not isinstance(exc.value, BlueprintError)

    def test_a_non_binary_result_fails_the_post_hook(self):
        with pytest.raises(ValueError, match="PostToolUse Hook Failed for bad"):
            orchestrator_for("bad", bad=lambda p: np.full(len(p), 2)).execute("q")

    def test_a_result_of_the_wrong_length_fails_the_post_hook(self):
        with pytest.raises(ValueError, match="PostToolUse Hook Failed for short"):
            orchestrator_for("short", short=lambda p: np.zeros(3, dtype=int)).execute("q")


class TestBlueprintBounds:
    def test_at_most_20_steps_and_50_assets(self):
        assert (MAX_STEPS, MAX_ASSETS) == (20, 50)
        calls = [FunctionCall(function_name="sma_crossover")] * MAX_STEPS
        ExecutionBlueprint(steps=calls, assets=["A"] * MAX_ASSETS)
        with pytest.raises(ValueError):
            ExecutionBlueprint(steps=[*calls, FunctionCall(function_name="x")])
        with pytest.raises(ValueError):
            ExecutionBlueprint(steps=calls, assets=["A"] * (MAX_ASSETS + 1))

    def test_defaults(self):
        bp = ExecutionBlueprint(steps=[])
        assert (bp.composition, bp.timeframe, bp.assets, bp.description) == ("AND", "1d", [], "")
        assert FunctionCall(function_name="f").args == {} and FunctionCall(function_name="f").weight == 1.0

    def test_an_unknown_composition_is_refused_by_the_model(self):
        with pytest.raises(ValueError):
            ExecutionBlueprint(steps=[], composition="MEDIAN")


class TestRunUntilStable:
    def test_a_constant_regime_is_stable_after_one_step(self, ones):
        result = orchestrator_for("ones", ones=ones).run_until_stable("q", max_iterations=5)
        assert result["stop_reason"] == "stable"
        assert result["iterations"] == 1
        assert result["regime"] == [1] * LOOKBACK
        assert result["initial_regime"] == [1] * LOOKBACK

    def test_a_two_cycle_trips_the_circuit_breaker(self, monkeypatch, alternating):
        monkeypatch.setattr(engine_module, "smooth_regime", lambda r: 1 - r)
        result = orchestrator_for("alt", alt=alternating).run_until_stable("q", max_iterations=50)
        assert result["stop_reason"] == "oscillation"
        assert result["iterations"] == 2  # init -> flipped -> back to init
        assert result["regime"] == result["initial_regime"]

    def test_running_out_of_iterations(self, monkeypatch, alternating):
        flipped = iter(range(0, 1000, 5))

        def churn(regime):  # five new positions flip on every call: never stable, never a 2-cycle
            out = regime.copy()
            start = next(flipped)
            out[start % 100 : start % 100 + 5] ^= 1
            return out

        monkeypatch.setattr(engine_module, "smooth_regime", churn)
        result = orchestrator_for("alt", alt=alternating).run_until_stable("q", max_iterations=4)
        assert result["stop_reason"] == "max_iterations"
        assert result["iterations"] == 4
        assert sum(a != b for a, b in zip(result["regime"], result["initial_regime"], strict=True)) == 20  # 4 x 5 flipped positions

    def test_one_iteration_is_allowed(self, monkeypatch, alternating):
        flipped = iter(range(0, 1000, 5))

        def churn(regime):
            out = regime.copy()
            start = next(flipped)
            out[start % 100 : start % 100 + 5] ^= 1
            return out

        monkeypatch.setattr(engine_module, "smooth_regime", churn)
        result = orchestrator_for("alt", alt=alternating).run_until_stable("q", max_iterations=1)
        assert (result["iterations"], result["stop_reason"]) == (1, "max_iterations")

    def test_zero_iterations_is_refused(self, ones):
        with pytest.raises(ValueError, match="at least 1"):
            orchestrator_for("ones", ones=ones).run_until_stable("q", max_iterations=0)

    def test_stable_wins_over_the_iteration_limit(self, ones):
        assert orchestrator_for("ones", ones=ones).run_until_stable("q", max_iterations=1)["stop_reason"] == "stable"

    def test_a_small_change_within_one_percent_counts_as_stable(self, monkeypatch, alternating):
        def nudge(regime):  # exactly one position differs: 1 <= 1% of 100
            out = regime.copy()
            out[0] ^= 1
            return out

        monkeypatch.setattr(engine_module, "smooth_regime", nudge)
        result = orchestrator_for("alt", alt=alternating).run_until_stable("q", max_iterations=9)
        assert (result["iterations"], result["stop_reason"]) == (1, "stable")
        # the regime returned is the smoothed one, not the starting one
        assert result["regime"][0] != result["initial_regime"][0]
        assert result["regime"][1:] == result["initial_regime"][1:]

    def test_two_changes_are_not_stable(self, monkeypatch, alternating):
        counter = iter(range(0, 1000, 2))

        def nudge(regime):
            out = regime.copy()
            i = next(counter) % 98
            out[i] ^= 1
            out[i + 1] ^= 1
            return out

        monkeypatch.setattr(engine_module, "smooth_regime", nudge)
        result = orchestrator_for("alt", alt=alternating).run_until_stable("q", max_iterations=3)
        assert result["stop_reason"] == "max_iterations"

    def test_the_real_smoothing_converges_on_a_trend(self):
        from src.router.mock_router import MockSemanticRouter

        result = Orchestrator(MockSemanticRouter()).run_until_stable("trend", max_iterations=50)
        assert result["stop_reason"] in {"stable", "oscillation"}
        assert 1 <= result["iterations"] <= 50
        assert len(result["regime"]) == LOOKBACK

    def test_the_provenance_says_how_it_ended(self, ones):
        result = orchestrator_for("ones", ones=ones).run_until_stable("q")
        assert result["provenance"] == "Recursive execution ended (stable) after 1 iterations"

    def test_the_blueprint_is_carried_over(self, ones):
        result = orchestrator_for("ones", ones=ones).run_until_stable("q")
        assert result["blueprint"]["steps"][0]["function_name"] == "ones"

    def test_a_sum_of_two_ones_is_not_binary_and_is_refused(self, ones):
        orch = orchestrator_for("a", "b", composition="SUM", a=ones, b=ones)
        with pytest.raises(BlueprintError, match="binary regime"):
            orch.run_until_stable("q")

    def test_a_sum_that_happens_to_be_binary_is_accepted(self, ones):
        zeros = lambda p: np.zeros(len(p), dtype=int)  # noqa: E731
        assert orchestrator_for("a", "b", composition="SUM", a=ones, b=zeros).run_until_stable("q")["stop_reason"] == "stable"

    def test_an_average_is_binary_so_it_can_be_stabilised(self, alternating, ones):
        result = orchestrator_for("a", "b", "c", composition="AVERAGE", a=ones, b=ones, c=alternating).run_until_stable("q")
        assert set(result["initial_regime"]) <= {0, 1}
        assert result["stop_reason"] in {"stable", "oscillation", "max_iterations"}

    def test_a_regime_that_mixes_binary_and_other_values_is_refused(self, alternating, ones):
        # alternating (0 1 0 1 ...) + ones = 1 2 1 2 ...: some values are in {0, 1}, the 2s are not
        orch = orchestrator_for("a", "b", composition="SUM", a=alternating, b=ones)
        with pytest.raises(BlueprintError, match="binary regime"):
            orch.run_until_stable("q")

    def test_a_binary_sum_is_accepted(self, ones):
        # one step, so SUM never adds anything: the regime stays 0/1
        assert orchestrator_for("a", composition="SUM", a=ones).run_until_stable("q")["stop_reason"] == "stable"

    def test_the_default_limit_is_ten_iterations(self, monkeypatch, alternating):
        calls = []

        def churn(regime):
            calls.append(1)
            out = regime.copy()
            k = len(calls) * 5 % 100
            out[k : k + 5] ^= 1
            return out

        monkeypatch.setattr(engine_module, "smooth_regime", churn)
        result = orchestrator_for("alt", alt=alternating).run_until_stable("q")
        assert result["iterations"] == 10 and len(calls) == 10
