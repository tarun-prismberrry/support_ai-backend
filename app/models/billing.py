"""
Billing and financial models for multi-tenant customer transactions and HITL refunds.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Organization
    from app.models.user import Customer
    from app.models.ticket import Ticket


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Invoice entity representing a financial transaction or billing record.
    Supports HITL refund workflows and ties Kaggle purchase history.
    """

    __tablename__ = "invoices"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    product_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="paid",
        nullable=False,
        comment="paid | pending | refunded | partially_refunded",
    )
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="invoices",
    )
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="invoices",
    )
    ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket",
        back_populates="invoices",
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, org_id={self.org_id}, "
            f"product='{self.product_name}', amount={self.amount} {self.currency}, "
            f"status='{self.status}')>"
        )