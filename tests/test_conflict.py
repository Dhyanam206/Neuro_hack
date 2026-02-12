"""
NEUROHACK — Conflict Detection Tests
"""

import pytest
from core.database import DatabaseManager
from core.models import MemoryStatus, ClarificationRequest
from core.conflict import ConflictHandler, ConflictResolution
from core.structurer import StructuredMemory


class TestConflictDetection:

    def setup_method(self):
        self.db = DatabaseManager(":memory:")
        self.db.create_tables()
        self.handler = ConflictHandler()

    def test_same_turn_conflict(self):
        sm1 = StructuredMemory(type="semantic", key="preferred_language", value="English", confidence=0.9)
        sm2 = StructuredMemory(type="semantic", key="preferred_language", value="Hindi", confidence=0.9)

        with self.db.session() as session:
            self.handler.check_and_resolve(session, "user1", sm1, 2, "PREF_001")
            res, _ = self.handler.check_and_resolve(session, "user1", sm2, 2, "PREF_001")
            assert res == ConflictResolution.CONFLICTED

            # Clarification should be queued
            clar = session.query(ClarificationRequest).first()
            assert clar is not None
            assert clar.resolved_at_turn is None

    def test_clarification_throttling(self):
        """At most one pending clarification per user."""
        with self.db.session() as session:
            clar = self.handler.get_pending_clarification(session, "user1")
            # No clarifications yet
            assert clar is None
