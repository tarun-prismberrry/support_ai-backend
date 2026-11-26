"""
Ticket Lifecycle, RBAC, Dialogue, and Multi-Tenant Isolation Tests (CONTRACTS.md §6.3-6.4 & §8).
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient

# Charlie's flagship ticket ID from seed.py
CHARLIE_TICKET_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "ticket-charlie-refund-issue")


@pytest.mark.asyncio
async def test_customer_lists_only_own_tickets(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Customers must only see their own tickets, not tickets of other customers."""
    response = await client.get("/tickets", headers=charlie_headers)
    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) > 0
    # Every ticket returned must belong to Charlie
    for t in tickets:
        assert t["customer_id"] == "ccccccc2-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_support_agent_lists_all_org_tickets(client: AsyncClient, bob_headers: dict[str, str]) -> None:
    """Support agents must be able to view tickets across the entire organization."""
    response = await client.get("/tickets", headers=bob_headers)
    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) > 1
    # Check that tickets from multiple customers in Org A appear
    customer_ids = {t["customer_id"] for t in tickets}
    assert len(customer_ids) > 1


@pytest.mark.asyncio
async def test_cross_tenant_isolation_ticket_access(client: AsyncClient, dave_headers: dict[str, str]) -> None:
    """Negative Test: Org B Admin (Dave) cannot view Org A tickets (must return 404 Not Found)."""
    response = await client.get(f"/tickets/{CHARLIE_TICKET_ID}", headers=dave_headers)
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_customer_creates_ticket(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Customer creates a ticket with category, priority, and description."""
    payload = {
        "title": "Automated Test Ticket - Login glitch",
        "description": "Encountering intermittent SSO timeouts on the mobile dashboard.",
        "category": "Technical",
        "priority": "medium",
        "channel": "web",
        "product_name": "AI Assistant Copilot",
    }
    response = await client.post("/tickets", json=payload, headers=charlie_headers)
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["title"] == payload["title"]
    assert ticket["status"] == "open"
    assert ticket["customer_id"] == "ccccccc2-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_agent_updates_ticket_status_state_machine(
    client: AsyncClient,
    charlie_headers: dict[str, str],
    bob_headers: dict[str, str],
) -> None:
    """Support agent transitions ticket status: open -> in_progress."""
    # Create an isolated ticket in open status to prevent shared-state race conditions
    create_resp = await client.post(
        "/tickets",
        json={
            "title": "State machine transition test",
            "description": "Verifying ticket status transition lifecycle",
            "category": "Technical",
            "priority": "low",
        },
        headers=charlie_headers,
    )
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["id"]

    response = await client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "in_progress", "resolution": None},
        headers=bob_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_ticket_dialogue_message_history(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Customer views dialogue history and appends a public message."""
    # 1. Fetch message history
    history_resp = await client.get(f"/tickets/{CHARLIE_TICKET_ID}/messages", headers=charlie_headers)
    assert history_resp.status_code == 200
    messages = history_resp.json()
    assert len(messages) >= 2  # Seeded with multi-turn dialogue

    # 2. Append new customer message
    new_msg_resp = await client.post(
        f"/tickets/{CHARLIE_TICKET_ID}/messages",
        json={"body": "Checking in to see if the refund has been processed yet."},
        headers=charlie_headers,
    )
    assert new_msg_resp.status_code == 201
    msg = new_msg_resp.json()
    assert msg["sender_type"] == "customer"
    assert "refund has been processed" in msg["body"]
