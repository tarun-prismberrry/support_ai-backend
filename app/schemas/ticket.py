"""
Pydantic v2 Schemas for Support Tickets, Public Dialogue Messages, and Internal Notes.
Adheres strictly to CONTRACTS.md Section 6.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Public Messages (Dialogue History) ───────────────────────────────────────

class TicketMessageCreate(BaseModel):
    """Payload to post a public message in a ticket conversation."""
    body: str = Field(..., min_length=1, max_length=10000, description="Message text content")
    sender_type: Optional[str] = Field(
        default=None,
        description="Optional sender override ('customer', 'support_agent', 'ai_agent'). Auto-detected from auth token if omitted.",
    )


class TicketMessageResponse(BaseModel):
    """Public dialogue message response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_type: str
    sender_id: Optional[uuid.UUID] = None
    body: str
    created_at: datetime


# ── Internal Notes (Staff-Only Whispers) ─────────────────────────────────────

class TicketNoteCreate(BaseModel):
    """Payload to add a private internal note to a ticket."""
    note: str = Field(..., min_length=1, max_length=10000, description="Internal staff note")


class TicketNoteResponse(BaseModel):
    """Internal note response matching CONTRACTS.md Section 6.5."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    org_id: uuid.UUID
    author_id: uuid.UUID
    note: str
    created_at: datetime


# ── Support Tickets ──────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    """Payload for submitting a new support ticket (CONTRACTS.md Section 6.3)."""
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5, max_length=10000)
    category: str = Field(..., min_length=2, max_length=64, description="e.g. Billing, Technical, Product")
    priority: str = Field(default="medium", description="low | medium | high | urgent")
    product_name: Optional[str] = Field(default=None, max_length=255)
    customer_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Target customer UUID. Ignored for customer callers; validated for staff callers.",
    )


class TicketStatusUpdate(BaseModel):
    """Payload for updating ticket lifecycle status (CONTRACTS.md Section 6.4)."""
    status: str = Field(..., description="open | in_progress | resolved | closed")
    resolution: Optional[str] = Field(default=None, max_length=5000, description="Resolution summary")


class TicketResponse(BaseModel):
    """Full ticket representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    assigned_agent_id: Optional[uuid.UUID] = None
    title: str
    description: str
    status: str
    priority: str
    category: str
    channel: str
    product_name: Optional[str] = None
    csat_rating: Optional[int] = None
    resolution: Optional[str] = None
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5, max_length=10000)
    category: str = Field(..., min_length=2, max_length=64)
    priority: str = Field(default="medium", description="low | medium | high | urgent")
    channel: str = Field(default="web", description="chat | email | web | phone")  # <-- Add this!
    product_name: Optional[str] = Field(default=None, max_length=255)
    customer_id: Optional[uuid.UUID] = Field(default=None)