#!/bin/sh
set -eu

PORT="${PORT:-8000}"

echo "Running alembic upgrade head..."
alembic upgrade head

echo "Seeding demo user and portfolio (conditional)..."
python -m app.db.seed

echo "Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
