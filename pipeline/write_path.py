"""
NEUROHACK — Write Path (Section 1.1.2 of Framework)

FIX APPLIED: Episodic memories without expires_at are dead-lettered,
not stored as ACTIVE with null expiry (which would be retrievable forever).

Step A: Rule Gate (deterministic)
Step B: LLM Structuring (only if gate fired)
Step C: Temporal Resolution
Step D: Conflict Check
Step E: Database Write + Buffer
"""

from typing import Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.rule_gate import evaluate_gate, GateResult
from core.structurer import MemoryStructurer, StructuredMemory
from core.temporal import TemporalResolver
from core.conflict import ConflictHandler, ConflictResolution
from core.buffer import WriteAheadBuffer
from core.dead_letter import DeadLetterQueue
from core.models import Memory, FailureStage


@dataclass
class WriteResult:
    gate_fired: bool
    matched_rules: list
    resolution: Optional[ConflictResolution] = None
    memory: Optional[Memory] = None
    dead_lettered: bool = False
    error: Optional[str] = None


class WritePath:

    def __init__(
        self,
        structurer: MemoryStructurer,
        temporal_resolver: TemporalResolver,
        conflict_handler: ConflictHandler,
        buffer: WriteAheadBuffer,
        dead_letter: DeadLetterQueue,
    ):
        self.structurer = structurer
        self.resolver = temporal_resolver
        self.conflict = conflict_handler
        self.buffer = buffer
        self.dead_letter = dead_letter

    def process(
        self,
        session: Session,
        user_id: str,
        message: str,
        turn_number: int,
    ) -> WriteResult:

        # ── Step A: Deterministic Rule Gate ───────────────────────
        gate_result = evaluate_gate(message)

        if not gate_result.fired:
            return WriteResult(gate_fired=False, matched_rules=[])

        # ── Step B: LLM Structuring ──────────────────────────────
        structured = self.structurer.structure(message, gate_result.matched_rules)

        if structured is None:
            self.dead_letter.log_failure(
                session, user_id, turn_number, message,
                FailureStage.STRUCTURING, "LLM returned malformed output"
            )
            return WriteResult(
                gate_fired=True, matched_rules=gate_result.matched_rules,
                dead_lettered=True, error="Structuring failed"
            )

        # ── Step C: Temporal Resolution ──────────────────────────
        expires_at = None
        if structured.temporal_expression:
            resolved_time, expires_at, needs_clarification = self.resolver.resolve(
                structured.temporal_expression
            )

            # CRITICAL FIX: If episodic but can't resolve time → dead-letter
            # Don't store episodic with null expires_at (would be retrievable forever)
            if structured.type == "episodic" and expires_at is None:
                if needs_clarification:
                    self.dead_letter.log_failure(
                        session, user_id, turn_number, message,
                        FailureStage.TEMPORAL,
                        f"Episodic needs time clarification: {structured.temporal_expression}",
                        partial_record={"type": structured.type, "key": structured.key, "value": structured.value}
                    )
                    return WriteResult(
                        gate_fired=True, matched_rules=gate_result.matched_rules,
                        dead_lettered=True, error="Temporal clarification needed"
                    )

        # Also: if type is episodic but NO temporal_expression at all,
        # and we can't determine an expiry, still store it but with a
        # generous default expiry (24 hours). Better than null.
        if structured.type == "episodic" and expires_at is None:
            from datetime import datetime, timedelta
            expires_at = datetime.utcnow() + timedelta(hours=24)

        # ── Step D: Conflict Check + Step E: DB Write ────────────
        try:
            resolution, memory = self.conflict.check_and_resolve(
                session, user_id, structured, turn_number,
                extraction_rule=gate_result.matched_rules[0]
            )

            # Set temporal fields if resolved
            if memory and expires_at:
                memory.expires_at = expires_at
                if self.resolver.timezone_known:
                    memory.timezone_context = str(self.resolver.tz)
                session.commit()

            # Add to write-ahead buffer
            if memory and resolution != ConflictResolution.DUPLICATE:
                self.buffer.add(memory, turn_number)

            return WriteResult(
                gate_fired=True, matched_rules=gate_result.matched_rules,
                resolution=resolution, memory=memory,
            )

        except Exception as e:
            session.rollback()
            self.dead_letter.log_failure(
                session, user_id, turn_number, message,
                FailureStage.DB_WRITE, str(e),
                partial_record={
                    "type": structured.type, "key": structured.key,
                    "value": structured.value,
                }
            )
            return WriteResult(
                gate_fired=True, matched_rules=gate_result.matched_rules,
                dead_lettered=True, error=str(e)
            )
