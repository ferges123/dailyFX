#!/bin/sh
set -eu

cleanup() {
    echo "Shutting down backend API and scheduler..."
    kill "$API_PID" "$SCHEDULER_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
    wait "$SCHEDULER_PID" 2>/dev/null || true
}

trap 'cleanup; exit 0' INT TERM

python -m app.preflight

python -m app.workers.scheduler &
SCHEDULER_PID=$!
echo "Scheduler started with PID $SCHEDULER_PID"

uvicorn app.main:app --host 0.0.0.0 --port 8438 &
API_PID=$!
echo "Backend API started with PID $API_PID"

while :; do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        API_EXIT_CODE=0
        wait "$API_PID" 2>/dev/null || API_EXIT_CODE=$?
        cleanup
        exit "$API_EXIT_CODE"
    fi

    if ! kill -0 "$SCHEDULER_PID" 2>/dev/null; then
        SCHEDULER_EXIT_CODE=0
        wait "$SCHEDULER_PID" 2>/dev/null || SCHEDULER_EXIT_CODE=$?
        cleanup
        exit "$SCHEDULER_EXIT_CODE"
    fi

    sleep 1
done
