"""
Knowledge Base Article model with pgvector embeddings for RAG semantic search.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Organization


class KnowledgeBaseArticle(Base, UUIDPrimaryKeyMixin):
    """
    Chunked Knowledge Base article with 1536-dim vector embedding.
    Supports tenant-isolated semantic search with categorical access tiers.
    """

    __tablename__ = "knowledge_base_articles"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Source document identifier grouping related chunks",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sequential index of the chunk within the document (0, 1, 2...)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    access_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="public | internal_staff | admin_only",
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
        comment="384-dimensional embedding vector (e.g., text-embedding-3-small)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Composite Index for Multi-Tenant Scoped Tier Lookups
    # -------------------------------------------------------------------------
    __table_args__ = (
        Index("idx_kb_lookup", "org_id", "access_level"),
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    organization: Mapped["Organization"] = relationship("Organization")

    def __repr__(self) -> str:
        return (
            f"<KnowledgeBaseArticle(id={self.id}, org_id={self.org_id}, "
            f"doc_id={self.document_id}, chunk={self.chunk_index}, "
            f"access='{self.access_level}', title='{self.title[:30]}')>"
        )