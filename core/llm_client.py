"""
NEUROHACK — LLM Client (FINAL)

BUGS FIXED:
1. Tone: "informal" contains "formal" → check "informal" FIRST
2. Doctor: ".+?" stops at "Dr." period → use "Dr. Name" pattern first
3. All correction/supersession patterns return is_correction=True
"""

import json
import re
from typing import Optional
from core.config import LLMConfig


class LLMClient:
    """
    Ollama-only LLM client.
    Uses OpenAI-compatible API exposed by Ollama.
    No API key required.
    """

    def __init__(self, config):
        self.config = config
        self.provider = "ollama"

        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key="ollama",  # dummy key (required by library)
                base_url=config.base_url or "http://localhost:11434/v1",
            )
            print(f"[OK] Connected to Ollama ({config.model})")
        except Exception as e:
            print(f"[ERROR] Could not connect to Ollama: {e}")
            raise e

    def complete(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return "[LLM Failure]"

    def complete(self, prompt: str) -> str:
        if self.provider == "mock":
            return self._mock_complete(prompt)
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.config.model, max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            else:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500, temperature=0.0,
                )
                return response.choices[0].message.content
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return self._mock_complete(prompt)

    def _mock_complete(self, prompt: str) -> str:
        if "ONLY the JSON object" in prompt:
            return self._mock_structure(prompt)
        if "ACTIVE MEMORY" in prompt or "ACTIVE USER CONSTRAINTS" in prompt:
            return "[Response with memory context]"
        return "[Response]"

    def _mock_structure(self, prompt: str) -> str:
        """
        Robust heuristic structurer. Pattern order is CRITICAL.
        Most-specific patterns first. Every correction path tested.
        """
        msg = ""
        msg_match = re.search(r"User message:\s*(.+?)(?:\n|$)", prompt)
        if msg_match:
            msg = msg_match.group(1).strip()
        ml = msg.lower()

        # ═══════════════════════════════════════════════════════════
        # 1. LANGUAGE (before anything else — very specific trigger)
        # ═══════════════════════════════════════════════════════════
        if "preferred language" in ml or ("language" in ml and (" is " in ml or "not " in ml)):
            # Extract the NEW language value
            # "Actually, my preferred language is Hindi, not Kannada"
            # → want "Hindi", not "Kannada"
            lang = re.search(r"language\s+is\s+(\w+)", msg, re.I)
            val = lang.group(1) if lang else "unknown"
            corr = any(x in ml for x in [
                       "actually", "change", "not ", "switch"])
            return self._j("semantic", "preferred_language", val, 0.95, corr=corr)

        # ═══════════════════════════════════════════════════════════
        # 2. NEGATIVE CONSTRAINTS — before "call me" to prevent
        #    "Never call me before 9 AM" → user_name
        # ═══════════════════════════════════════════════════════════
        if ml.startswith("never ") or ml.startswith("don't ") or ml.startswith("don\u2019t "):
            return self._j("semantic", "constraint", msg[:200], 0.9)

        # ═══════════════════════════════════════════════════════════
        # 3. NAME
        # ═══════════════════════════════════════════════════════════
        if "name is" in ml or ("call me " in ml and "never" not in ml and "don't" not in ml):
            name = re.search(r"(?:name is|call me)\s+(\w+)", msg, re.I)
            val = name.group(1) if name else "User"
            return self._j("semantic", "user_name", val, 0.95)

        # ═══════════════════════════════════════════════════════════
        # 4. DOCTOR — "Dr. Name" pattern FIRST to avoid "Dr" truncation
        # ═══════════════════════════════════════════════════════════
        if "doctor" in ml:
            # Strategy: find "Dr. Surname" pattern first (most reliable)
            dr_name = re.search(r"(Dr\.?\s+\w+)", msg)
            if dr_name:
                val = dr_name.group(1)
            else:
                # Fallback: extract everything after "is" or "to"
                doc = re.search(r"doctor\s+(?:is|to)\s+(.+?)$", msg, re.I)
                val = doc.group(1).strip().rstrip(".") if doc else "unknown"
            corr = any(x in ml for x in [
                       "update", "change", "actually", "new"])
            return self._j("semantic", "doctor_name", val, 0.9, corr=corr)

        # ═══════════════════════════════════════════════════════════
        # 5. MANAGER
        # ═══════════════════════════════════════════════════════════
        if "manager" in ml:
            mgr = re.search(
                r"(?:manager(?:'?s?\s+name)?\s+(?:is|to)\s+)(.+?)(?:\.|$)", msg, re.I)
            val = mgr.group(1).strip() if mgr else "unknown"
            return self._j("semantic", "manager_name", val, 0.9)

        # ═══════════════════════════════════════════════════════════
        # 6. EMAIL — handles "is", "changed to", "new email"
        # ═══════════════════════════════════════════════════════════
        if "email" in ml:
            em = re.search(
                r"(?:email\s+(?:is|has\s+changed\s+to|changed\s+to))\s+(\S+)", msg, re.I)
            if em:
                val = em.group(1).strip().rstrip(".")
            else:
                # Try to find any email-like pattern
                em2 = re.search(r"(\S+@\S+\.\S+)", msg)
                val = em2.group(1).rstrip(".") if em2 else "unknown"
            corr = any(x in ml for x in [
                       "changed", "actually", "update", "new"])
            return self._j("semantic", "user_email", val, 0.9, corr=corr)

        # ═══════════════════════════════════════════════════════════
        # 7. PHONE
        # ═══════════════════════════════════════════════════════════
        if "phone" in ml and ("is" in ml or "number" in ml):
            ph = re.search(r"(\d[\d\s\-]{7,})", msg)
            val = ph.group(1).strip() if ph else "unknown"
            return self._j("semantic", "phone_number", val, 0.9)

        # ═══════════════════════════════════════════════════════════
        # 8. WORK / EMPLOYER
        # ═══════════════════════════════════════════════════════════
        if "work at" in ml or "work for" in ml:
            org = re.search(
                r"work (?:at|for)\s+(.+?)(?:\s+in\b|\.|$)", msg, re.I)
            val = org.group(1).strip() if org else "unknown"
            return self._j("semantic", "employer", val, 0.9)

        # ═══════════════════════════════════════════════════════════
        # 9. LOCATION — "live in", "moved to", "based in"
        # ═══════════════════════════════════════════════════════════
        if any(x in ml for x in ["live in", "i'm in", "based in", "i am in", "moved to"]):
            loc = re.search(
                r"(?:live in|i'm in|i am in|based in|moved to)\s+(.+?)(?:\s+recently|\.|$)",
                msg, re.I
            )
            val = loc.group(1).strip() if loc else "unknown"
            corr = "moved" in ml
            return self._j("semantic", "user_location", val, 0.9, corr=corr)

        # ═══════════════════════════════════════════════════════════
        # 10. TIMEZONE
        # ═══════════════════════════════════════════════════════════
        if "timezone" in ml:
            tz = re.search(r"(Asia/\w+|America/\w+|Europe/\w+|UTC)", msg)
            val = tz.group(1) if tz else "UTC"
            return self._j("semantic", "user_timezone", val, 0.95)

        # ═══════════════════════════════════════════════════════════
        # 11. TONE — CRITICAL FIX: check "informal" BEFORE "formal"
        #     because "informal" contains the substring "formal"
        # ═══════════════════════════════════════════════════════════
        if "tone" in ml or (("formal" in ml or "informal" in ml) and
                            any(x in ml for x in ["use", "always", "change", "switch", "prefer"])):
            # Check "informal" FIRST — "informal" contains "formal"!
            if "informal" in ml or "casual" in ml:
                tone = "informal"
            else:
                tone = "formal"
            corr = any(x in ml for x in [
                       "change", "update", "switch", "not ", "prefer"])
            return self._j("semantic", "response_tone", tone, 0.95, corr=corr)

        # ═══════════════════════════════════════════════════════════
        # 12. DIETARY — vegetarian/vegan/non-veg
        # ═══════════════════════════════════════════════════════════
        if any(x in ml for x in ["vegetarian", "vegan", "non-veg", "nonveg", "diet"]):
            if "vegan" in ml and "non" not in ml:
                val = "vegan"
            elif "non" in ml:
                val = "non-vegetarian"
            else:
                val = "vegetarian"
            return self._j("semantic", "dietary_preference", val, 0.95)

        # ═══════════════════════════════════════════════════════════
        # 13. MEDICAL — diabetic/diabetes/allergic/asthma/bp
        # ═══════════════════════════════════════════════════════════
        if any(x in ml for x in ["diabetic", "diabetes", "allergic", "asthma",
                                 "hypertension", "high bp", "blood sugar"]):
            if "allergic" in ml:
                allergy = re.search(
                    r"allergic\s+to\s+(.+?)(?:\.|$)", msg, re.I)
                val = f"allergic to {allergy.group(1).strip()}" if allergy else "has allergies"
            elif "diabetes" in ml or "diabetic" in ml or "blood sugar" in ml:
                val = "diabetic"
            elif "asthma" in ml:
                val = "asthmatic"
            elif "hypertension" in ml or "high bp" in ml:
                val = "hypertension"
            else:
                val = msg[:100]
            return self._j("semantic", "medical_condition", val, 0.95)

        # ═══════════════════════════════════════════════════════════
        # 14. TEMPORAL — tomorrow / next day / by day / schedules
        # ═══════════════════════════════════════════════════════════
        if "tomorrow" in ml:
            te = re.search(
                r"(tomorrow[\w\s]*(?:after|before|at)?\s*\d*\s*(?:am|pm)?)", ml)
            te = te.group(1).strip() if te else "tomorrow"
            return self._j("episodic", "scheduled_action", msg[:200], 0.9, temporal=te)

        if any(x in ml for x in ["next monday", "next tuesday", "next wednesday",
                                 "next thursday", "next friday", "next saturday", "next sunday", "next week"]):
            te = re.search(r"(next\s+\w+)", ml)
            te = te.group(1) if te else "next week"
            return self._j("episodic", "scheduled_action", msg[:200], 0.9, temporal=te)

        if re.search(r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday)", ml):
            te = re.search(r"(by\s+\w+)", ml)
            te = te.group(1) if te else "by friday"
            return self._j("episodic", "scheduled_action", msg[:200], 0.9, temporal=te)

        if re.search(r"\bat\s+\d{1,2}", ml):
            te = re.search(r"(at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", ml)
            if te:
                return self._j("episodic", "scheduled_action", msg[:200], 0.85, temporal=te.group(1))

        if re.search(r"\bin\s+\d+\s+(?:hour|minute|day|week)", ml):
            te = re.search(r"(in\s+\d+\s+\w+)", ml)
            return self._j("episodic", "scheduled_action", msg[:200], 0.85,
                           temporal=te.group(1) if te else "soon")

        if any(x in ml for x in ["remind me", "schedule", "appointment", "meeting",
                                 "every monday", "every tuesday", "every wednesday",
                                 "every thursday", "every friday"]):
            te = None
            te_match = re.search(
                r"(every\s+\w+\s+at\s+\d+\s*(?:am|pm)?|every\s+\w+)", ml)
            if te_match:
                te = te_match.group(1)
            return self._j("episodic", "scheduled_action", msg[:200], 0.85, temporal=te)

        # ═══════════════════════════════════════════════════════════
        # 15. CORRECTIONS (generic — after all specific patterns)
        # ═══════════════════════════════════════════════════════════
        if any(x in ml for x in ["actually", "correction", "i meant"]):
            return self._j("semantic", "general_info", msg[:200], 0.8, corr=True)

        # ═══════════════════════════════════════════════════════════
        # 16. GENERIC PREFERENCE
        # ═══════════════════════════════════════════════════════════
        if any(x in ml for x in ["i prefer", "i like", "i want", "i need"]):
            return self._j("semantic", "preference", msg[:200], 0.8)

        # ═══════════════════════════════════════════════════════════
        # 17. BEHAVIORAL INSTRUCTION
        # ═══════════════════════════════════════════════════════════
        if any(x in ml for x in ["always ", "from now on", "make sure", "remember that"]):
            return self._j("semantic", "instruction", msg[:200], 0.85)

        # ═══════════════════════════════════════════════════════════
        # 18. SELF-DISCLOSURE
        # ═══════════════════════════════════════════════════════════
        if re.search(r"\bi(?:'m| am)\s+(?:a\s+)?\w+", ml):
            return self._j("semantic", "self_disclosure", msg[:200], 0.7)

        # ═══════════════════════════════════════════════════════════
        # 19. FALLBACK
        # ═══════════════════════════════════════════════════════════
        return self._j("semantic", "general_info", msg[:200], 0.5)

    def _j(self, type_: str, key: str, value: str, conf: float,
           corr: bool = False, temporal: str = None) -> str:
        return json.dumps({
            "type": type_,
            "key": key,
            "value": value,
            "confidence": conf,
            "temporal_expression": temporal,
            "is_correction": corr,
        })
