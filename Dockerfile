FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY main.py ./
COPY src/ ./src/
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

# /app/data holds delta-detection state (hash_store.json) and scraped output.
# It is NOT persisted by this image alone -- whatever schedules this container
# (volume mount, CI artifact cache, etc.) must restore it before running and
# save it after, or every run will behave like a first run.
RUN mkdir -p /app/data

CMD ["python", "main.py"]
