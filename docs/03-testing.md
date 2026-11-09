# 03. Testing

```bash
uv run pytest -q          # 254 tests, well under a second
uv run ruff check .       # lint (the rule set is in pyproject.toml)
```

## Layout

```text
tests/
  conftest.py                  a stub router and helpers to build a blueprint and an orchestrator with extra functions
  unit/
    test_core.py               the validators: every accepted and refused input, boundaries, types, bool
    test_library.py            each function on small series with hand-computed answers (windows, thresholds, edges)
    test_library_golden.py     the exact regimes on the mock series (characterization of the arithmetic)
    test_engine.py             composition truth tables, error paths, assets and spreads, hooks, the stability loop
    test_support.py            Hamming distance, smoothing, hooks, the data loader, the mock router
    test_multi_asset.py        (original) synthetic positions and breadth
  integration/
    test_pipeline.py           (original) router + orchestrator
    test_api.py                the HTTP API through FastAPI's test client, and the module's entry point
  mutation/                    the mutation driver and its list
```

Nothing needs the network, a model or a market feed: data is the mock loader.

## Golden values

`test_library_golden.py` records the exact output of each function on the mock series (run-length encoded). Small hand-computed series check
the *logic*; the golden values check what they cannot: default windows and thresholds, the unit of the volatility proxy, the length of the warm-up.
They are characterization tests: a deliberate change to a function changes them, and the same commit should update them and say why.

## Mutation checks

`tests/mutation/mutants.py` holds 242 deliberate bugs, each `(name, file, old text, new text)`: a comparison flipped, a window off by one,
a threshold shifted, a guard dropped, a status code changed, a default altered. The driver applies one at a time and counts it **killed** if
the tests then fail. All are killed. (The first run left 6 not killed: 3 missing assertions (a threshold equal to the bandwidth, the regime a loop returns, the router's
descriptions), 1 missing OpenAPI check, 1 redundant `fillna` that was simplified away, and 1 pattern that did not match and was
corrected. Before that run, review had already removed two other redundancies: `fillna` calls the NaN comparison made unnecessary,
and a loop bound that made the stop hook decorative.)

```bash
python3 tests/mutation/mutate.py tests/mutation/mutants.py -- uv run pytest -x -q
```

Rules: the suite must be green first (the driver checks); do not edit the tree while it runs; each pattern must occur exactly once.

## Checked outside pytest

The Docker image was built and run: `/health`, plain and recursive `/query`, a `max_iterations` of 10^9 (422), an empty query (422), an unknown field (422),
the process user (10001) and the container's health status (`healthy`).

## Not tested

A language-model router (none exists); real market data (none is loaded); load or concurrency.
