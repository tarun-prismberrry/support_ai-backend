"""
Pydantic Schemas for Invoices, HITL Refund Pre-Approvals, and Refund Executions.
Enforces Decimal financial precision and CONTRACTS.md Section 6 specifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InvoiceResponse(BaseModel):
    """Public representation of an invoice."""

    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    ticket_id: Optional[uuid.UUID] = None
    product_name: str
    amount: Decimal
    currency: str = "USD"
    status: str
    refunded_amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApproveRefundRequest(BaseModel):
    """Payload to request an admin HITL refund pre-approval token."""

    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Refund amount to approve")


class ApproveRefundResponse(BaseModel):
    """Signed HMAC approval token response."""

    invoice_id: uuid.UUID
    amount: Decimal
    approval_token: str
    expires_at: int


class RefundRequest(BaseModel):
    """Payload to execute a refund against an invoice."""

    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Refund amount to issue")
    reason: str = Field(..., min_length=3, max_length=500, description="Business justification for refund")
    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Unique client idempotency key to prevent double charging/refunding",
    )
    approval_token: Optional[str] = Field(
        None,
        description="HMAC signed approval token (mandatory if amount > 100.00)",
    )


class RefundResponse(BaseModel):
    """Result of a completed or idempotently replayed refund operation."""

    invoice_id: uuid.UUID
    amount: Decimal
    status: str
    refunded_amount: Decimal
    remaining_balance: Decimal
    idempotency_key: str
    audit_log_id: uuid.UUID
    message: str
