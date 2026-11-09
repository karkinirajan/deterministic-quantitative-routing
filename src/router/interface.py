from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

# What a router may ask for in one plan: the router will be a language model, so its output is bounded.
MAX_STEPS = 20
MAX_ASSETS = 50


class FunctionCall(BaseModel):
    """
    Represents a single function call in the execution blueprint.
    """

    function_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0  # For weighted combinations


class ExecutionBlueprint(BaseModel):
    """
    Structured plan for executing the user's intent.
    """

    steps: list[FunctionCall] = Field(max_length=MAX_STEPS)
    composition: Literal["AND", "OR", "XOR", "AVERAGE", "SUM"] = "AND"
    timeframe: str = "1d"  # Default to daily
    assets: list[str] = Field(default_factory=list, max_length=MAX_ASSETS)
    description: str = ""  # Explanation of the plan


class SemanticRouter(Protocol):
    """
    Protocol for the Semantic Routing Layer.
    """

    def parse_intent(self, query: str) -> ExecutionBlueprint:
        """
        Parses a natural language query into an Execution Blueprint.
        """
        ...
