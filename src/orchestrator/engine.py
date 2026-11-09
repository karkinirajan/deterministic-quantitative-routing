import re

import numpy as np

from src.library.momentum import rsi_overbought, rsi_oversold
from src.library.trend import price_above_sma, sma_crossover
from src.library.volatility import atr_expansion, bollinger_squeeze
from src.orchestrator.hooks import LifecycleHooks
from src.orchestrator.stability import calculate_hamming_distance, check_stability
from src.router.interface import SemanticRouter
from src.utils.data_loader import load_data
from src.utils.smoothing import smooth_regime

# Number of data points loaded per asset.
LOOKBACK = 100

# A symbol: letters, digits, dot and underscore. The dash is taken by the spread syntax (A-B).
_SYMBOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._]{0,19}")


class BlueprintError(ValueError):
    """
    The plan the router returned cannot be executed: an unknown function, a rejected argument,
    an unusable asset name, no steps. The caller can fix it (and the message says how), unlike a
    failure inside the platform.
    """


class Orchestrator:
    """
    Kernel-Mode Orchestrator: Coordinates execution of frozen functions.
    """

    def __init__(self, router: SemanticRouter):
        self.router = router
        self.registry = {
            "sma_crossover": sma_crossover,
            "price_above_sma": price_above_sma,
            "bollinger_squeeze": bollinger_squeeze,
            "atr_expansion": atr_expansion,
            "rsi_overbought": rsi_overbought,
            "rsi_oversold": rsi_oversold,
        }

    def _prices(self, asset: str) -> np.ndarray:
        """
        Resolve one asset to a price series: a symbol, or SYMBOL-SYMBOL for a synthetic
        position (the difference of the two series).
        """
        parts = asset.split("-")
        if len(parts) > 2 or not all(_SYMBOL.fullmatch(part) for part in parts):
            raise BlueprintError(
                f"Asset {asset[:40]!r} must be a symbol or SYMBOL-SYMBOL (letters, digits, '.' and '_')"
            )
        if len(parts) == 2:
            return load_data(parts[0], limit=LOOKBACK) - load_data(parts[1], limit=LOOKBACK)
        return load_data(parts[0], limit=LOOKBACK)

    def execute(self, query: str) -> dict:
        """
        Main entry point: Parse intent -> Generate Blueprint -> Execute.
        Support for Multi-Asset Cross-Sectional Execution and Synthetic Positions.
        """
        blueprint = self.router.parse_intent(query)
        if not blueprint.steps:
            raise BlueprintError("The blueprint has no steps to execute")
        assets = blueprint.assets if blueprint.assets else ["BTC"]

        final_results = []

        for asset in assets:
            prices = self._prices(asset)

            asset_results = []
            for step in blueprint.steps:
                func = self.registry.get(step.function_name)
                if not func:
                    raise BlueprintError(f"Function {step.function_name[:60]!r} is not in the registry")

                LifecycleHooks.pre_tool_use(step.function_name, step.args, prices)
                try:
                    res = func(prices, **step.args)
                except (TypeError, ValueError) as e:
                    # A rejected or unknown argument: the router's plan is at fault.
                    raise BlueprintError(f"{step.function_name}: {e}") from e
                LifecycleHooks.post_tool_use(step.function_name, res, len(prices))
                asset_results.append(res)

            # Vertical composition: the steps' results combine into one regime per asset.
            final_results.append(self._compose(asset_results, blueprint.composition))

        # Cross-sectional composition: with several assets the per-asset regimes combine the
        # same way (SUM across assets is a breadth count); one asset is returned as it is.
        final_regime = self._compose(final_results, blueprint.composition)

        return {
            "regime": final_regime.tolist(),
            "blueprint": blueprint.model_dump(),
            "provenance": "Executed via Quant Library Orchestrator v1.1 (Multi-Asset)",
        }

    def _compose(self, results: list[np.ndarray], method: str) -> np.ndarray:
        """
        Logic Gate Implementation (AND, OR, XOR) and the counting and averaging compositions (SUM, AVERAGE).
        """
        if not results:
            return np.array([])

        if len(results) == 1:
            return results[0]

        if method == "AVERAGE":
            # The element-wise mean of all the results, rounded to the nearest integer, which keeps the regime binary (the
            # README's composition rule). A tie (exactly half of the inputs say 1) rounds to 0: a strict majority is needed.
            return np.rint(np.mean(results, axis=0)).astype(int)

        combined = results[0]
        for i in range(1, len(results)):
            next_res = results[i]

            if method == "AND":
                combined = np.logical_and(combined, next_res)
            elif method == "OR":
                combined = np.logical_or(combined, next_res)
            elif method == "XOR":
                combined = np.logical_xor(combined, next_res)
            elif method == "SUM":
                combined = combined + next_res
            else:
                raise BlueprintError(f"Unknown composition method: {method}")

        return combined.astype(int)

    def run_until_stable(self, query: str, max_iterations: int = 10) -> dict:
        """
        Recursive Stability Loop.
        Executing query, then iteratively applying smoothing until stable.

        Stops when the regime is stable (Hamming distance within 1% of its length), when it
        falls into a 2-cycle (the circuit breaker: smoothing would flip between the same two
        states forever), or after `max_iterations`. `stop_reason` says which.
        """
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

        result = self.execute(query)
        initial_regime = np.array(result["regime"])
        if not np.isin(initial_regime, [0, 1]).all():
            raise BlueprintError(
                "Recursive stability needs a binary regime; a SUM composition produces counts"
            )

        history = [initial_regime]
        stop_reason = "max_iterations"

        iteration = 0
        while True:
            iteration += 1
            prev_regime = history[-1]
            next_regime = smooth_regime(prev_regime)

            # Check stability
            d_h = calculate_hamming_distance(prev_regime, next_regime)
            is_stable = check_stability(d_h, len(prev_regime))

            history.append(next_regime)

            if is_stable:
                stop_reason = "stable"
                break

            # Circuit breaker: the new state equals the one two steps back.
            if len(history) >= 3 and np.array_equal(next_regime, history[-3]):
                stop_reason = "oscillation"
                break

            # Stop Hook: the limit (it always ends the loop: `iteration` counts up to `max_iterations`)
            if LifecycleHooks.stop_hook(iteration, max_iterations, d_h):
                break

        return {
            "regime": history[-1].tolist(),
            "iterations": len(history) - 1,
            "initial_regime": initial_regime.tolist(),
            "blueprint": result["blueprint"],
            "provenance": f"Recursive execution ended ({stop_reason}) after {len(history) - 1} iterations",
            "stop_reason": stop_reason,
        }
