"""
Internal Staff Notes API Routes (Private Whispers).
Strictly guarded by ticket.note:read and ticket.note:write permissions.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import UserContext, require_permission
from app.models.ticket import Ticket, TicketNote
from app.schemas.ticket import TicketNoteCreate, TicketNoteResponse

router = APIRouter(prefix="/tickets/{ticket_id}/notes", tags=["Internal Notes"])


@router.get("", response_model=list[TicketNoteResponse], status_code=status.HTTP_200_OK)
async def list_internal_notes(
    ticket_id: uuid.UUID,
    current_user: UserContext = Depends(require_permission("ticket.note:read")),
    db: AsyncSession = Depends(get_db),
) -> list[TicketNote]:
    """
    Retrieve internal staff notes. Strictly forbidden to customers.
    """
    # Verify ticket belongs to this organization
    t_stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.org_id == current_user.org_id)
    t_res = await db.execute(t_stmt)
    if not t_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    stmt = select(TicketNote).where(
        TicketNote.ticket_id == ticket_id,
        TicketNote.org_id == current_user.org_id,
    ).order_by(TicketNote.created_at.asc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=TicketNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_internal_note(
    ticket_id: uuid.UUID,
    payload: TicketNoteCreate,
    current_user: UserContext = Depends(require_permission("ticket.note:write")),
    db: AsyncSession = Depends(get_db),
) -> TicketNote:
    """
    Add a private staff whisper to a ticket. Strictly forbidden to customers.
    """
    t_stmt = select(Ticket).where(Ticket.id == ticket_id, Ticket.org_id == current_user.org_id)
    t_res = await db.execute(t_stmt)
    if not t_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    note = TicketNote(
        org_id=current_user.org_id,
        ticket_id=ticket_id,
        author_id=current_user.id,
        note=payload.note.strip(),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note