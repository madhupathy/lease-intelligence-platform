#!/bin/sh
set -eu

PORT="${PORT:-8000}"

echo "Running alembic upgrade head..."
alembic upgrade head

echo "Seeding demo user..."
python -m app.db.seed

# Portfolio PDF seed: only when table empty and both LLM keys are present.
echo "Running portfolio seed (conditional)..."
python seed/seed.py

echo "Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
