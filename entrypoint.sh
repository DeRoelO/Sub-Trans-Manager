#!/bin/bash
set -e

PUID=${PUID:-33}
PGID=${PGID:-33}

# Ensure the group exists
if ! getent group abc >/dev/null; then
    groupadd -g ${PGID} abc
fi

# Ensure the user exists
if ! getent passwd abc >/dev/null; then
    useradd -u ${PUID} -g ${PGID} -d /app -s /bin/false abc
fi

echo "Starting Sub-Trans Manager with UID=${PUID} and GID=${PGID}"

# We ensure the config path exists and belongs to the user
mkdir -p "$CONFIG_PATH"
chown -R abc:abc "$CONFIG_PATH"

# Run FastAPI using gosu to drop privileges
# We use uvicorn to serve the API
cd /app
exec gosu abc uvicorn backend.main:app --host 0.0.0.0 --port 8060
