"""
Tenant and Dynamic RBAC Models.
Defines Organizations (tenants) and Roles with JSONB permissions.
"""

from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User, Customer
    from app.models.ticket import Ticket
    from app.models.billing import Invoice


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Organization (Tenant) Root Model.
    Represents an enterprise client (Org A, Org B).
    """
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    customers: Mapped[list["Customer"]] = relationship(
        "Customer",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Dynamic RBAC Role Model.
    Scoped per organization with customizable JSONB permissions.
    """
    __tablename__ = "roles"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Prevent duplicate role names within the SAME organization
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_org_role_name"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="roles")
    users: Mapped[list["User"]] = relationship("User", back_populates="role")