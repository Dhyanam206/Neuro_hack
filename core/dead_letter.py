"""
NEUROHACK — Dead-Letter Queue (Section 11.2 of Framework)

Captures any memory extraction that fails after the rule gate fires.
Prevents silent memory loss. Retries once, then logs permanently.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from core.models import DeadLetter, FailureStage


class DeadLetterQueue:
    """
    Logs and optionally retries failed memory extractions.
    """

    def log_failure(
        self,
        session: Session,
        user_id: str,
        turn_number: int,
        original_message: str,
        failure_stage: FailureStage,
        error_message: str,
        partial_record: Optional[dict] = None,
    ) -> DeadLetter:
        """Log a failed extraction attempt."""
        entry = DeadLetter(
            user_id=user_id,
            turn_number=turn_number,
            original_message=original_message,
            failure_stage=failure_stage,
            error_message=error_message,
            partial_record=json.dumps(partial_record) if partial_record else None,
        )
        session.add(entry)
        session.commit()
        return entry

    def get_retryable(self, session: Session, user_id: str):
        """Get failed extractions eligible for retry (retry_count < 1)."""
        return (
            session.query(DeadLetter)
            .filter(
                DeadLetter.user_id == user_id,
                DeadLetter.resolved == False,
                DeadLetter.retry_count < 1,
            )
            .all()
        )

    def mark_retried(self, session: Session, dead_letter_id: int):
        """Increment retry count."""
        entry = session.query(DeadLetter).get(dead_letter_id)
        if entry:
            entry.retry_count += 1
            session.commit()

    def mark_resolved(self, session: Session, dead_letter_id: int):
        """Mark as resolved (successful retry)."""
        entry = session.query(DeadLetter).get(dead_letter_id)
        if entry:
            entry.resolved = True
            session.commit()

    def get_unresolved_count(self, session: Session, user_id: str) -> int:
        """Count unresolved failures for monitoring."""
        return (
            session.query(DeadLetter)
            .filter(
                DeadLetter.user_id == user_id,
                DeadLetter.resolved == False,
            )
            .count()
        )
