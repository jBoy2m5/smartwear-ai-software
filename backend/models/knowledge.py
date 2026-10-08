"""Append-only revisions of procedures and reviewed session knowledge."""
from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.base import Base


class KnowledgeRevision(Base):
    __tablename__ = 'knowledge_revisions'
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
