"""
NEUROHACK — Conflict Handling (Section 6 of Framework)

Supersession: Later turn wins. Atomic transaction.
Contradiction: Same-key conflicts detected, user asked to clarify.
Clarification throttling: At most one conflict question per turn.

INVARIANT: The system never silently resolves a conflict by guessing.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
from enum import Enum

from sqlalchemy.orm import Session

from core.models import (
    Memory, MemoryStatus, MemoryType, AuditLog, AuditAction,
    ClarificationRequest, generate_memory_id
)
from core.structurer import StructuredMemory


class ConflictResolution(str, Enum):
    NO_CONFLICT = "no_conflict"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    DUPLICATE = "duplicate"


class ConflictHandler:
    """
    Handles memory conflicts: supersession, contradiction, and duplicates.
    All operations are atomic (single transaction).
    """

    def check_and_resolve(
        self,
        session: Session,
        user_id: str,
        new_memory: StructuredMemory,
        source_turn: int,
        extraction_rule: str,
    ) -> Tuple[ConflictResolution, Optional[Memory]]:
        """
        Check for conflicts with existing memories and resolve.
        
        Returns:
            (resolution_type, created_memory_or_none)
        """
        # Find existing active memory with same (type, key)
        existing = (
            session.query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.type == new_memory.type,
                Memory.key == new_memory.key,
                Memory.status == MemoryStatus.ACTIVE,
            )
            .first()
        )

        # ── No existing memory: clean insert ─────────────────────
        if existing is None:
            mem = self._create_memory(user_id, new_memory, source_turn, extraction_rule)
            session.add(mem)
            session.flush()  # Ensure memory row exists before FK-dependent audit
            session.add(self._audit(mem.memory_id, None, MemoryStatus.ACTIVE, source_turn))
            session.commit()
            return ConflictResolution.NO_CONFLICT, mem

        # ── Duplicate: same (type, key, value) ───────────────────
        if existing.value.strip().lower() == new_memory.value.strip().lower():
            return ConflictResolution.DUPLICATE, None

        # ── Later turn wins: supersession ────────────────────────
        if source_turn > existing.source_turn:
            return self._supersede(session, existing, user_id, new_memory, source_turn, extraction_rule)

        # ── Same turn or ambiguous: conflict ─────────────────────
        if source_turn == existing.source_turn:
            return self._mark_conflict(session, existing, user_id, new_memory, source_turn, extraction_rule)

        # Earlier turn (shouldn't happen in normal flow, but handle gracefully)
        # The existing (later) memory takes precedence
        return ConflictResolution.DUPLICATE, None

    def _supersede(
        self, session, existing, user_id, new_memory, source_turn, extraction_rule
    ) -> Tuple[ConflictResolution, Memory]:
        """Atomic supersession: old → superseded, new → active."""
        now = datetime.now(timezone.utc)

        # 1. Demote the existing memory and flush to free up the UNIQUE constraint
        old_status = existing.status
        existing.status = MemoryStatus.SUPERSEDED
        existing.updated_at = now
        session.flush()

        # 2. Create the new memory and flush so its PK exists for the AuditLog FK
        new_mem = self._create_memory(user_id, new_memory, source_turn, extraction_rule)
        new_mem.supersedes = existing.memory_id
        session.add(new_mem)
        session.flush()

        # 3. Link the old memory to the new one
        existing.superseded_by = new_mem.memory_id

        # 4. Insert Audit logs
        session.add(self._audit(existing.memory_id, old_status, MemoryStatus.SUPERSEDED, source_turn))
        session.add(self._audit(new_mem.memory_id, None, MemoryStatus.ACTIVE, source_turn))
        session.commit()

        return ConflictResolution.SUPERSEDED, new_mem

    def _mark_conflict(
        self, session, existing, user_id, new_memory, source_turn, extraction_rule
    ) -> Tuple[ConflictResolution, Memory]:
        """Mark both as conflicted and queue clarification."""
        now = datetime.now(timezone.utc)

        # Create the new memory as conflicted
        new_mem = self._create_memory(user_id, new_memory, source_turn, extraction_rule)
        new_mem.status = MemoryStatus.CONFLICTED

        # Mark existing as conflicted
        old_status = existing.status
        existing.status = MemoryStatus.CONFLICTED
        existing.updated_at = now

        # Queue clarification
        clarification = ClarificationRequest(
            user_id=user_id,
            memory_id_a=existing.memory_id,
            memory_id_b=new_mem.memory_id,
        )

        session.add(new_mem)
        session.flush()  # Ensure new memory row exists before FK-dependent audit + clarification
        session.add(clarification)
        session.add(self._audit(existing.memory_id, old_status, MemoryStatus.CONFLICTED, source_turn))
        session.add(self._audit(new_mem.memory_id, None, MemoryStatus.CONFLICTED, source_turn))
        session.commit()

        return ConflictResolution.CONFLICTED, new_mem

    def get_pending_clarification(self, session: Session, user_id: str) -> Optional[ClarificationRequest]:
        """
        Get the most recent unresolved clarification.
        Returns at most ONE per turn (throttling).
        """
        return (
            session.query(ClarificationRequest)
            .filter(
                ClarificationRequest.user_id == user_id,
                ClarificationRequest.resolved_at_turn == None,
            )
            .order_by(ClarificationRequest.created_at.desc())
            .first()
        )

    def resolve_clarification(
        self, session: Session, clarification_id: int,
        chosen_memory_id: str, current_turn: int
    ):
        """Resolve a conflict: chosen → active, other → superseded."""
        clar = session.query(ClarificationRequest).get(clarification_id)
        if not clar:
            return

        other_id = clar.memory_id_b if chosen_memory_id == clar.memory_id_a else clar.memory_id_a

        chosen = session.query(Memory).get(chosen_memory_id)
        other = session.query(Memory).get(other_id)

        if chosen:
            chosen.status = MemoryStatus.ACTIVE
            chosen.updated_at = datetime.now(timezone.utc)
            session.add(self._audit(chosen.memory_id, MemoryStatus.CONFLICTED, MemoryStatus.ACTIVE, current_turn))

        if other:
            other.status = MemoryStatus.SUPERSEDED
            other.superseded_by = chosen_memory_id
            other.updated_at = datetime.now(timezone.utc)
            session.add(self._audit(other.memory_id, MemoryStatus.CONFLICTED, MemoryStatus.SUPERSEDED, current_turn))

        clar.resolved_at_turn = current_turn
        clar.resolved_value = chosen_memory_id
        session.commit()

    def _create_memory(self, user_id, sm: StructuredMemory, turn: int, rule: str) -> Memory:
        return Memory(
            memory_id=generate_memory_id(),
            user_id=user_id,
            type=MemoryType(sm.type),
            key=sm.key,
            value=sm.value,
            status=MemoryStatus.ACTIVE,
            confidence=sm.confidence,
            source_turn=turn,
            extraction_rule=rule,
        )

    def _audit(self, memory_id, prev, new_status, turn) -> AuditLog:
        return AuditLog(
            memory_id=memory_id,
            action=AuditAction.CREATED if prev is None else AuditAction(new_status.value),
            previous_status=prev,
            new_status=new_status,
            turn_number=turn,
        )
