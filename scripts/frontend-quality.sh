#!/usr/bin/env bash
set -e

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "=== Prettier format check ==="
npm run format:check

echo "=== ESLint ==="
npm run lint

echo "All frontend quality checks passed."
