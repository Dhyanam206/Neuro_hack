"""
NEUROHACK — LLM Structurer (Section 3.2 of Framework)

FIX APPLIED: Deterministic post-processing guardrails.
If matched rule is ENT_001 + "doctor" in message, force key=doctor_name
and extract full name via regex if LLM output is too short (e.g. "Dr").

INVARIANT: LLM is invoked only for structuring, never for classification.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class StructuredMemory:
    type: str
    key: str
    value: str
    confidence: float
    temporal_expression: Optional[str] = None
    is_correction: bool = False


STRUCTURING_PROMPT = """You are a memory extraction engine. Your ONLY job is to convert
a user message into a structured memory record.

The message has already been classified as memory-worthy. Do NOT judge importance.
Extract the information into this exact JSON format:

{{
    "type": "semantic" or "episodic",
    "key": "lowercase_underscore_key (e.g. preferred_language, call_time, doctor_name)",
    "value": "concise factual value (max 500 chars, no raw conversation text)",
    "confidence": 0.0 to 1.0,
    "temporal_expression": "raw time expression if any, else null",
    "is_correction": true/false (true if user is correcting prior info)
}}

Rules:
- key must be normalized: lowercase, underscores, no spaces
- value must be factual and concise, not a quote of the message
- confidence: 1.0 = explicit clear statement, 0.7-0.9 = clear but needs context, <0.7 = ambiguous
- temporal_expression: extract the raw time phrase ("tomorrow after 11 AM") for separate resolution
- is_correction: true ONLY if the user explicitly corrects prior info ("actually", "no it's", "change my")

Matched rules: {matched_rules}
User message: {message}

Respond with ONLY the JSON object. No explanation. No markdown."""


# ─── Key Coercion Rules ──────────────────────────────────────────
# If a matched rule + message content clearly indicates a specific key,
# we force it to prevent LLM key drift.

KEY_COERCION = {
    "doctor": "doctor_name",
    "manager": "manager_name",
    "boss": "manager_name",
    "email": "user_email",
    "phone": "phone_number",
    "name is": "user_name",
    "language": "preferred_language",
    "tone": "response_tone",
    "vegetarian": "dietary_preference",
    "vegan": "dietary_preference",
    "diabetic": "medical_condition",
    "diabetes": "medical_condition",
    "allergic": "medical_condition",
    "work at": "employer",
    "work for": "employer",
    "live in": "user_location",
    "moved to": "user_location",
    "based in": "user_location",
    "timezone": "user_timezone",
}

# ─── Value Extraction Regexes ─────────────────────────────────────
# Used when LLM output value is too short or clearly truncated.

VALUE_EXTRACTORS = {
    "doctor_name": [
        re.compile(r"(?:doctor(?:'?s?\s+name)?\s+(?:is|to)\s+)(.+?)(?:\.|$)", re.I),
        re.compile(r"(Dr\.?\s+\w+(?:\s+\w+)?)", re.I),
    ],
    "manager_name": [
        re.compile(r"(?:manager(?:'?s?\s+name)?\s+(?:is|to)\s+)(.+?)(?:\.|$)", re.I),
    ],
    "user_name": [
        re.compile(r"(?:name is|call me)\s+(\w+(?:\s+\w+)?)", re.I),
    ],
    "employer": [
        re.compile(r"work (?:at|for)\s+(.+?)(?:\s+in\b|\.|$)", re.I),
    ],
    "user_location": [
        re.compile(r"(?:live in|i'm in|based in|moved to)\s+(.+?)(?:\s+recently|\.|$)", re.I),
    ],
}


class MemoryStructurer:

    def __init__(self, llm_client):
        self.llm = llm_client

    def structure(self, message: str, matched_rules: List[str]) -> Optional[StructuredMemory]:
        prompt = STRUCTURING_PROMPT.format(
            matched_rules=", ".join(matched_rules),
            message=message
        )

        try:
            raw_output = self.llm.complete(prompt)

            cleaned = raw_output.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)

            required = ["type", "key", "value", "confidence"]
            for field in required:
                if field not in parsed:
                    return None

            if parsed["type"] not in ("semantic", "episodic"):
                return None
            if not (0.0 <= parsed["confidence"] <= 1.0):
                return None
            if len(parsed["value"]) > 500:
                parsed["value"] = parsed["value"][:500]

            parsed["key"] = parsed["key"].lower().replace(" ", "_").strip("_")

            # ── GUARDRAIL: Key Coercion ──────────────────────────
            msg_lower = message.lower()
            for trigger, forced_key in KEY_COERCION.items():
                if trigger in msg_lower:
                    parsed["key"] = forced_key
                    break

            # ── GUARDRAIL: Value too short → regex extraction ────
            if len(parsed["value"]) <= 3 and parsed["key"] in VALUE_EXTRACTORS:
                for regex in VALUE_EXTRACTORS[parsed["key"]]:
                    m = regex.search(message)
                    if m:
                        parsed["value"] = m.group(1).strip().rstrip(".")
                        break

            return StructuredMemory(
                type=parsed["type"],
                key=parsed["key"],
                value=parsed["value"],
                confidence=parsed["confidence"],
                temporal_expression=parsed.get("temporal_expression"),
                is_correction=parsed.get("is_correction", False)
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
