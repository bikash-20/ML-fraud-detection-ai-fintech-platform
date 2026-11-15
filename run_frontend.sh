#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/frontend"

echo "🚀 Starting Wallet frontend on http://localhost:3000..."
exec npm run dev
