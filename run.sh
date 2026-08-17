#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ creating virtualenv"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env

set -a; . ./.env; set +a

echo "→ running migrations"
./.venv/bin/alembic upgrade head

exec ./.venv/bin/uvicorn app.main:app --reload --port 8000
