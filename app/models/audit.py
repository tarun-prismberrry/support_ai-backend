"""
Audit log model for compliance, security events, and HITL transaction auditing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Organization
    from app.models.user import User


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """
    Immutable audit log entry recording state-changing actions across the system.
    Write-once, append-only table.
    """

    __tablename__ = "audit_logs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="e.g. ticket.create | role.create | role.edit | refund.issue",
    )
    resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="e.g. tickets | roles | invoices",
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    organization: Mapped["Organization"] = relationship("Organization")
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        foreign_keys=[actor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, org_id={self.org_id}, "
            f"action='{self.action}', resource='{self.resource_type}:{self.resource_id}', "
            f"actor_id={self.actor_id})>"
        )