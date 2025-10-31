#!/bin/bash

# Exit if any command fails
set -e

# Start Redis server in the background
echo "Starting Redis server..."
redis-server --daemonize yes
sleep 2  # Give Redis a moment to start

# Start Celery worker in the background
echo "Starting Celery worker..."
poetry run celery -A app.celery_app worker --loglevel=INFO --pool=solo &
CELERY_PID=$!

# Start FastAPI app (Uvicorn)
echo "Starting FastAPI server..."
poetry run uvicorn app.main:app --reload --port 8000

# When FastAPI stops, also stop Celery
echo "Stopping Celery worker..."
kill $CELERY_PID
