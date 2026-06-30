# One image for the API, the worker and the Paystub sandbox; compose picks the command.
FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 carob && mkdir -p /data && chown carob /data
USER carob
EXPOSE 8000
# No HEALTHCHECK here: the API, the worker and Paystub each answer on their own port, so
# the Compose files say how to check each service.
CMD ["uvicorn", "carob.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
