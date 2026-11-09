# 01. Architecture

A prototype of the routing layer of a "thin agent, fat platform" design: a language model (here, a keyword stub) decides *which* frozen
functions to run, and the platform runs them. The model never does arithmetic.

```text
POST /query ──► SemanticRouter ──► ExecutionBlueprint ──► Orchestrator ──► regime (0/1 list) + blueprint + why it stopped
 (FastAPI)      (mock: keywords)    steps, composition,     │  per asset: load data, run each step through the hooks
                                    assets                  │  compose the steps, then the assets
                                                            └► optional: smooth until stable (circuit breaker)
```

## Modules

| Path | Does |
|---|---|
| `src/api/main.py`, `models.py` | `GET /health`, `POST /query`; request limits; error mapping |
| `src/router/interface.py` | `FunctionCall`, `ExecutionBlueprint` (at most 20 steps and 50 assets), the `SemanticRouter` protocol |
| `src/router/mock_router.py` | The keyword router used for tests and the API |
| `src/orchestrator/engine.py` | `Orchestrator.execute`, `_compose`, `run_until_stable`; `BlueprintError` |
| `src/orchestrator/hooks.py` | `pre_tool_use`, `post_tool_use` (validate input and output of every call), `stop_hook` |
| `src/orchestrator/stability.py` | Hamming distance and the 1% stability rule |
| `src/library/` | The frozen functions and the validators (`core.py`) |
| `src/utils/` | `smooth_regime` (majority vote), `load_data` (mock random walk) |

The code is imported as `src.*` from the repository root; it is an application, not an installable package (`[tool.uv] package = false`).

## A request, step by step

1. The router turns the text into a blueprint. A language-model router would be the only part that interprets text.
2. Each asset (`BTC`, or `A-B` for the difference of two series) is loaded, then every step is run through `pre_tool_use` (the data is valid),
   the function (its arguments are validated by the function itself) and `post_tool_use` (the result is binary and the right length).
3. Steps compose into one regime per asset, assets compose into one regime: `AND`, `OR`, `XOR`, `SUM` (a count), or `AVERAGE` (the mean,
   rounded; a tie rounds to 0).
4. With `recursive_stability`, the regime is smoothed (majority of three) until it settles: at most 1% of positions change (`stable`), or the
   state repeats from two steps back (`oscillation`: the circuit breaker), or `max_iterations` is reached. The response says which; an
   unstable result is never returned silently.

## Errors

`BlueprintError` means the *plan* cannot run (unknown function, a rejected argument, a bad asset name, no steps, a count regime sent
to the stability loop); the API answers **422** with the message. Anything else is the platform's fault: **500** with `Internal error`, and the
detail goes to the log.

## What the design describes and the code does not do

See the status table in the README: no language-model router, no ordinal-pattern functions, no Redis state, no provenance receipts, no
multi-timeframe broadcasting. `FunctionCall.weight` and `ExecutionBlueprint.timeframe` are accepted from a router and ignored.
