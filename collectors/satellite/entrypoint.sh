#!/bin/bash
set -e

# Export environment variables for cron
# Cron runs in a minimal environment, so we need to pass our env vars
printenv | grep -E '^(COPERNICUS_|PYTHONPATH|PYTHONUNBUFFERED)' > /etc/environment

echo "Starting satellite collector..."
echo "Cron schedule: Daily at 06:00 UTC"

# Run once on startup (optional, can be disabled by setting RUN_ON_STARTUP=false)
if [ "${RUN_ON_STARTUP:-true}" = "true" ]; then
    echo "Running initial collection..."
    cd /app && python src/download.py
fi

# Start cron daemon in foreground
echo "Starting cron daemon..."
exec cron -f
