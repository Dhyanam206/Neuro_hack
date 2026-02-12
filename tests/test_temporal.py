"""
NEUROHACK — Temporal Resolution Tests
"""

import pytest
from datetime import datetime
from core.temporal import TemporalResolver
import pytz


class TestTemporalResolver:

    def setup_method(self):
        self.resolver = TemporalResolver("Asia/Kolkata")
        self.ref_time = pytz.timezone("Asia/Kolkata").localize(
            datetime(2026, 2, 8, 14, 30, 0)
        )

    def test_tomorrow(self):
        resolved, expires, clarify = self.resolver.resolve("tomorrow", self.ref_time)
        assert resolved.day == 9
        assert not clarify

    def test_tomorrow_with_time(self):
        resolved, expires, clarify = self.resolver.resolve("tomorrow after 11 AM", self.ref_time)
        assert resolved.day == 9
        assert resolved.hour == 11

    def test_duration(self):
        resolved, expires, clarify = self.resolver.resolve("in 2 hours", self.ref_time)
        assert resolved.hour == 16
        assert resolved.minute == 30

    def test_ambiguous_time_only(self):
        """Time without day context should flag for potential clarification."""
        resolved, expires, clarify = self.resolver.resolve("after 11", self.ref_time)
        assert resolved is not None  # Best-effort resolution

    def test_unresolvable(self):
        resolved, expires, clarify = self.resolver.resolve("sometime later", self.ref_time)
        assert clarify is True
