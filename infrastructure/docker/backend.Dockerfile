FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.13-slim-bookworm AS base
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
RUN uv sync --locked --no-dev
RUN useradd --create-home --uid 10001 noris
USER noris
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "noris_ai.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM base AS development
USER root
COPY backend/scripts ./scripts
COPY backend/tests ./tests
RUN uv sync --locked
USER noris
CMD ["uvicorn", "noris_ai.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS production
