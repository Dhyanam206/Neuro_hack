"""
NEUROHACK — Memory Schema (Section 2 of Framework)

Source of truth: relational database (SQLite).
Every memory record, regardless of type, conforms to this schema.

INVARIANT: At most one active semantic memory exists per (user_id, type, key) triple.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, Enum,
    ForeignKey, Index, UniqueConstraint, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ─── Enums ────────────────────────────────────────────────────────

class MemoryType(str, enum.Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


class MemoryStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CONFLICTED = "conflicted"


class FailureStage(str, enum.Enum):
    STRUCTURING = "structuring"
    TEMPORAL = "temporal"
    CONFLICT = "conflict"
    DB_WRITE = "db_write"


class AuditAction(str, enum.Enum):
    CREATED = "created"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CONFLICTED = "conflicted"
    RESOLVED = "resolved"
    ACCESSED = "accessed"


# ─── Base ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


def generate_memory_id() -> str:
    return f"mem_{uuid.uuid4().hex[:12]}"


# ─── Memory Table ─────────────────────────────────────────────────

class Memory(Base):
    """
    Primary memory table. One row per memory record.
    Superseded and expired records are retained for audit, never deleted.
    """
    __tablename__ = "memories"

    memory_id = Column(String(20), primary_key=True, default=generate_memory_id)
    user_id = Column(String(64), nullable=False, index=True)

    # Type & content
    type = Column(Enum(MemoryType), nullable=False)
    key = Column(String(256), nullable=False)
    value = Column(Text, nullable=False)

    # Lifecycle
    status = Column(Enum(MemoryStatus), nullable=False, default=MemoryStatus.ACTIVE)
    confidence = Column(Float, nullable=False)

    # Provenance
    source_turn = Column(Integer, nullable=False)
    extraction_rule = Column(String(128), nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    last_accessed_turn = Column(Integer, nullable=True)

    # Temporal (episodic only)
    expires_at = Column(DateTime, nullable=True)
    timezone_context = Column(String(64), nullable=True)

    # Supersession chain
    supersedes = Column(String(20), ForeignKey("memories.memory_id"), nullable=True)
    superseded_by = Column(String(20), ForeignKey("memories.memory_id"), nullable=True)

    # Vector index pointer
    embedding_id = Column(String(64), nullable=True)

    # ─── Indexes ──────────────────────────────────────────────────
    __table_args__ = (
        # Primary retrieval index
        Index("idx_active_lookup", "user_id", "type", "key", "status"),
        # Temporal range queries
        Index("idx_temporal", "user_id", "type", "status", "expires_at"),
        # Recency-based retrieval
        Index("idx_recency", "user_id", "status", "last_accessed_turn"),
        # CRITICAL: At most one active semantic memory per key per user
        Index(
            "uq_active_semantic",
            "user_id", "type", "key",
            unique=True,
            sqlite_where=(status == MemoryStatus.ACTIVE) & (type == MemoryType.SEMANTIC)
        ),
    )

    def __repr__(self):
        return (
            f"<Memory {self.memory_id} [{self.status.value}] "
            f"{self.type.value}:{self.key}={self.value}>"
        )

    def is_retrievable(self) -> bool:
        """Check if this memory passes all retrieval filters."""
        if self.status != MemoryStatus.ACTIVE:
            return False
        if self.confidence < 0.7:  # TODO: pull from config
            return False
        if self.expires_at:
            now = datetime.utcnow()
            exp = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
            if exp < now:
                return False
        return True


# ─── Dead Letter Table ────────────────────────────────────────────

class DeadLetter(Base):
    """
    Captures failed extraction attempts. Prevents silent memory loss.
    """
    __tablename__ = "dead_letters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    turn_number = Column(Integer, nullable=False)
    original_message = Column(Text, nullable=False)
    failure_stage = Column(Enum(FailureStage), nullable=False)
    error_message = Column(Text, nullable=False)
    partial_record = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    retry_count = Column(Integer, nullable=False, default=0)
    resolved = Column(Boolean, nullable=False, default=False)


# ─── Clarification Queue ─────────────────────────────────────────

class ClarificationRequest(Base):
    """
    Stores pending conflict clarification requests.
    At most one clarification is presented per turn.
    """
    __tablename__ = "clarification_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    memory_id_a = Column(String(20), ForeignKey("memories.memory_id"), nullable=False)
    memory_id_b = Column(String(20), ForeignKey("memories.memory_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    presented_at_turn = Column(Integer, nullable=True)
    resolved_at_turn = Column(Integer, nullable=True)
    resolved_value = Column(String(20), ForeignKey("memories.memory_id"), nullable=True)


# ─── Audit Log ────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Append-only log of all memory state transitions.
    Never queried during response path — exists solely for post-hoc auditability.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(String(20), ForeignKey("memories.memory_id"), nullable=False)
    action = Column(Enum(AuditAction), nullable=False)
    previous_status = Column(Enum(MemoryStatus), nullable=True)
    new_status = Column(Enum(MemoryStatus), nullable=False)
    turn_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
