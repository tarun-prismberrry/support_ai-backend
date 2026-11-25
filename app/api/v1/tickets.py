"""
Support Ticket and Public Dialogue Message API Routes.
Enforces multi-tenant scoping, state transitions, and RBAC rules (CONTRACTS.md Section 6).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import UserContext, get_current_user, require_permission
from app.models.ticket import Ticket, TicketMessage
from app.models.user import Customer
from app.schemas.ticket import (
    TicketCreate,
    TicketMessageCreate,
    TicketMessageResponse,
    TicketResponse,
    TicketStatusUpdate,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

# Valid state machine transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"resolved", "closed", "open"},
    "resolved": {"closed", "in_progress"},
    "closed": {"in_progress"},
}


@router.get("", response_model=list[TicketResponse], status_code=status.HTTP_200_OK)
async def list_or_search_tickets(
    query: Optional[str] = Query(None, description="Case-insensitive search on title/description"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="Filter by priority"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Ticket]:
    """
    List or search tickets. Staff sees all org tickets; customers see only their own.
    """
    stmt = select(Ticket).where(Ticket.org_id == current_user.org_id)

    # Scoping: If customer, restrict to own tickets
    if not current_user.has_permission("ticket.read:org"):
        if not current_user.customer_id:
            return []
        stmt = stmt.where(Ticket.customer_id == current_user.customer_id)

    if status_filter:
        stmt = stmt.where(Ticket.status == status_filter.lower())
    if priority_filter:
        stmt = stmt.where(Ticket.priority == priority_filter.lower())
    if query:
        search_pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Ticket.title.ilike(search_pattern),
                Ticket.description.ilike(search_pattern),
            )
        )

    stmt = stmt.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    """
    Create a new support ticket.
    Customers automatically bind their own customer_id. Staff can target a customer.
    """
    is_staff = current_user.has_permission("ticket.write:org") or current_user.has_permission("*")

    if is_staff:
        if not payload.customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Staff callers must specify 'customer_id'",
            )
        target_customer_id = payload.customer_id
        # Verify customer exists in the same tenant
        cust_stmt = select(Customer).where(
            Customer.id == target_customer_id,
            Customer.org_id == current_user.org_id,
        )
        cust_res = await db.execute(cust_stmt)
        if not cust_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found in this organization",
            )
    else:
        # Caller is customer: strictly bind own customer_id
        if not current_user.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller has no linked customer profile",
            )
        target_customer_id = current_user.customer_id

    ticket = Ticket(
        org_id=current_user.org_id,
        customer_id=target_customer_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category.strip(),
        priority=payload.priority.lower(),
        product_name=payload.product_name,
        channel=payload.channel.lower() if payload.channel else "web",   # <-- Add this!
        status="open",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketResponse, status_code=status.HTTP_200_OK)
async def get_ticket_details(
    ticket_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    """
    Retrieve ticket details. Enforces tenant and ownership boundaries.
    """
    stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.org_id == current_user.org_id)
    if not current_user.has_permission("ticket.read:org"):
        stmt = stmt.where(Ticket.customer_id == current_user.customer_id)

    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return ticket


@router.patch("/{ticket_id}/status", response_model=TicketResponse, status_code=status.HTTP_200_OK)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    """
    Update ticket lifecycle status with state machine and RBAC transition validation.
    """
    target_status = payload.status.lower()
    stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.org_id == current_user.org_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    is_staff = current_user.has_permission("ticket.status:update") or current_user.has_permission("*")

    if not is_staff:
        # Customer rule from CONTRACTS.md Section 6.4:
        # Allowed ONLY if updating own ticket from resolved -> closed
        is_own_ticket = (ticket.customer_id == current_user.customer_id)
        if not (is_own_ticket and ticket.status == "resolved" and target_status == "closed"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers can only close resolved tickets",
            )
    else:
        # Staff state machine transition check
        allowed = VALID_TRANSITIONS.get(ticket.status, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid status transition from '{ticket.status}' to '{target_status}'",
            )

    ticket.status = target_status
    if payload.resolution:
        ticket.resolution = payload.resolution
    if target_status == "resolved" and not ticket.resolved_at:
        ticket.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(ticket)
    return ticket


# ── Public Dialogue Messages ─────────────────────────────────────────────────

@router.get("/{ticket_id}/messages", response_model=list[TicketMessageResponse], status_code=status.HTTP_200_OK)
async def list_ticket_messages(
    ticket_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TicketMessage]:
    """List public dialogue messages in a ticket."""
    # Verify access to parent ticket
    await get_ticket_details(ticket_id=ticket_id, current_user=current_user, db=db)

    stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{ticket_id}/messages", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED)
async def add_ticket_message(
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketMessage:
    """Post a public message to a ticket conversation."""
    ticket = await get_ticket_details(ticket_id=ticket_id, current_user=current_user, db=db)

    # Determine sender type
    if payload.sender_type:
        sender_type = payload.sender_type.lower()
    elif current_user.customer_id:
        sender_type = "customer"
    else:
        sender_type = "support_agent"

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type=sender_type,
        sender_id=current_user.id,
        body=payload.body.strip(),
    )
    db.add(message)

    # Update first response timestamp if staff reply
    if sender_type in {"support_agent", "ai_agent"} and not ticket.first_response_at:
        ticket.first_response_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(message)
    return message