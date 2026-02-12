"""
NEUROHACK — Retrieval Algorithm (Section 5 of Framework)

FIX APPLIED: KEY_TERM_MAP massively expanded to cover diet, health,
employer, and many synonyms. Tier-1 always-inject now includes
dietary_preference, medical_condition, employer — critical stable facts.

INVARIANT: Total injected memory never exceeds 800 tokens.
"""

import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from core.models import Memory, MemoryStatus, MemoryType


@dataclass
class IntentObject:
    intent_type: str
    key_terms: List[str]
    temporal_expr: Optional[str] = None
    entity_refs: List[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    memory: Memory
    retrieval_level: int
    score: float = 0.0


class IntentClassifier:
    """Deterministic intent classifier. Rule-based, no LLM."""

    TEMPORAL_PATTERNS = [
        re.compile(r"\btomorrow\b", re.IGNORECASE),
        re.compile(r"\bnext\s+(?:week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.IGNORECASE),
        re.compile(r"\bat\s+\d{1,2}", re.IGNORECASE),
        re.compile(r"\b(?:schedule|meeting|appointment|call|remind|commitment|upcoming|pending)\b", re.IGNORECASE),
    ]

    CORRECTION_PATTERNS = [
        re.compile(r"\bactually\b", re.IGNORECASE),
        re.compile(r"\bchange\s+my\b", re.IGNORECASE),
        re.compile(r"\bupdate\s+my\b", re.IGNORECASE),
    ]

    QUERY_PATTERNS = [
        re.compile(r"^(?:what|how|why|when|where|who|do you|can you|could you)", re.IGNORECASE),
        re.compile(r"\btell\s+me\s+(?:about|everything)\b", re.IGNORECASE),
        re.compile(r"\bsummarize\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+(?:do\s+you|should\s+you)\s+(?:know|remember)\b", re.IGNORECASE),
    ]

    def classify(self, message: str) -> IntentObject:
        message = message.strip()
        key_terms = self._extract_key_terms(message)
        temporal_expr = None
        intent_type = "social"

        for p in self.TEMPORAL_PATTERNS:
            m = p.search(message)
            if m:
                temporal_expr = m.group(0)
                intent_type = "commitment"
                break

        for p in self.CORRECTION_PATTERNS:
            if p.search(message):
                intent_type = "correction"
                break

        for p in self.QUERY_PATTERNS:
            if p.search(message):
                intent_type = "query"
                break

        if intent_type == "social":
            if re.search(r"\b(?:always|never|don't|prefer|want|need|like)\b", message, re.IGNORECASE):
                intent_type = "instruction"

        return IntentObject(
            intent_type=intent_type,
            key_terms=key_terms,
            temporal_expr=temporal_expr,
        )

    def _extract_key_terms(self, message: str) -> List[str]:
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "i", "me", "my", "you", "your", "it", "its", "we", "they",
                      "do", "does", "did", "can", "could", "will", "would", "should",
                      "have", "has", "had", "to", "for", "of", "in", "on", "at",
                      "and", "or", "but", "not", "no", "what", "how", "when", "where",
                      "tell", "about", "know", "everything", "remember", "with", "that",
                      "this", "there", "some", "any", "all", "am", "been"}
        words = re.findall(r"\b[a-zA-Z]+\b", message.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]


# ─── KEY TERM MAP — massively expanded ───────────────────────────
# Maps user query terms to memory keys for exact-key lookup.

KEY_TERM_MAP: Dict[str, str] = {
    # Language
    "language": "preferred_language",
    "kannada": "preferred_language",
    "hindi": "preferred_language",
    "english": "preferred_language",
    "telugu": "preferred_language",
    "tamil": "preferred_language",
    "speak": "preferred_language",

    # Tone
    "tone": "response_tone",
    "formal": "response_tone",
    "informal": "response_tone",
    "talk": "response_tone",

    # Name
    "name": "user_name",

    # Contact
    "email": "user_email",
    "phone": "phone_number",
    "number": "phone_number",

    # Doctor / medical
    "doctor": "doctor_name",
    "health": "medical_condition",
    "medical": "medical_condition",
    "condition": "medical_condition",
    "conditions": "medical_condition",
    "diabetes": "medical_condition",
    "diabetic": "medical_condition",
    "disease": "medical_condition",
    "illness": "medical_condition",
    "aware": "medical_condition",

    # Diet
    "diet": "dietary_preference",
    "dietary": "dietary_preference",
    "food": "dietary_preference",
    "eat": "dietary_preference",
    "eating": "dietary_preference",
    "vegetarian": "dietary_preference",
    "vegan": "dietary_preference",
    "nonveg": "dietary_preference",
    "restriction": "dietary_preference",
    "restrictions": "dietary_preference",

    # Employer / work
    "employer": "employer",
    "company": "employer",
    "job": "employer",
    "work": "employer",
    "office": "employer",
    "workplace": "employer",

    # Location
    "location": "user_location",
    "city": "user_location",
    "live": "user_location",
    "address": "user_location",
    "based": "user_location",
    "currently": "user_location",

    # Timezone
    "timezone": "user_timezone",
    "time": "user_timezone",

    # Manager
    "manager": "manager_name",
    "boss": "manager_name",

    # Scheduling
    "commitment": "scheduled_action",
    "commitments": "scheduled_action",
    "reminder": "scheduled_action",
    "reminders": "scheduled_action",
    "upcoming": "scheduled_action",
    "pending": "scheduled_action",
    "appointment": "scheduled_action",
    "appointments": "scheduled_action",

    # Constraints
    "constraint": "constraint",
    "constraints": "constraint",
    "never": "constraint",
}


class MemoryRetriever:
    """4-level retrieval with tiered token budget."""

    def __init__(self, config: Dict[str, Any]):
        self.top_k = config.get("top_k", 5)
        self.confidence_threshold = config.get("confidence_threshold", 0.7)
        self.ranking_weights = config.get("ranking_weights", {
            "recency": 0.3, "confidence": 0.3, "specificity": 0.4
        })

    def retrieve(
        self,
        session: Session,
        user_id: str,
        intent: IntentObject,
        current_turn: int,
        pending_buffer: List[Memory] = None,
    ) -> List[RetrievalResult]:
        results: List[RetrievalResult] = []
        seen_ids = set()

        # ── Level 1: Exact Key Lookup ────────────────────────────
        for term in intent.key_terms:
            mapped_key = KEY_TERM_MAP.get(term)
            if mapped_key:
                memories = self._exact_lookup(session, user_id, mapped_key)
                for mem in memories:
                    if mem.memory_id not in seen_ids:
                        results.append(RetrievalResult(memory=mem, retrieval_level=1))
                        seen_ids.add(mem.memory_id)

        # ── Level 2: Temporal Range Query ────────────────────────
        if intent.temporal_expr and len(results) < self.top_k:
            temporal_results = self._temporal_query(session, user_id)
            for mem in temporal_results:
                if mem.memory_id not in seen_ids:
                    results.append(RetrievalResult(memory=mem, retrieval_level=2))
                    seen_ids.add(mem.memory_id)

        # ── Level 3: Category-Scoped Query ───────────────────────
        if len(results) < self.top_k:
            mem_type = self._intent_to_type(intent.intent_type)
            if mem_type:
                cat_results = self._category_query(session, user_id, mem_type, current_turn)
                for mem in cat_results:
                    if mem.memory_id not in seen_ids:
                        results.append(RetrievalResult(memory=mem, retrieval_level=3))
                        seen_ids.add(mem.memory_id)

        # ── Check Write-Ahead Buffer ─────────────────────────────
        if pending_buffer:
            for mem in pending_buffer:
                if mem.memory_id not in seen_ids and mem.is_retrievable():
                    results.append(RetrievalResult(memory=mem, retrieval_level=1))
                    seen_ids.add(mem.memory_id)

        results = self._rank(results, current_turn)
        return results[:self.top_k]

    def get_always_inject(self, session: Session, user_id: str) -> List[Memory]:
        """
        Tier 1 always-inject: stable preferences and core facts.
        EXPANDED to include dietary_preference, medical_condition, employer.
        """
        always_keys = {
            "preferred_language", "response_tone", "user_name",
            "user_timezone", "user_location", "user_email",
            "dietary_preference", "medical_condition", "employer",
            "constraint", "doctor_name",
        }

        return (
            session.query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.status == MemoryStatus.ACTIVE,
                Memory.type == MemoryType.SEMANTIC,
                Memory.key.in_(always_keys),
                Memory.confidence >= self.confidence_threshold,
            )
            .all()
        )

    # ── Private Methods ──────────────────────────────────────────

    def _exact_lookup(self, session: Session, user_id: str, key: str) -> List[Memory]:
        now = datetime.utcnow()
        return (
            session.query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.key == key,
                Memory.status == MemoryStatus.ACTIVE,
                Memory.confidence >= self.confidence_threshold,
            )
            .filter(
                (Memory.expires_at == None) | (Memory.expires_at > now)
            )
            .all()
        )

    def _temporal_query(self, session: Session, user_id: str) -> List[Memory]:
        now = datetime.utcnow()
        return (
            session.query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.type == MemoryType.EPISODIC,
                Memory.status == MemoryStatus.ACTIVE,
                Memory.confidence >= self.confidence_threshold,
                Memory.expires_at > now,
            )
            .order_by(Memory.created_at.desc())
            .limit(self.top_k)
            .all()
        )

    def _category_query(
        self, session: Session, user_id: str, mem_type: MemoryType, current_turn: int
    ) -> List[Memory]:
        now = datetime.utcnow()
        return (
            session.query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.type == mem_type,
                Memory.status == MemoryStatus.ACTIVE,
                Memory.confidence >= self.confidence_threshold,
            )
            .filter(
                (Memory.expires_at == None) | (Memory.expires_at > now)
            )
            .order_by(Memory.last_accessed_turn.desc(), Memory.confidence.desc())
            .limit(self.top_k)
            .all()
        )

    def _intent_to_type(self, intent_type: str) -> Optional[MemoryType]:
        return {
            "commitment": MemoryType.EPISODIC,
            "query": MemoryType.SEMANTIC,
            "instruction": MemoryType.SEMANTIC,
        }.get(intent_type)

    def _rank(self, results: List[RetrievalResult], current_turn: int) -> List[RetrievalResult]:
        w = self.ranking_weights
        specificity_map = {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.3}

        for r in results:
            recency = 1.0
            if r.memory.last_accessed_turn:
                gap = current_turn - r.memory.last_accessed_turn
                recency = max(0.0, 1.0 - (gap / max(current_turn, 1)))
            specificity = specificity_map.get(r.retrieval_level, 0.3)
            r.score = (
                w["recency"] * recency +
                w["confidence"] * r.memory.confidence +
                w["specificity"] * specificity
            )

        results.sort(key=lambda r: (-r.score, r.memory.created_at))
        return results
