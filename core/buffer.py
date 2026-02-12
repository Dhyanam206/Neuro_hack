"""
NEUROHACK — Write-Ahead Buffer (Section 11.1 of Framework)

Bridges the latency gap between async memory writes and sync retrieval.
Retrieval checks DB ∪ buffer, ensuring turn N memory is visible at N+1.

Parameters: max capacity 10, TTL 2 turns, FIFO eviction.
Not persisted — DB is the source of truth.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from collections import deque

from core.models import Memory


@dataclass
class BufferEntry:
    """A pending memory write in the buffer."""
    memory: Memory
    inserted_at_turn: int


class WriteAheadBuffer:
    """
    In-memory FIFO queue for pending memory writes.
    
    The retrieval layer queries DB UNION this buffer on every call.
    """

    def __init__(self, max_capacity: int = 10, ttl_turns: int = 2):
        self.max_capacity = max_capacity
        self.ttl_turns = ttl_turns
        self._buffer: deque[BufferEntry] = deque(maxlen=max_capacity)

    def add(self, memory: Memory, current_turn: int):
        """Add a pending memory to the buffer."""
        self._buffer.append(BufferEntry(memory=memory, inserted_at_turn=current_turn))

    def get_pending(self, current_turn: int) -> List[Memory]:
        """
        Get all non-expired buffer entries.
        Evicts expired entries as a side effect.
        """
        self._evict(current_turn)
        return [entry.memory for entry in self._buffer]

    def _evict(self, current_turn: int):
        """Remove entries that have exceeded their TTL."""
        while self._buffer:
            oldest = self._buffer[0]
            if current_turn - oldest.inserted_at_turn > self.ttl_turns:
                self._buffer.popleft()
            else:
                break

    def clear(self):
        """Clear the buffer. Used for testing/reset."""
        self._buffer.clear()

    @property
    def size(self) -> int:
        return len(self._buffer)
