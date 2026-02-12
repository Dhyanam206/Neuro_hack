"""
NEUROHACK — Supersession Tests
"""

import pytest
from core.database import DatabaseManager
from core.models import Memory, MemoryStatus, MemoryType, generate_memory_id
from core.conflict import ConflictHandler, ConflictResolution
from core.structurer import StructuredMemory


class TestSupersession:

    def setup_method(self):
        self.db = DatabaseManager(":memory:")
        self.db.create_tables()
        self.handler = ConflictHandler()

    def test_later_turn_wins(self):
        sm1 = StructuredMemory(type="semantic", key="preferred_language", value="Kannada", confidence=0.95)
        sm2 = StructuredMemory(type="semantic", key="preferred_language", value="Hindi", confidence=0.95)

        with self.db.session() as session:
            res1, mem1 = self.handler.check_and_resolve(session, "user1", sm1, 1, "PREF_001")
            assert res1 == ConflictResolution.NO_CONFLICT

            res2, mem2 = self.handler.check_and_resolve(session, "user1", sm2, 20, "CORR_001")
            assert res2 == ConflictResolution.SUPERSEDED

            # Old memory should be superseded
            old = session.query(Memory).get(mem1.memory_id)
            assert old.status == MemoryStatus.SUPERSEDED
            assert old.superseded_by == mem2.memory_id

    def test_duplicate_detection(self):
        sm = StructuredMemory(type="semantic", key="preferred_language", value="Kannada", confidence=0.95)

        with self.db.session() as session:
            self.handler.check_and_resolve(session, "user1", sm, 1, "PREF_001")
            res, mem = self.handler.check_and_resolve(session, "user1", sm, 5, "PREF_001")
            assert res == ConflictResolution.DUPLICATE
            assert mem is None
