#!/bin/sh
set -eu

cleanup() {
    echo "Shutting down backend API and scheduler..."
    kill "$API_PID" "$SCHEDULER_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
    wait "$SCHEDULER_PID" 2>/dev/null || true
}

trap 'cleanup; exit 0' INT TERM

# Wait for PostgreSQL when DATABASE_URL points to it (internal `db`
# service or an external Postgres in another docker). SQLite needs no wait.
if [ "${DATABASE_URL#postgresql}" != "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL..."
    ATTEMPTS=0
    until python -c "import os; from sqlalchemy import create_engine, text; e=create_engine(os.environ['DATABASE_URL'], connect_args={'connect_timeout': 3}); c=e.connect(); c.execute(text('SELECT 1')); c.close(); e.dispose()" 2>/dev/null; do
        ATTEMPTS=$((ATTEMPTS+1))
        if [ "$ATTEMPTS" -ge 30 ]; then
            echo "PostgreSQL still not reachable after 60s, continuing to preflight for a clear error..."
            break
        fi
        echo "PostgreSQL not ready yet (attempt $ATTEMPTS/30)..."
        sleep 2
    done
    # Final check via preflight gives a clear error if DB is still down.
fi

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
