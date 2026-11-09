import numpy as np
import pytest

from src.orchestrator.engine import Orchestrator
from src.router.interface import ExecutionBlueprint, FunctionCall


class StubRouter:
    """A router that returns a fixed blueprint, whatever the query."""

    def __init__(self, blueprint: ExecutionBlueprint):
        self.blueprint = blueprint

    def parse_intent(self, query: str) -> ExecutionBlueprint:
        return self.blueprint


def blueprint(*steps, composition="AND", assets=None) -> ExecutionBlueprint:
    """Build a blueprint from (function_name, args) pairs or function names."""
    calls = [
        FunctionCall(function_name=s) if isinstance(s, str) else FunctionCall(function_name=s[0], args=s[1])
        for s in steps
    ]
    return ExecutionBlueprint(steps=calls, composition=composition, assets=assets or [])


def orchestrator_for(*steps, composition="AND", assets=None, **registry) -> Orchestrator:
    """An orchestrator whose router returns this blueprint; extra keyword arguments are added to the registry."""
    orch = Orchestrator(StubRouter(blueprint(*steps, composition=composition, assets=assets)))
    orch.registry.update(registry)
    return orch


@pytest.fixture
def alternating():
    """A frozen function that returns 0 1 0 1 ..."""
    return lambda prices: np.arange(len(prices)) % 2


@pytest.fixture
def ones():
    return lambda prices: np.ones(len(prices), dtype=int)
