#!/bin/sh
set -euo pipefail

cd /app/backend

python app.py &
api_pid=$!

cleanup() {
  if [ -n "${api_pid:-}" ]; then
    kill -TERM "$api_pid" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

nginx -g 'daemon off;'
