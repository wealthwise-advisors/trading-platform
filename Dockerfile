# AutoTrader / Elliott Wave engine -- production API image (Task 10, v1.0.0).
#
# Builds and runs the FastAPI service (api.main:app), which wraps the
# Elliott Wave engine (src/analysis/), backtesting engine, and CLI. The
# React frontend (web/) is built and served separately -- see web/Dockerfile
# and docker-compose.yml, which puts both behind one origin so the browser
# never needs cross-origin requests in the default deployment.
#
# Live trading (src/live/, src/broker/rithmic_broker.py) is a documented
# stub -- see docs/RELEASE_AUDIT.md "Known limitations" -- this image runs
# backtesting, replay, and Elliott Wave analysis; it does not place live
# trades.

FROM python:3.12-slim AS base

# Real, pinned system deps only -- no build toolchain left in the final
# image beyond what pandas/numpy wheels need to import (none, on
# manylinux wheels for this Python/arch combo); kept minimal deliberately.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer cached separately from source so `docker build` after a
# pure code change doesn't reinstall ~15 packages every time.
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY api/ api/
COPY cli/ cli/
COPY benchmark/ benchmark/
COPY validation/ validation/
COPY config/settings.yaml config/settings.yaml
COPY config/credentials.yaml.example config/credentials.yaml.example
COPY pyproject.toml README.md ./

# Editable-less install of the same package the CLI/pyproject.toml define,
# so `elliott` and `import api.main` resolve identically to a dev checkout.
RUN pip install --no-cache-dir --no-deps .

# Non-root: this process only ever reads config/ (mounted read-only in
# compose) and writes to data/ and logs/ -- no reason to run as root.
RUN useradd --create-home --uid 1000 autotrader \
    && mkdir -p /app/data/historical /app/logs \
    && chown -R autotrader:autotrader /app
USER autotrader

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production startup: no --reload, bind all interfaces inside the
# container (the compose network / any reverse proxy controls what's
# actually reachable from outside).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
