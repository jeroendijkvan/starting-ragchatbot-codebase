#!/usr/bin/env bash
set -e

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "=== Formatting frontend files with Prettier ==="
npm run format

echo "Done. All frontend files formatted."
