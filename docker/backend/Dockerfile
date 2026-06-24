# LuomiNest Backend Dockerfile
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . && rm -rf /root/.cache

COPY . .

FROM base AS development
RUN pip install --no-cache-dir -e ".[dev]" && rm -rf /root/.cache
CMD ["uvicorn", "app.core.app_factory:create_app", "--host", "0.0.0.0", "--port", "18000", "--reload"]

FROM base AS production
COPY ./docker/backend/start.sh /app/start.sh
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
