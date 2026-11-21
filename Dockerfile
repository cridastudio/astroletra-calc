# astroletra-calc. Build from the repository root:
#   docker build -t astroletra-calc .
# Tarot scans are optional: put <card_id>.png files in assets/tarot (see app/tarot/cards.py); without them the spread
# image uses placeholders.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TAROT_ASSETS_DIR=/app/assets/tarot \
    LIBEPHEMERIS_DATA_DIR=/app/ephemeris

# WeasyPrint runtime libraries and fonts (DejaVu + Noto, with astrological symbols).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        libffi8 libjpeg62-turbo libopenjp2-7 shared-mime-info \
        fonts-dejavu-core fonts-dejavu-extra fonts-noto-core fonts-noto-color-emoji \
        fontconfig \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged user, created first so the files can be copied already owned by it.
RUN useradd --create-home --uid 10001 calc
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
# Install the pinned dependencies first (layer cache), then the application code.
RUN python -m pip install --upgrade pip \
    && python - <<'PY'
import re, subprocess, sys, tomllib
with open("pyproject.toml", "rb") as fh:
    project = tomllib.load(fh)["project"]
deps = project["dependencies"] + project["optional-dependencies"]["dev"]
subprocess.check_call([sys.executable, "-m", "pip", "install", *deps])
PY

# Reviewed LEB2 assets of the base tier (1850-2150): core + asteroids (Chiron) + exotics + apogee, ~49 MB.
# Without the asteroid group Chiron would fall back to a Keplerian approximation.
RUN libephemeris download leb2-base && ls -la /app/ephemeris/leb && chown -R calc:calc /app/ephemeris

COPY --chown=calc:calc assets ./assets
COPY --chown=calc:calc tools ./tools
COPY --chown=calc:calc tests ./tests
COPY --chown=calc:calc app ./app

# Precompiled bytecode: PYTHONDONTWRITEBYTECODE stops writing .pyc at runtime, so compile the app once here and every
# cold start of the container skips it.
RUN python -m compileall -q /app/app && chown -R calc:calc /app/app && chown calc:calc /app

USER calc

# docker-compose.yml has its own health check.
EXPOSE 8000
# One worker: 1 GiB must hold the ephemeris + WeasyPrint. uvicorn is PID 1 (exec) so SIGTERM stops it cleanly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1 --timeout-graceful-shutdown 10"]
