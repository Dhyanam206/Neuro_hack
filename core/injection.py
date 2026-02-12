"""
NEUROHACK — Memory Injection (Section 7 of Framework)

Converts retrieved memories into behavioral directives for the LLM prompt.
Memories are injected as INSTRUCTIONS, not as conversation history.

INVARIANT: Memories are injected as behavioral directives, not as conversation
           history. The model never sees raw past conversation text.
"""

from typing import List, Dict, Any
from dataclasses import dataclass

from core.models import Memory, MemoryType
from core.retrieval import RetrievalResult


@dataclass
class InjectionBlock:
    """The formatted memory block ready for prompt insertion."""
    tier_1: str         # Always-inject constraints
    tier_2: str         # Intent-matched contextual
    tier_3: str         # Vector fallback
    total_tokens: int   # Approximate token count
    memory_ids: List[str]  # IDs of injected memories (for audit)


# ─── Directive Templates ─────────────────────────────────────────

DIRECTIVE_TEMPLATES: Dict[str, str] = {
    "preferred_language": "User's preferred language is {value}. Respond in {value} unless user explicitly requests otherwise.",
    "response_tone": "User has instructed: use {value} tone. Apply this to all responses.",
    "user_name": "User's name is {value}. Use it naturally when appropriate.",
    "user_timezone": "User is in timezone {value}. Use this for all time references.",
    "user_location": "User is located in {value}.",
    "call_time": "User prefers calls {value}. Respect this in scheduling discussions.",
    "doctor_name": "User's doctor is {value}.",
    "medical_condition": "User has disclosed: {value}. Be sensitive and relevant.",
    "user_email": "User's email is {value}.",
    "dietary_preference": "User's dietary preference: {value}. Respect in food/restaurant suggestions.",
    "employer": "User works at {value}.",
    "constraint": "User constraint: {value}. Always respect this.",
    "manager_name": "User's manager is {value}.",
    "phone_number": "User's phone number is {value}.",
    "scheduled_action": "Active commitment: {value}.",
    # Default fallback
    "_default_semantic": "User information: {key} is {value}.",
    "_default_episodic": "Active commitment: {value} (expires {expires_at}). Respect this in relevant discussions.",
}


class MemoryInjector:
    """
    Formats retrieved memories into a tiered injection block.
    Enforces hard token caps per tier.
    """

    def __init__(self, config: Dict[str, Any]):
        self.tier_1_cap = config.get("tier_1", 300)
        self.tier_2_cap = config.get("tier_2", 300)
        self.tier_3_cap = config.get("tier_3", 200)
        self.total_cap = config.get("total", 800)

    def build_injection(
        self,
        always_inject: List[Memory],
        intent_matched: List[RetrievalResult],
        vector_fallback: List[RetrievalResult] = None,
    ) -> InjectionBlock:
        """
        Build the tiered injection block with hard token caps.
        
        Args:
            always_inject: Tier 1 memories (constraints, preferences)
            intent_matched: Tier 2 memories (retrieval levels 1-3)
            vector_fallback: Tier 3 memories (retrieval level 4)
        """
        memory_ids = []

        # ── Tier 1: Always-Inject ────────────────────────────────
        tier_1_directives = []
        tier_1_tokens = 0
        for mem in always_inject:
            directive = self._format_directive(mem)
            tokens = self._estimate_tokens(directive)
            if tier_1_tokens + tokens <= self.tier_1_cap:
                tier_1_directives.append(directive)
                tier_1_tokens += tokens
                memory_ids.append(mem.memory_id)

        # ── Tier 2: Intent-Matched ───────────────────────────────
        tier_2_directives = []
        tier_2_tokens = 0
        for result in intent_matched:
            # Skip if already in Tier 1
            if result.memory.memory_id in memory_ids:
                continue
            directive = self._format_directive(result.memory)
            tokens = self._estimate_tokens(directive)
            if tier_2_tokens + tokens <= self.tier_2_cap:
                tier_2_directives.append(directive)
                tier_2_tokens += tokens
                memory_ids.append(result.memory.memory_id)

        # ── Tier 3: Vector Fallback ──────────────────────────────
        tier_3_directives = []
        tier_3_tokens = 0
        if vector_fallback:
            for result in vector_fallback:
                if result.memory.memory_id in memory_ids:
                    continue
                directive = self._format_directive(result.memory)
                tokens = self._estimate_tokens(directive)
                if tier_3_tokens + tokens <= self.tier_3_cap:
                    tier_3_directives.append(directive)
                    tier_3_tokens += tokens
                    memory_ids.append(result.memory.memory_id)

        total_tokens = tier_1_tokens + tier_2_tokens + tier_3_tokens

        return InjectionBlock(
            tier_1="\n".join(tier_1_directives) if tier_1_directives else "",
            tier_2="\n".join(tier_2_directives) if tier_2_directives else "",
            tier_3="\n".join(tier_3_directives) if tier_3_directives else "",
            total_tokens=total_tokens,
            memory_ids=memory_ids,
        )

    def format_prompt_block(self, block: InjectionBlock) -> str:
        """Format the injection block into the system prompt section."""
        sections = []
        if block.tier_1:
            sections.append(f"[ACTIVE USER CONSTRAINTS]\n{block.tier_1}")
        if block.tier_2:
            sections.append(f"[CONTEXTUAL MEMORY]\n{block.tier_2}")
        if block.tier_3:
            sections.append(f"[ADDITIONAL CONTEXT]\n{block.tier_3}")

        if not sections:
            return ""

        return "\n\n".join(sections)

    def _format_directive(self, memory: Memory) -> str:
        """Convert a memory record to a behavioral directive string."""
        template = DIRECTIVE_TEMPLATES.get(memory.key)
        if template:
            return template.format(
                value=memory.value,
                key=memory.key,
                expires_at=memory.expires_at.isoformat() if memory.expires_at else "N/A"
            )

        # Fallback templates
        if memory.type == MemoryType.SEMANTIC:
            return DIRECTIVE_TEMPLATES["_default_semantic"].format(
                key=memory.key.replace("_", " "), value=memory.value
            )
        else:
            return DIRECTIVE_TEMPLATES["_default_episodic"].format(
                value=memory.value,
                expires_at=memory.expires_at.isoformat() if memory.expires_at else "N/A"
            )

    def _estimate_tokens(self, text: str) -> int:
        """Approximate token count. ~4 chars per token for English."""
        return max(1, len(text) // 4)
