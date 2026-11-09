# Work done

What this repository was, what was changed, and what still needs a person. Branch: `chore/modernize` (local, nothing pushed).
Start point: `c107536`.

## At a glance

- **Was:** a small FastAPI prototype (about 700 lines) of the routing layer of a "thin agent, fat platform" design: a keyword router turns a
  query into a plan, an orchestrator runs six technical-indicator functions on mock data and composes the results, and an optional loop
  smooths the regime until it settles. 8 tests, no lockfile or version pins (`requirements.txt` listed seven bare names), no CI, a
  `python:3.11` Docker image that ran as root, and a README that described a much larger system (Redis, provenance receipts, ordinal-pattern
  maths, shell hooks) that is not in the code. Reviewing the code found: **every error became a 500 carrying the exception text; the request's
  `max_iterations` was unbounded (a caller could keep a worker looping for as long as it liked); the plan could ask for any assets, any
  number of steps and any function arguments; the server listened on `0.0.0.0` with no authentication**; and several results that
  would mislead a user (a Bollinger squeeze signalled for any spread whose average is negative, "price above average" true everywhere when the
  window was longer than the data, `AVERAGE` returning fractions that then crashed the response model and was not a true mean for three or
  more inputs, and the README's promised oscillation circuit breaker missing).
- **Now:** all fixed and tested: 254 tests, 242 deliberate bugs that the suite fails for, a ruff lint gate, locked dependencies (`uv.lock`) on
  the latest releases with `uv audit` clean, a two-stage non-root Docker image **built and run here**, CI on Python 3.12 and 3.14, and the
  README now opens with a table of what the code implements against what the design describes; `VERSIONS.md`, four docs chapters.
- **Needs a person:** decide which README is the specification (it holds the design, a pasted client brief and a second README draft, and they
  disagree); confirm the `AVERAGE` tie rule; push. See [What a person might want to do](#what-a-person-might-want-to-do).

## Verified

Run on the final tree, 2026-11-10:

| Gate | Command | Result |
|---|---|---|
| Lint | `uv run ruff check .` | pass (new gate; 28 findings at the start: unused imports, deprecated typing, unchained `raise`; none suppressed) |
| Tests | `uv run pytest -q` | 254 passed (8 at the start). One warning stays: Starlette's test client asks for `httpx2` instead of `httpx`; not added (could not be vetted here) and not filtered out |
| Mutation | `tests/mutation/mutate.py` | 242 of 242 killed, on a green baseline (a first run left 6 not killed: 3 missing assertions, 1 missing OpenAPI check, 1 redundant `fillna` simplified, 1 pattern typo) |
| Audit | `uv audit` | no known vulnerabilities in 28 packages |
| Docker | `docker build`, then run | image builds; container answers `/health`, plain and recursive `/query`; `max_iterations` 10^9, an empty query and an unknown field each return 422; runs as uid 10001; health status `healthy`; 408 MB |
| Secrets | pattern scan of the tree and all 12 commits | none found (a pattern scan, counts only; `.env*` files were not read, and none was ever tracked; not a guarantee) |
| Formatting | | not changed: no formatter is configured |

**Not verified:** anything against a real market (the loader is a mock random walk, the same series for every symbol); a language-model router
(none exists); behaviour under load; Python 3.15 (available, not adopted); the GitHub Actions workflow itself (it was not run).

## Findings and fixes

| Finding | Fix |
|---|---|
| **Any exception became `500` with `str(e)`** | `BlueprintError` is a 422 with our own message; anything else is a generic 500, logged |
| **`max_iterations` unbounded** in the request (and an alternating regime never settles) | 1 to 100 at the API; circuit breaker for 2-cycles; the result carries `stop_reason` |
| Query unbounded; unknown JSON fields accepted | 1 to 2000 characters; `extra="forbid"` |
| A plan could name any asset text, any number of steps and assets, any arguments | At most 20 steps and 50 assets; asset names validated (`SYMBOL` or `SYMBOL-SYMBOL`); every function validates its own arguments |
| `python -m src.api.main` bound `0.0.0.0`, no authentication | Loopback by default; `HOST` and `PORT` |
| Docker image: root, `python:3.11`, unpinned `pip install`, no health check | Two-stage, locked, `python:3.14-slim`, uid 10001, `HEALTHCHECK` |
| `np.random.seed(42)` reset numpy's global generator on every data load | A local generator, same seed and same numbers |
| `bollinger_squeeze`: signed average in the denominator (a negative spread read as a squeeze); warm-up filled with 1.0 | `|SMA|`; warm-up left undefined |
| `price_above_sma`, `sma_crossover`: an undefined average filled with 0 | No signal |
| `AVERAGE`: fractions, a running pairwise "average", a 500 from the response model | The mean of all inputs, rounded to the nearest integer, a tie rounding to 0 (the README's composition rule); a binary result, so it can be stabilised |
| README promised an oscillation circuit breaker; none existed | Implemented |
| No steps in a plan returned an empty regime | 422 |
| Blocking CPU work in `async def` handlers | Plain `def` (thread pool) |
| No lockfile, no pins, `pytest` in the runtime requirements, `requirements.txt` | `pyproject.toml` + `uv.lock`; dev group; `requirements.txt` removed |
| README: Python 3.11, Redis, `pip install -r requirements.txt`, `scripts/verify_integrity.py`, `lib/quant` and more that do not exist | A status table at the top, real install steps, "Adding a function", the original design text kept and labelled, the pasted material marked as an appendix |

Details: [docs/02-security.md](docs/02-security.md).

## Changes, file by file

### Source

| File | Was | Now |
|---|---|---|
| `src/library/core.py` | `validate_input`, `validate_output` | plus `check_window`, `check_number` (argument validation) |
| `src/library/trend.py`, `momentum.py`, `volatility.py` | arguments unchecked; NaN fills; signed denominator | arguments validated; no NaN fills; `|SMA|` |
| `src/orchestrator/engine.py` | `RuntimeError` for argument failures, errors with text, a 100-point loop with a decorative stop hook, float `AVERAGE`, free-form assets | `BlueprintError`, validated assets, no-steps check, `AVERAGE` as specified, the circuit breaker and `stop_reason`, the stop hook as the loop's limit |
| `src/orchestrator/hooks.py`, `stability.py` | unchained `raise`; numpy int | `raise ... from`; plain int |
| `src/router/interface.py` | unbounded plans | at most 20 steps and 50 assets |
| `src/router/mock_router.py` | unused import | cleaned |
| `src/api/main.py`, `models.py` | `async def`, `str(e)` in the 500, `0.0.0.0`, unbounded request | `def`, 422/500 mapping, loopback, limits, `stop_reason` |
| `src/utils/data_loader.py` | global reseed | local generator; `limit >= 2` |

### Configuration and tooling

| File | Was | Now |
|---|---|---|
| `pyproject.toml` | pytest settings only | project metadata, dependencies, dev group, ruff configuration |
| `uv.lock`, `.python-version` (new) | none | locked set; Python 3.14 |
| `requirements.txt` | seven unpinned names | removed (superseded; the Dockerfile and README no longer use it) |
| `Dockerfile`, `.dockerignore` (new) | single stage, root | see above |
| `.github/workflows/ci.yml` (new) | none | lint, tests, audit on Python 3.12 and 3.14; docker build |
| `tests/` | 3 files, 8 tests | 8 files, 254 tests, `tests/mutation/` (driver, 242 mutants) |

### Docs

`README.md` extended (status table, install steps, adding a function, labelled design sections, appendix note; the owner's text is
otherwise unchanged). `VERSIONS.md`, `docs/01` to `04` and this file are new.

## What a person might want to do

1. **Decide the specification.** The README holds three things: the design, a pasted critique of an earlier version ("Why the Current Project is
   Not Right": delete the indicator maths, parameterless "frozen" functions, multi-timeframe broadcasting) and a second README draft. They
   disagree. This pass followed the code and the design text, implemented the two requirements the others agree on (the `AVERAGE` rule, the
   stability stop with a flagged circuit breaker) and did **not** delete the indicators or add broadcasting.
2. **Confirm the `AVERAGE` tie rule.** The README's worked example lost its numbers (the arrays were swallowed by Markdown formatting). A tie,
   exactly half of the inputs saying 1, rounds to **0** here (a strict majority is required); if it should round to 1, it is one line in
   `Orchestrator._compose`, and a mutant and a test pin the current choice.
3. **Stability threshold:** the code treats "at most 1% of positions changed" as stable (inclusive); the brief says "< 1%". For 100 points that is
   one flip. Say which you mean.
4. **Push** when satisfied: `git push -u origin chore/modernize` (not done here).
5. Put authentication in front of the API before exposing it, and write a real router and data loader before reading anything into a regime.

## Known and left alone

- No authentication or rate limit; the mock data is the same series for every symbol (so `A-B` is all zeros); `weight` and `timeframe` are accepted and ignored.
- The moving averages' warm-up is back-filled from later data (existing behaviour; a backtest should drop it); `atr_expansion` uses `pct_change()`, not
  meaningful across zero.
- The code is imported as `src.*` and is not an installable package (by design here); Prettier/Black formatting was not applied.
