"""
Internal Staff Notes & Whispers Tests (CONTRACTS.md §6.4 & §8).
Enforces RBAC boundary: Agents can read/write, Customers are strictly 403 Forbidden.
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient

CHARLIE_TICKET_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "ticket-charlie-refund-issue")


@pytest.mark.asyncio
async def test_agent_creates_and_reads_internal_notes(client: AsyncClient, bob_headers: dict[str, str]) -> None:
    """Support agents with ticket.note:write can record internal whispers."""
    # 1. Add internal staff note
    create_resp = await client.post(
        f"/tickets/{CHARLIE_TICKET_ID}/notes",
        json={"note": "Automated verification note: escalated to finance for batch refund payout."},
        headers=bob_headers,
    )
    assert create_resp.status_code == 201
    note = create_resp.json()
    assert "escalated to finance" in note["note"]
    assert note["author_id"] == "bbbbbbb1-1111-1111-1111-111111111111"

    # 2. Read notes list
    list_resp = await client.get(f"/tickets/{CHARLIE_TICKET_ID}/notes", headers=bob_headers)
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) > 0


@pytest.mark.asyncio
async def test_customer_cannot_read_internal_notes(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Security Boundary: Customers attempting to read staff whispers must be rejected with 403 FORBIDDEN."""
    response = await client.get(f"/tickets/{CHARLIE_TICKET_ID}/notes", headers=charlie_headers)
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_customer_cannot_write_internal_notes(client: AsyncClient, charlie_headers: dict[str, str]) -> None:
    """Security Boundary: Customers attempting to write staff whispers must be rejected with 403 FORBIDDEN."""
    response = await client.post(
        f"/tickets/{CHARLIE_TICKET_ID}/notes",
        json={"note": "I am trying to inject a customer note as an internal whisper."},
        headers=charlie_headers,
    )
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "FORBIDDEN"
