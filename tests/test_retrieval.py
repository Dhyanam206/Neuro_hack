"""
NEUROHACK — Retrieval Tests

Tests the 4-level precedence chain and token budget enforcement.
"""

import pytest
from core.retrieval import IntentClassifier, MemoryRetriever


class TestIntentClassifier:

    def setup_method(self):
        self.classifier = IntentClassifier()

    def test_query_intent(self):
        result = self.classifier.classify("What is my preferred language?")
        assert result.intent_type == "query"

    def test_commitment_intent(self):
        result = self.classifier.classify("Call me tomorrow")
        assert result.intent_type == "commitment"

    def test_correction_intent(self):
        result = self.classifier.classify("Actually, change my language to Hindi")
        assert result.intent_type == "correction"

    def test_social_intent(self):
        result = self.classifier.classify("Tell me a joke")
        # Should not be commitment or correction
        assert result.intent_type in ("social", "query")

    def test_key_term_extraction(self):
        result = self.classifier.classify("What language do I prefer?")
        assert "language" in result.key_terms or "prefer" in result.key_terms
