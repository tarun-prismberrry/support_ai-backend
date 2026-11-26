"""
PostgreSQL Row-Level Security (RLS) Verification Tests (CONTRACTS.md §8).
Directly tests PostgreSQL kernel-level tenant isolation by executing raw queries
WITHOUT application WHERE org_id clauses.

NOTE: PostgreSQL superusers (such as the default 'postgres' user) always bypass RLS.
Therefore, these verification tests switch the active role to 'app_user' (a non-superuser
role without BYPASSRLS) to prove kernel-level policy enforcement.
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, set_db_tenant_context
from tests.conftest import ORG_A_ID, ORG_B_ID

EVE_CUSTOMER_ID = uuid.UUID("eeeeeee2-2222-2222-2222-222222222222")


@pytest.mark.asyncio
async def test_rls_filters_tickets_by_tenant_context() -> None:
    """
    Proves PostgreSQL RLS intercepts queries at the storage engine level:
    When app.current_org_id is set to Org A, a raw SELECT * FROM tickets
    (with NO WHERE clause) physically returns ONLY Org A rows.
    """
    async with async_session_factory() as db:
        await db.execute(text("SET ROLE app_user;"))
        try:
            # Set tenant context to Org A
            await set_db_tenant_context(db, ORG_A_ID)

            # Raw query with NO WHERE clause!
            result = await db.execute(text("SELECT id, org_id FROM tickets"))
            rows = result.fetchall()

            assert len(rows) > 0, "Expected Org A tickets to be returned"
            for row in rows:
                assert row.org_id == ORG_A_ID, f"RLS Leaked row belonging to {row.org_id}!"
        finally:
            await db.rollback()
            await db.execute(text("RESET ROLE;"))


@pytest.mark.asyncio
async def test_rls_filters_tickets_for_org_b() -> None:
    """When app.current_org_id is set to Org B, raw SELECT returns ONLY Org B rows."""
    async with async_session_factory() as db:
        await db.execute(text("SET ROLE app_user;"))
        try:
            # Set tenant context to Org B
            await set_db_tenant_context(db, ORG_B_ID)

            # Raw query with NO WHERE clause
            result = await db.execute(text("SELECT id, org_id FROM tickets"))
            rows = result.fetchall()

            assert len(rows) > 0, "Expected Org B tickets to be returned"
            for row in rows:
                assert row.org_id == ORG_B_ID, f"RLS Leaked row belonging to {row.org_id}!"
        finally:
            await db.rollback()
            await db.execute(text("RESET ROLE;"))


@pytest.mark.asyncio
async def test_rls_returns_zero_rows_when_context_is_unset() -> None:
    """
    Critical Security Proof:
    If a query runs without setting app.current_org_id, PostgreSQL RLS
    evaluates org_id = NULL (FALSE) and returns ZERO rows.
    """
    async with async_session_factory() as db:
        await db.execute(text("SET ROLE app_user;"))
        try:
            # Explicitly ensure app.current_org_id is reset/empty
            await db.execute(text("SELECT set_config('app.current_org_id', '', false)"))

            result = await db.execute(text("SELECT id, org_id FROM tickets"))
            rows = result.fetchall()

            assert len(rows) == 0, f"RLS Failure! Unauthenticated query saw {len(rows)} tickets!"
        finally:
            await db.rollback()
            await db.execute(text("RESET ROLE;"))


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_insert() -> None:
    """
    Proves the WITH CHECK clause:
    If a connection with Org A context tries to INSERT an Org B row,
    PostgreSQL immediately rejects it with an RLS policy violation.
    """
    async with async_session_factory() as db:
        await db.execute(text("SET ROLE app_user;"))
        try:
            await set_db_tenant_context(db, ORG_A_ID)

            # Attempt to insert an invoice belonging to Org B while in Org A context
            illegal_insert = text("""
                INSERT INTO invoices (id, org_id, customer_id, product_name, amount, currency, status, refunded_amount)
                VALUES (:id, :org_id, :customer_id, :product, :amount, 'USD', 'paid', 0.00)
            """)

            with pytest.raises(Exception) as exc_info:
                await db.execute(
                    illegal_insert,
                    {
                        "id": uuid.uuid4(),
                        "org_id": ORG_B_ID,  # Cross-tenant mismatch!
                        "customer_id": EVE_CUSTOMER_ID,
                        "product": "Hacked Subscription",
                        "amount": 999.99,
                    },
                )
                await db.flush()

            # Verify PostgreSQL raised RLS violation
            err_msg = str(exc_info.value).lower()
            assert "row-level security policy" in err_msg or "privilege" in err_msg
        finally:
            await db.rollback()
            await db.execute(text("RESET ROLE;"))

        err_msg = str(exc_info.value).lower()
        assert "row-level security" in err_msg or "policy" in err_msg
