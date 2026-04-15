#!/bin/bash

# Default to 33 (www-data) if not provided
PUID=${PUID:-33}
PGID=${PGID:-33}

echo "Starting Sub-Trans Manager with UID=${PUID} and GID=${PGID}"

# We ensure the config path exists and belongs to the requested PID/GID
mkdir -p "$CONFIG_PATH"
chown -R ${PUID}:${PGID} "$CONFIG_PATH" 2>/dev/null || true

# Run FastAPI using gosu to drop privileges to the requested raw numbers
# This bypasses the need for the user to explicitly exist in /etc/passwd
cd /app/backend
exec gosu ${PUID}:${PGID} uvicorn main:app --host 0.0.0.0 --port 8060
