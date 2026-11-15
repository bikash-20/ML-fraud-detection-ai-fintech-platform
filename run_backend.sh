#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"

if [ ! -d ".venv" ]; then
  echo "Virtualenv not found at backend/.venv. Creating..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

export PYTHONPATH="$ROOT_DIR/backend"
echo "🚀 Starting Wallet backend on http://127.0.0.1:8000..."
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
