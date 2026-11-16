# Backend image. Build from the repository root:
#   docker build -f backend/Dockerfile -t roamwise-api backend
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first so this layer is cached until the lock file changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

# Run as an unprivileged user; /data holds the SQLite file.
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser
ENV ROAMWISE_DB_PATH=/data/roamwise.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
