"""enable_rls_tenant_policies

Revision ID: b71e33cfa5d2
Revises: a60f22bfa6a3
Create Date: 2026-11-26 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b71e33cfa5d2'
down_revision: Union[str, Sequence[str], None] = 'a60f22bfa6a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Business domain tables subject to strict tenant isolation
DOMAIN_TENANT_TABLES = [
    "customers",
    "tickets",
    "ticket_messages",
    "ticket_notes",
    "invoices",
    "audit_logs",
    "knowledge_base_articles",
]


def upgrade() -> None:
    """
    Enables PostgreSQL Row-Level Security (RLS) on all tenant-scoped business tables.
    Forces RLS to ensure queries without explicit WHERE org_id clauses are physically blocked.
    """
    # 0. Ensure non-superuser app_user exists and has table privileges
    # (Superusers bypass RLS by design in PostgreSQL; app_user enforces strict RLS)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
                CREATE USER app_user WITH PASSWORD 'app_pass';
            END IF;
        END
        $$;
        GRANT USAGE ON SCHEMA public TO app_user;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;
    """)

    # 1. Strict Tenant Isolation on Business Domain Tables
    for table in DOMAIN_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation_policy ON {table}
            FOR ALL
            USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
            WITH CHECK (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);
        """)

    # 2. Roles Table: allow system roles or matching tenant context
    op.execute("ALTER TABLE roles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE roles FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY role_tenant_isolation_policy ON roles
        FOR ALL
        USING (
            is_system = TRUE 
            OR org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
        )
        WITH CHECK (
            org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
        );
    """)


def downgrade() -> None:
    """
    Disables PostgreSQL Row-Level Security (RLS) and removes isolation policies.
    """
    # 1. Drop policies and disable RLS on Domain Tables
    for table in DOMAIN_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    # 2. Revert Roles Table
    op.execute("DROP POLICY IF EXISTS role_tenant_isolation_policy ON roles;")
    op.execute("ALTER TABLE roles NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE roles DISABLE ROW LEVEL SECURITY;")
