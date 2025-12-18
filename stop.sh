#!/bin/bash

# Exit if any command fails
set -e

echo "Stopping FastAPI (Uvicorn) server if running..."
# Kill any uvicorn process serving app.main:app
pkill -f "uvicorn app.main:app" || echo "No Uvicorn process found."

echo "Stopping Celery worker if running..."
# Kill any Celery worker for app.celery_app
pkill -f "celery -A app.celery_app worker" || echo "No Celery worker process found."

echo "Stopping Redis server if running..."
# Try a graceful Redis shutdown; ignore error if not running
if command -v redis-cli >/dev/null 2>&1; then
  redis-cli shutdown || echo "Redis was not running or could not be shut down via redis-cli."
else
  echo "redis-cli not found; skipping Redis shutdown."
fi

echo "Clearing ports (8000 for FastAPI, 6379 for Redis) if still in use..."

kill_port() {
  local port=$1
  # Use lsof if available
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -t -i :"$port" || true)
    if [ -n "$pids" ]; then
      echo "Killing PIDs on port $port: $pids"
      kill -9 $pids || true
    else
      echo "No processes found on port $port."
    fi
  # Fallback to fuser if lsof is not available
  elif command -v fuser >/dev/null 2>&1; then
    if fuser "$port"/tcp >/dev/null 2>&1; then
      echo "Killing processes on port $port using fuser..."
      fuser -k "$port"/tcp || true
    else
      echo "No processes found on port $port."
    fi
  else
    echo "Neither lsof nor fuser is available; cannot clear port $port automatically."
  fi
}

kill_port 8000
kill_port 6379

echo "All services and ports cleaned up (if they were running)."


