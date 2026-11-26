#!/bin/bash
set -e

# Enable PostgreSQL Extensions and create multi-service schemas
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "vector";
    CREATE SCHEMA IF NOT EXISTS orchestrator;

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'orchestrator_user') THEN
            CREATE USER orchestrator_user WITH PASSWORD 'orchestrator_pass';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
            CREATE USER app_user WITH PASSWORD 'app_pass';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE support_ai_db TO orchestrator_user, app_user;
    GRANT USAGE, CREATE ON SCHEMA orchestrator TO orchestrator_user;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA orchestrator TO orchestrator_user;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA orchestrator TO orchestrator_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA orchestrator GRANT ALL ON TABLES TO orchestrator_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA orchestrator GRANT ALL ON SEQUENCES TO orchestrator_user;
    REVOKE ALL ON SCHEMA public FROM orchestrator_user;

    GRANT USAGE ON SCHEMA public TO app_user;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;
EOSQL