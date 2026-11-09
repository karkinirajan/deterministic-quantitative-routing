# 02. Security

The API computes on mock data and has no secrets, database or file access, so the findings are about *what a router or a caller can make it
do*. The router will eventually be a language model, so everything it returns is treated as untrusted input.

## What was fixed

| Finding | Fix |
|---|---|
| **Any exception became a 500 with its text** (`detail=str(e)`): internal messages, file paths and library errors reached the caller | `BlueprintError` (the plan cannot run) is a 422 with our own message; anything else is a generic `Internal error` 500 and is logged |
| **`max_iterations` was unbounded** in the request: `{"max_iterations": 1000000000}` kept a worker smoothing for as long as the regime did not settle, and an alternating regime never settles | Limited to 1 to 100 at the API; the loop also has a circuit breaker for 2-cycles. Tested, and checked against the running container (422) |
| **No limits on the query** (any length) | 1 to 2000 characters; unknown JSON fields are refused (`extra="forbid"`) |
| **A plan could ask for anything**: any number of steps or assets, any asset text (the name is passed to the data loader, which will one day read a file or a URL), any arguments for a function | At most 20 steps and 50 assets; an asset must be a symbol (`[A-Za-z0-9][A-Za-z0-9._]{0,19}`) or `SYMBOL-SYMBOL`; each function validates its own arguments (whole numbers for windows, finite numbers in range for thresholds, no booleans) and a rejected argument is a 422 |
| **`python -m src.api.main` listened on `0.0.0.0`** with no authentication | Loopback by default; `HOST` and `PORT` override. The Docker image sets `HOST=0.0.0.0` (a container needs it) |
| **The container ran as root**, with an unpinned `pip install` | Two-stage build, locked dependencies (`--locked --no-dev`), unprivileged user (uid 10001), `HEALTHCHECK`; verified by running it |
| **`np.random.seed(42)` on every `load_data` call** reset numpy's global generator for the whole process | A local generator with the same seed: the same numbers, no global side effect |
| Blocking CPU work inside `async def` handlers | Plain `def` handlers (FastAPI runs them in its thread pool) |

## Correctness defects found on the way (they would mislead a user)

| Finding | Fix |
|---|---|
| `bollinger_squeeze` divided the band width by the *signed* average, so a spread (`A-B`, which can be negative) was read as a squeeze whenever its average was below zero | Divided by `|SMA|` |
| `price_above_sma` and `sma_crossover` filled an undefined average with 0: with a window longer than the data, every positive price was "above" it, and a short average was "above" a negative long one | An undefined average gives no signal |
| `bollinger_squeeze` filled its warm-up with 1.0, which signalled a squeeze there for any threshold above 1 | Left undefined: no signal |
| `AVERAGE` returned fractions, and for three or more inputs a running pairwise average (the last input weighed 1/2, not 1/3); a fraction also failed the response model (a 500) | The element-wise mean of all inputs, rounded, as the README specifies; a tie rounds to 0 |
| The README promised a circuit breaker for oscillation; none existed | Implemented; the response carries `stop_reason` |
| `execute` with no steps returned an empty regime | A 422 |

## Known and left alone

- **No authentication or rate limit.** It is an internal prototype: put it behind a gateway before exposing it.
- The mock data is the same series for every symbol, so a spread `A-B` is all zeros. That is the loader's documented behaviour, not a bug in the engine.
- `atr_expansion` uses `pct_change()` as a volatility proxy; on a spread that crosses zero, relative changes are not meaningful.
- The leading values of the moving averages are back-filled with the first full-window average, so the warm-up period uses a value that is
  computed from later data. It is the existing (documented) behaviour of the functions; a backtest should drop the warm-up.
- Starlette's test client prints a deprecation warning about `httpx`; see [VERSIONS.md](../VERSIONS.md).
