"""
SQLAlchemy 2.0 Models Package.
Exports all 10 relational entities and mixins.
"""

from app.models.audit import AuditLog
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.billing import Invoice
from app.models.rag import KnowledgeBaseArticle
from app.models.tenant import Organization, Role
from app.models.ticket import Ticket, TicketMessage, TicketNote
from app.models.user import Customer, User

__all__ = [
    "UUIDPrimaryKeyMixin",
    "TimestampMixin",
    "Organization",
    "Role",
    "User",
    "Customer",
    "Ticket",
    "TicketMessage",
    "TicketNote",
    "Invoice",
    "AuditLog",
    "KnowledgeBaseArticle",
]