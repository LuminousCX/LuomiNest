# LuomiNest Backend Dockerfile
# Multi-architecture build support (linux/amd64, linux/arm64)
# Build command:
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -t luominest/backend:latest --push .
#
# Single-arch local build:
#   docker buildx build --platform linux/arm64 -t luominest/backend:arm64 --load .

FROM python:3.12-slim AS base

# TARGETARCH is automatically set by buildx (amd64 | arm64)
ARG TARGETPLATFORM=linux/amd64
ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies; add platform-specific packages here if needed
# e.g., ARM64 may require different binary packages for certain native extensions
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
