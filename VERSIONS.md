# Versions

What this project runs on, and why, as of 2026-11-10. Everything below was read from `uv.lock`, the installed environment or the running
container on that day; nothing is quoted from memory.

## Runtime

| | Version | Notes |
|---|---|---|
| Python | **3.14** (`.python-version`); `requires-python >=3.12` | The system has 3.14.9; the Docker image uses `python:3.14-slim` (3.14.10). CI runs 3.12 and 3.14. The README said 3.11+ and the Dockerfile used 3.11. 3.15 is available from `uv python list` (3.15.2) and was **not** adopted or tested. |
| uv | 0.13.7 | Installs and locks everything; the Docker build uses the pinned image `ghcr.io/astral-sh/uv:0.13.7`. |

## Application (`[project] dependencies`)

The project had **no lockfile and no version pins**: `requirements.txt` listed seven bare names. `pyproject.toml` now holds the dependencies and
`uv.lock` pins them (`requirements.txt` was removed).

| Package | Locked | Was |
|---|---|---|
| fastapi | 0.162.2 | unpinned |
| starlette (via fastapi) | 1.10.0 | unpinned |
| pydantic | 2.14.3 | unpinned |
| uvicorn | 0.54.0 | unpinned |
| numpy | 2.5.4 | unpinned |
| pandas | 3.1.1 | unpinned |

## Development (`[dependency-groups] dev`)

| Package | Locked | Notes |
|---|---|---|
| pytest | 9.2.0 | `pytest` was in the runtime requirements; it is a dev dependency now |
| httpx | 0.28.1 | FastAPI's test client. **Starlette 1.10 prints a deprecation warning** ("install `httpx2` instead"); that package was not added (it could not be vetted here), so the warning stays visible rather than being filtered out. |
| ruff | 0.17.4 | New lint gate (`E4 E7 E9 F B I UP`, line length 100, target py312) |

## Changes made in this pass

- `pyproject.toml` gained project metadata, dependency groups and the ruff configuration; `uv.lock` is new; `.python-version` is new.
- `uv audit` reports no known vulnerabilities (28 packages).
- The Docker image went from `python:3.11-slim` (root, no health check, unpinned `pip install`) to a two-stage build on `python:3.14-slim` that installs
  the locked set with `--locked --no-dev`, runs as an unprivileged user and has a `HEALTHCHECK`.
- `pandas` 3 and `numpy` 2.5 were already what an unpinned install resolved to; all of the original 8 tests passed on them before any code change.

## Left alone

Nothing the resolver offered was held back. Re-check with `uv lock --upgrade` and `uv audit` when touching dependencies.
