# 04. Operations

## Running

| Command | Does |
|---|---|
| `uv sync` | Install the locked dependencies |
| `uv run python -m src.api.main` | The API on `127.0.0.1:8000` (`HOST`, `PORT` override) |
| `uv run uvicorn src.api.main:app --reload` | The API with reload, for development |
| `uv run pytest -q` / `uv run ruff check .` | Tests / lint |
| `docker build -t dqr .` then `docker run -p 8000:8000 dqr` | The container (non-root, health check) |

## Settings

| Variable | Default | |
|---|---|---|
| `HOST` | `127.0.0.1` (the image sets `0.0.0.0`) | Bind address. There is no authentication: keep it on loopback or behind a gateway |
| `PORT` | `8000` | |

## The API

`POST /query` takes `{"query": "...", "recursive_stability": false, "max_iterations": 10}` (query 1 to 2000 characters, iterations 1 to 100, no other fields).

| Status | Meaning |
|---|---|
| 200 | `regime` (a list of 0/1; counts for a `SUM` plan), `blueprint`, `provenance`; with `recursive_stability`: `iterations`, `initial_regime`, `stop_reason` |
| 422 | The request is invalid, or the plan cannot run (the message says which function or argument) |
| 500 | `Internal error`; the details are in the log (`uvicorn.error`, "query failed") |

`stop_reason` is `stable`, `oscillation` or `max_iterations`: the last two mean the regime did **not** settle.

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`: lint, tests and (once, on 3.14) `uv audit` on Python 3.12 and 3.14,
and a `docker build`.

## Before using this for anything real

The router is a keyword stub and the data is a mock random walk: the regimes mean nothing about any market. A real router and a real data
loader have to be written; see the status table in the README for what is missing.
