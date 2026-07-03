FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
# --no-dev keeps pytest out of the runtime image.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY main.py ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Warm the tiktoken vocab into the image so the daily run never has to download
# it mid-job (chunk.py encodes with the gpt-4o encoding).
RUN python -c "import tiktoken; tiktoken.encoding_for_model('gpt-4o').encode('warmup')"

# /app/data holds delta-detection state (hash_store.json). It is NOT persisted by
# this image alone -- the scheduler must mount it (docker run -v ...:/app/data)
# so state survives between daily runs, or every run behaves like a first run.
RUN mkdir -p /app/data

CMD ["python", "main.py"]
