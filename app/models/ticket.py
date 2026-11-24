"""
Ticketing Domain Models.
Defines Ticket, TicketMessage (public chat dialogue), and TicketNote (staff-only whispers).
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Organization
    from app.models.user import User, Customer
    from app.models.billing import Invoice


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Support Ticket Model.
    Represents the core customer support issue lifecycle.
    """
    __tablename__ = "tickets"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Core Ticket Attributes
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium", nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Operational & Kaggle Support Fields
    channel: Mapped[str] = mapped_column(String(32), default="chat", nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    csat_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Database Check Constraint for CSAT rating (1 to 5)
    __table_args__ = (
        CheckConstraint("csat_rating >= 1 AND csat_rating <= 5", name="check_csat_range"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="tickets")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="tickets")
    assigned_agent: Mapped["User | None"] = relationship(
        "User",
        back_populates="assigned_tickets",
        foreign_keys=[assigned_agent_id],
    )
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )
    notes: Mapped[list["TicketNote"]] = relationship(
        "TicketNote",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketNote.created_at",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="ticket",
    )


class TicketMessage(Base, UUIDPrimaryKeyMixin):
    """
    Public Ticket Conversation Message (Dialogue Turn).
    Visible to customer, support agents, and LangGraph AI agents.
    """
    __tablename__ = "ticket_messages"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'customer', 'support_agent', 'ai_agent', 'system'
    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # Nullable for AI agents
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="messages")


class TicketNote(Base, UUIDPrimaryKeyMixin):
    """
    Internal Staff-Only Note (Private Whisper).
    Visible ONLY to staff (Support_Agent and Org_Admin). Never returned to customers.
    """
    __tablename__ = "ticket_notes"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="notes")
    author: Mapped["User"] = relationship("User", back_populates="authored_notes")