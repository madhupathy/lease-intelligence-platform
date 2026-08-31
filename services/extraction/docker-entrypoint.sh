#!/bin/sh
set -eu

# Railway injects PORT (typically 8080). Local compose may override.
PORT="${PORT:-8080}"

echo "Running alembic upgrade head..."
alembic upgrade head

# Demo user is fast and required for /api/auth/login — do it before listen.
echo "Seeding demo user (idempotent)..."
python -c "from app.db.seed import seed_demo_user; seed_demo_user()"

# Portfolio extraction can take minutes / fail on one PDF — never block the API.
echo "Starting portfolio seed in background (failures will not stop uvicorn)..."
(
  python -c "from app.db.seed import seed_portfolio; seed_portfolio()" \
    || echo "Portfolio seed exited with error (uvicorn continues)"
) &

echo "Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
