#!/bin/bash
set -e

# Enable PostgreSQL Extensions and create multi-service schemas
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "vector";
    CREATE SCHEMA IF NOT EXISTS orchestrator;
    GRANT ALL ON SCHEMA orchestrator TO $POSTGRES_USER;
EOSQL