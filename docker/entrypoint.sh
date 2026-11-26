#!/bin/sh
set -e

# Wait for PostgreSQL to be ready if DATABASE_URL or DATABASE_URL_SYNC is provided
echo "Waiting for database to accept connections..."
python - << 'EOF'
import os
import sys
import time
import urllib.parse
import socket

db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
if db_url:
    clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urllib.parse.urlparse(clean_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    max_retries = 30
    for i in range(max_retries):
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"Database port {host}:{port} is open and ready.")
                sys.exit(0)
        except (socket.error, OSError):
            time.sleep(1)
    print(f"Failed to connect to database at {host}:{port} after {max_retries} seconds.")
    sys.exit(1)
EOF

echo "Applying Alembic database migrations..."
python -m alembic upgrade head

echo "Starting application service..."
exec "$@"
