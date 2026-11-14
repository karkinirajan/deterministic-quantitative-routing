# syntax=docker/dockerfile:1

# ---- build: install the locked dependencies into a virtual environment
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev

# ---- run
FROM python:3.14-slim
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8000
WORKDIR /app
RUN useradd --system --no-create-home --uid 10001 app
COPY --from=build /app/.venv ./.venv
COPY src ./src
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=2)"
# The HOST and PORT variables are read by `python -m src.api.main`; uvicorn on 0.0.0.0 is what a container needs.
CMD ["python", "-m", "src.api.main"]
