from pydantic import BaseModel, ConfigDict, Field

MAX_QUERY_LENGTH = 2000
MAX_ITERATIONS = 100


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    recursive_stability: bool = False
    max_iterations: int = Field(default=10, ge=1, le=MAX_ITERATIONS)


class RegimeResponse(BaseModel):
    # Binary (0/1) for AND/OR/XOR/AVERAGE, counts for SUM.
    regime: list[int]
    blueprint: dict
    provenance: str
    iterations: int | None = None
    initial_regime: list[int] | None = None
    # Why the recursive loop stopped: "stable", "oscillation" or "max_iterations".
    stop_reason: str | None = None
