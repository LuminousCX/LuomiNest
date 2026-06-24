#!/bin/sh
# LuomiNest Backend Startup Script
set -e

export PYTHONUNBUFFERED=1

# Run database migrations if alembic is configured
if [ -f "scripts/migrate/alembic.ini" ]; then
    echo "[LuomiNest] Running database migrations..."
    alembic -c scripts/migrate/alembic.ini upgrade head || echo "[LuomiNest] Migration skipped or failed; continuing startup."
fi

# Start application server
echo "[LuomiNest] Starting backend server..."
exec uvicorn app.core.app_factory:create_app \
    --host "${BACKEND_HOST:-0.0.0.0}" \
    --port "${BACKEND_PORT:-18000}" \
    --log-level "${LOG_LEVEL:-info}" \
    --workers "${BACKEND_WORKERS:-1}"
