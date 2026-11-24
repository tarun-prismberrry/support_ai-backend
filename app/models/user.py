"""
User and Customer Domain Models.
Defines User (authentication, credentials, roles) and Customer (business profiles, demographics).
"""

from typing import Any, TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Organization, Role
    from app.models.ticket import Ticket, TicketNote
    from app.models.billing import Invoice
    from app.models.audit import AuditLog


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Authenticated User Account Model.
    Represents internal staff (Alice, Bob) or logged-in customers (Charlie).
    """
    __tablename__ = "users"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Unique email per organization
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_org_user_email"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    
    # 1:1 link to customer profile (uselist=False)
    customer: Mapped["Customer | None"] = relationship(
        "Customer",
        back_populates="user",
        uselist=False,
    )

    # Reverse relationships to tickets and notes
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="assigned_agent",
        foreign_keys="[Ticket.assigned_agent_id]",
    )
    authored_notes: Mapped[list["TicketNote"]] = relationship(
        "TicketNote",
        back_populates="author",
        foreign_keys="[TicketNote.author_id]",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="actor",
        foreign_keys="[AuditLog.actor_id]",
    )


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Customer Profile Model.
    Stores customer contact information, Kaggle demographic fields, and extensible metadata.
    """
    __tablename__ = "customers"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Kaggle dataset support fields
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="customers")
    user: Mapped["User | None"] = relationship("User", back_populates="customer")
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="customer",
        cascade="all, delete-orphan",
    )