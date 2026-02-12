"""
NEUROHACK — Temporal Anchoring (Section 4 of Framework)

All relative time expressions are resolved to absolute ISO 8601 timestamps
at WRITE TIME, never at read time. This prevents "tomorrow" at turn 1
from being misinterpreted at turn 500.

INVARIANT: No episodic memory whose expires_at is in the past will ever
           be injected into an inference prompt.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import re

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
import pytz


DAY_MAP = {
    "monday": MO, "tuesday": TU, "wednesday": WE, "thursday": TH,
    "friday": FR, "saturday": SA, "sunday": SU
}


class TemporalResolver:
    """
    Resolves relative temporal expressions to absolute timestamps.
    Requires a user timezone (IANA string). If unknown, flags for clarification.
    """

    def __init__(self, user_timezone: Optional[str] = None):
        self.tz = pytz.timezone(user_timezone) if user_timezone else pytz.utc
        self.timezone_known = user_timezone is not None

    def resolve(
        self, expression: str, reference_time: Optional[datetime] = None
    ) -> Tuple[Optional[datetime], Optional[datetime], bool]:
        """
        Resolve a temporal expression to (resolved_time, expires_at, needs_clarification).

        Args:
            expression: Raw temporal string (e.g., "tomorrow after 11 AM")
            reference_time: The wall-clock time at extraction (defaults to now)

        Returns:
            (resolved_time, expires_at, needs_clarification)
            If needs_clarification is True, resolved_time is best-effort UTC.
        """
        if reference_time is None:
            reference_time = datetime.now(self.tz)
        elif reference_time.tzinfo is None:
            reference_time = self.tz.localize(reference_time)

        expr_lower = expression.lower().strip()
        needs_clarification = False

        # ── "tomorrow" ───────────────────────────────────────────
        if "tomorrow" in expr_lower:
            base = reference_time + timedelta(days=1)
            time_part = self._extract_time(expr_lower)
            if time_part:
                resolved = base.replace(hour=time_part[0], minute=time_part[1], second=0)
            else:
                resolved = base.replace(hour=0, minute=0, second=0)
            expires_at = base.replace(hour=23, minute=59, second=59)
            return resolved, expires_at, needs_clarification

        # ── "next [day]" ─────────────────────────────────────────
        for day_name, day_const in DAY_MAP.items():
            if f"next {day_name}" in expr_lower:
                resolved = reference_time + relativedelta(weekday=day_const(+1))
                resolved = resolved.replace(hour=0, minute=0, second=0)
                time_part = self._extract_time(expr_lower)
                if time_part:
                    resolved = resolved.replace(hour=time_part[0], minute=time_part[1])
                expires_at = resolved.replace(hour=23, minute=59, second=59)
                return resolved, expires_at, needs_clarification

        # ── "in N hours/days/minutes" ────────────────────────────
        duration_match = re.search(r"in\s+(\d+)\s+(hour|minute|day|week)s?", expr_lower)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)
            delta = {
                "minute": timedelta(minutes=amount),
                "hour": timedelta(hours=amount),
                "day": timedelta(days=amount),
                "week": timedelta(weeks=amount),
            }.get(unit, timedelta(hours=amount))
            resolved = reference_time + delta
            expires_at = resolved + timedelta(hours=1)  # 1-hour buffer
            return resolved, expires_at, needs_clarification

        # ── "by [day]" ───────────────────────────────────────────
        by_day_match = re.search(r"by\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", expr_lower)
        if by_day_match:
            day_const = DAY_MAP[by_day_match.group(1)]
            resolved = reference_time + relativedelta(weekday=day_const(+1))
            expires_at = resolved.replace(hour=23, minute=59, second=59)
            return resolved, expires_at, needs_clarification

        # ── "at/after/before [time]" (no day → needs clarification) ──
        time_part = self._extract_time(expr_lower)
        if time_part and not any(w in expr_lower for w in ["tomorrow", "next", "today"]):
            # Time without day context — ambiguous
            resolved = reference_time.replace(hour=time_part[0], minute=time_part[1], second=0)
            if resolved < reference_time:
                resolved += timedelta(days=1)  # Assume next occurrence
            expires_at = resolved.replace(hour=23, minute=59, second=59)
            needs_clarification = not self.timezone_known
            return resolved, expires_at, needs_clarification

        # ── "today" ──────────────────────────────────────────────
        if "today" in expr_lower:
            time_part = self._extract_time(expr_lower)
            if time_part:
                resolved = reference_time.replace(hour=time_part[0], minute=time_part[1], second=0)
            else:
                resolved = reference_time
            expires_at = reference_time.replace(hour=23, minute=59, second=59)
            return resolved, expires_at, needs_clarification

        # ── Fallback: unresolvable ───────────────────────────────
        return None, None, True

    def _extract_time(self, text: str) -> Optional[Tuple[int, int]]:
        """Extract hour:minute from text. Returns (hour_24, minute) or None."""
        # Match "11 AM", "3:30 PM", "14:00"
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)", text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3).lower()
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            return (hour, minute)

        # 24-hour format
        time_24 = re.search(r"(\d{1,2}):(\d{2})(?!\s*(?:am|pm))", text)
        if time_24:
            return (int(time_24.group(1)), int(time_24.group(2)))

        # Bare number with "after/before/at"
        bare = re.search(r"(?:after|before|at)\s+(\d{1,2})(?!\d)", text)
        if bare:
            hour = int(bare.group(1))
            if hour <= 12:
                return (hour, 0)  # Ambiguous AM/PM, default to number as-is

        return None


class TemporalGarbageCollector:
    """
    Mechanically expires episodic memories whose expires_at has passed.
    
    Runs every N turns or M minutes. No LLM involved.
    Pure SQL operation: UPDATE ... SET status='expired' WHERE expires_at < NOW()
    """

    def __init__(self, interval_turns: int = 50, interval_minutes: int = 5):
        self.interval_turns = interval_turns
        self.interval_minutes = interval_minutes
        self._last_run_turn = 0
        self._last_run_time = datetime.now(timezone.utc)

    def should_run(self, current_turn: int) -> bool:
        """Check if GC should run based on turn count or time elapsed."""
        turns_elapsed = current_turn - self._last_run_turn
        time_elapsed = (datetime.now(timezone.utc) - self._last_run_time).total_seconds() / 60

        return turns_elapsed >= self.interval_turns or time_elapsed >= self.interval_minutes

    def run(self, session, current_turn: int) -> int:
        """
        Expire all overdue episodic memories. Returns count of expired records.
        
        SQL equivalent:
            UPDATE memories SET status='expired', updated_at=NOW()
            WHERE status='active' AND type='episodic' AND expires_at < NOW()
        """
        from core.models import Memory, MemoryStatus, MemoryType, AuditLog, AuditAction

        now = datetime.now(timezone.utc)

        expired_memories = (
            session.query(Memory)
            .filter(
                Memory.status == MemoryStatus.ACTIVE,
                Memory.type == MemoryType.EPISODIC,
                Memory.expires_at < now
            )
            .all()
        )

        for mem in expired_memories:
            old_status = mem.status
            mem.status = MemoryStatus.EXPIRED
            mem.updated_at = now

            # Audit log
            session.add(AuditLog(
                memory_id=mem.memory_id,
                action=AuditAction.EXPIRED,
                previous_status=old_status,
                new_status=MemoryStatus.EXPIRED,
                turn_number=current_turn
            ))

        session.commit()

        self._last_run_turn = current_turn
        self._last_run_time = now

        return len(expired_memories)
