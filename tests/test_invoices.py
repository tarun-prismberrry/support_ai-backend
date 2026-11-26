"""
Invoices & HITL Refund Pipeline Integration Tests (CONTRACTS.md §6.1-6.2 & §8).
Tests invoice queries, approval tokens, HMAC verification, balance checks, and idempotency replay.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.core.database import async_session_factory
from app.models.billing import Invoice
from tests.conftest import ORG_A_ID

# Charlie's flagship $250 invoice ID from seed.py
CHARLIE_INVOICE_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "invoice-charlie-refund-target")


@pytest.mark.asyncio
async def test_customer_views_own_invoices(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Customer can view their own billing history."""
    response = await client.get("/invoices", headers=charlie_headers)
    assert response.status_code == 200
    invoices = response.json()
    assert len(invoices) > 0
    # Every invoice must belong to Charlie
    for inv in invoices:
        assert inv["customer_id"] == "ccccccc2-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_cross_tenant_invoice_isolation(client: AsyncClient, dave_headers: dict[str, str]) -> None:
    """Org B Admin (Dave) cannot access Org A invoices (must return 404)."""
    response = await client.get(f"/invoices/{CHARLIE_INVOICE_ID}", headers=dave_headers)
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_refund_over_100_requires_hitl_approval(client: AsyncClient, bob_headers: dict[str, str]) -> None:
    """Refunding > $100 without an approval token must be rejected with REQUIRES_APPROVAL."""
    payload = {
        "amount": "250.00",
        "reason": "Customer cancellation within policy window",
        "idempotency_key": f"test-no-approval-{uuid.uuid4()}",
    }
    response = await client.post(f"/invoices/{CHARLIE_INVOICE_ID}/refund", json=payload, headers=bob_headers)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "REQUIRES_APPROVAL"
    assert "Refund amount $250.00 exceeds threshold $100.00" in data["error"]["message"]


@pytest.mark.asyncio
async def test_full_hitl_refund_workflow(
    client: AsyncClient,
    alice_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    """
    End-to-End HITL Refund Pipeline:
    1. Admin Alice generates HMAC approval token for a $250 invoice.
    2. Support Agent Bob submits the refund with the valid approval token.
    3. Operation succeeds: remaining balance drops to $0.00.
    4. Repeating the exact request replays idempotently from cache.
    """
    # Create an isolated test invoice so Charlie's seeded flagship invoice remains untouched
    test_inv_id = uuid.uuid4()
    async with async_session_factory() as db:
        test_inv = Invoice(
            id=test_inv_id,
            org_id=ORG_A_ID,
            customer_id=uuid.UUID("ccccccc2-2222-2222-2222-222222222222"),
            product_name="HITL Test Cloud Service",
            amount=Decimal("250.00"),
            currency="USD",
            status="paid",
            refunded_amount=Decimal("0.00"),
        )
        db.add(test_inv)
        await db.commit()

    # 1. Admin approves refund
    approve_resp = await client.post(
        f"/invoices/{test_inv_id}/approve-refund",
        json={"amount": "250.00"},
        headers=alice_headers,
    )
    assert approve_resp.status_code == 200
    approval_data = approve_resp.json()
    approval_token = approval_data["approval_token"]
    assert approval_token is not None

    # 2. Agent executes refund with valid approval token
    idempotency_key = f"hitl-test-{uuid.uuid4()}"
    refund_payload = {
        "amount": "250.00",
        "reason": "Customer switched to monthly subscription",
        "approval_token": approval_token,
        "idempotency_key": idempotency_key,
    }
    refund_resp = await client.post(
        f"/invoices/{test_inv_id}/refund",
        json=refund_payload,
        headers=bob_headers,
    )
    assert refund_resp.status_code == 200
    result = refund_resp.json()
    assert result["status"] == "refunded"
    assert Decimal(str(result["amount"])) == Decimal("250.00")
    assert Decimal(str(result["remaining_balance"])) == Decimal("0.00")

    # 3. Idempotency Replay Test: re-submitting with identical idempotency_key
    replay_resp = await client.post(
        f"/invoices/{test_inv_id}/refund",
        json=refund_payload,
        headers=bob_headers,
    )
    assert replay_resp.status_code == 200
    replay_result = replay_resp.json()
    assert replay_result["idempotency_key"] == idempotency_key
    assert "previously processed" in replay_result["message"]
