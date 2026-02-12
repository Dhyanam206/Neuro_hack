"""
NEUROHACK — Deterministic Rule Gate (Section 3 of Framework)

FIX APPLIED: Questions containing memory triggers now pass through.
The old blanket exclusion was blocking "Can you call me tomorrow?" which
is the PS's flagship example.

INVARIANT: Same input → same output, every time. No LLM involved.
"""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class GateResult:
    fired: bool
    matched_rules: List[str] = field(default_factory=list)
    extracted_fragments: List[str] = field(default_factory=list)


@dataclass
class ExtractionRule:
    rule_id: str
    description: str
    memory_type: str
    patterns: List[re.Pattern]


# ─── Compile all patterns at module load ──────────────────────────

EXTRACTION_RULES: List[ExtractionRule] = [

    # ── Category 1: Explicit Preference ──────────────────────────
    ExtractionRule(
        rule_id="PREF_001",
        description="First-person preference statement",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bi\s+prefer\b", re.IGNORECASE),
            re.compile(r"\bi\s+like\b(?!\s+to\s+know)", re.IGNORECASE),
            re.compile(r"\bi\s+want\b", re.IGNORECASE),
            re.compile(r"\bi\s+need\b", re.IGNORECASE),
            re.compile(r"\bmy\s+preferred\b", re.IGNORECASE),
            re.compile(r"\bmy\s+preference\b", re.IGNORECASE),
            re.compile(r"\bprefer\s+dark\s+mode\b", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="PREF_002",
        description="Negative preference (don't/never/avoid)",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bdon'?t\s+(?:ever\s+)?(?:call|use|send|contact|schedule)", re.IGNORECASE),
            re.compile(r"\bnever\s+(?:call|use|send|contact|schedule)", re.IGNORECASE),
            re.compile(r"\bavoid\s+(?:calling|using|sending)", re.IGNORECASE),
            re.compile(r"\bi\s+don'?t\s+eat\b", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="PREF_003",
        description="Behavioral instruction (always/from now on)",
        memory_type="semantic",
        patterns=[
            re.compile(r"\balways\s+(?:use|respond|speak|write|call|send)", re.IGNORECASE),
            re.compile(r"\bfrom\s+now\s+on\b", re.IGNORECASE),
            re.compile(r"\bmake\s+sure\s+to\b", re.IGNORECASE),
            re.compile(r"\bkeep\s+in\s+mind\b", re.IGNORECASE),
            re.compile(r"\bremember\s+that\b", re.IGNORECASE),
        ]
    ),

    # ── Category 2: Temporal Commitment ──────────────────────────
    ExtractionRule(
        rule_id="TEMP_001",
        description="Temporal commitment with day reference",
        memory_type="episodic",
        patterns=[
            re.compile(r"\btomorrow\b", re.IGNORECASE),
            re.compile(r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)", re.IGNORECASE),
            re.compile(r"\bthis\s+(?:evening|afternoon|weekend)", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="TEMP_002",
        description="Temporal commitment with time reference",
        memory_type="episodic",
        patterns=[
            re.compile(r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)", re.IGNORECASE),
            re.compile(r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2})", re.IGNORECASE),
            re.compile(r"\bbefore\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?", re.IGNORECASE),
            re.compile(r"\bafter\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?", re.IGNORECASE),
            re.compile(r"\bevery\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="TEMP_003",
        description="Duration-based or scheduling commitment",
        memory_type="episodic",
        patterns=[
            re.compile(r"\bin\s+\d+\s+(?:hour|minute|day|week)s?\b", re.IGNORECASE),
            re.compile(r"\bremind\s+me\b", re.IGNORECASE),
            re.compile(r"\bschedule\b", re.IGNORECASE),
            re.compile(r"\bappointment\b", re.IGNORECASE),
            re.compile(r"\bmeeting\b", re.IGNORECASE),
            re.compile(r"\bdeadline\b", re.IGNORECASE),
        ]
    ),

    # ── Category 3: Named Entity with Relation ──────────────────
    ExtractionRule(
        rule_id="ENT_001",
        description="Named entity relation (my X is Y)",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bmy\s+(?:doctor|lawyer|manager|boss|wife|husband|partner|friend|assistant|accountant|therapist)(?:'?s?\s+name)?\s+is\b", re.IGNORECASE),
            re.compile(r"\bmy\s+(?:name|email|phone|number|address)\s+is\b", re.IGNORECASE),
            re.compile(r"\bmy\s+(?:company|employer)\s+is\b", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="ENT_002",
        description="Organizational relation",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bi\s+work\s+(?:at|for)\b", re.IGNORECASE),
            re.compile(r"\bi'?m\s+an?\s+employee\s+(?:at|of)\b", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="ENT_003",
        description="Location relation",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bi\s+(?:live|am|stay)\s+in\b", re.IGNORECASE),
            re.compile(r"\bi'?m\s+(?:in|from|based\s+in)\b", re.IGNORECASE),
            re.compile(r"\bi\s+moved\s+to\b", re.IGNORECASE),
        ]
    ),

    # ── Category 4: Factual Self-Disclosure ──────────────────────
    ExtractionRule(
        rule_id="FACT_001",
        description="Self-disclosure (I am/have attribute)",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bi\s+(?:am|have|suffer\s+from)\s+(?:a\s+)?(?:diabetic|vegetarian|vegan|allergic|pregnant|retired)", re.IGNORECASE),
            re.compile(r"\bi'?m\s+(?:a\s+)?(?:diabetic|vegetarian|vegan|allergic|pregnant|retired|student|developer|engineer|teacher|doctor)", re.IGNORECASE),
            re.compile(r"\bi\s+have\s+(?:diabetes|asthma|high\s+bp|hypertension|type\s*\d)", re.IGNORECASE),
            re.compile(r"\bi\s+(?:eat|don'?t\s+eat)\s+(?:veg|non-?veg|meat|fish|eggs)", re.IGNORECASE),
            re.compile(r"\bmy\s+diet\b", re.IGNORECASE),
        ]
    ),

    ExtractionRule(
        rule_id="FACT_002",
        description="Identity fact (name, age, title)",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bmy\s+name\s+is\b", re.IGNORECASE),
            re.compile(r"\bi'?m\s+\d{1,3}\s+years?\s+old\b", re.IGNORECASE),
            re.compile(r"\bcall\s+me\s+\w+", re.IGNORECASE),
            re.compile(r"\bmy\s+phone\s+(?:number\s+)?is\b", re.IGNORECASE),
        ]
    ),

    # ── Category 5: Explicit Correction ──────────────────────────
    ExtractionRule(
        rule_id="CORR_001",
        description="Correction of prior information",
        memory_type="semantic",
        patterns=[
            re.compile(r"\bactually\b.*\bis\b", re.IGNORECASE),
            re.compile(r"\bi\s+meant\b", re.IGNORECASE),
            re.compile(r"\bcorrection\s*:", re.IGNORECASE),
            re.compile(r"\bno,?\s+it'?s\b", re.IGNORECASE),
            re.compile(r"\bchange\s+(?:my|the)\b", re.IGNORECASE),
            re.compile(r"\bupdate\s+my\b", re.IGNORECASE),
            re.compile(r"\bhas\s+changed\s+to\b", re.IGNORECASE),
            re.compile(r"\bi\s+moved\s+to\b", re.IGNORECASE),
        ]
    ),
]


# ─── Exclusion Patterns ──────────────────────────────────────────
# Simple acknowledgments and greetings — NEVER store these.

EXCLUSION_PATTERNS: List[re.Pattern] = [
    re.compile(r"^(?:ok|okay|sure|yes|no|yeah|nah|thanks|thank you|got it|go ahead|do it|fine|great|cool|alright|hmm|hm)[\.\!\?]?$", re.IGNORECASE),
    re.compile(r"^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening)|bye|goodbye)[\.\!\?]?$", re.IGNORECASE),
]

# ─── CRITICAL FIX: Questions with memory triggers ────────────────
# Old code had a blanket "block all questions" exclusion.
# This broke "Can you call me tomorrow?" — the PS's example.
#
# New approach: questions are excluded ONLY if they don't contain
# any memory-worthy triggers.

QUESTION_PATTERN = re.compile(
    r"^(?:what|how|why|when|where|who|can you|could you|would you|will you|do you)\b.*\?$",
    re.IGNORECASE,
)

MEMORY_TRIGGERS_IN_QUESTIONS = re.compile(
    r"\b(tomorrow|next\s+\w+|today|at\s+\d|by\s+\w+day|before\s+\d|after\s+\d|"
    r"remind|schedule|appointment|meeting|call\s+me|"
    r"my\s+name\s+is|i\s+am|i'm|i\s+have|i\s+work\s+at|i\s+work\s+for|"
    r"preferred|from\s+now\s+on|always|never)\b",
    re.IGNORECASE,
)


# ─── Gate Function ────────────────────────────────────────────────

def evaluate_gate(message: str) -> GateResult:
    """
    Evaluate a user message against the extraction rule catalog.
    This is a PURE FUNCTION. No side effects. No LLM calls.
    """
    message = message.strip()

    # Step 1: Check simple exclusions (ok, thanks, hi, etc.)
    for pattern in EXCLUSION_PATTERNS:
        if pattern.match(message):
            return GateResult(fired=False)

    # Step 2: Check question exclusion — BUT allow questions with triggers
    if QUESTION_PATTERN.match(message):
        if not MEMORY_TRIGGERS_IN_QUESTIONS.search(message):
            return GateResult(fired=False)

    # Step 3: Check each extraction rule
    matched_rules: List[str] = []
    fragments: List[str] = []

    for rule in EXTRACTION_RULES:
        for pattern in rule.patterns:
            match = pattern.search(message)
            if match:
                matched_rules.append(rule.rule_id)
                fragments.append(message)
                break

    # Step 4: Gate fires if at least one rule matched
    if matched_rules:
        return GateResult(
            fired=True,
            matched_rules=matched_rules,
            extracted_fragments=fragments
        )

    return GateResult(fired=False)
