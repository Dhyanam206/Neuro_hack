"""
NEUROHACK — Rule Gate Tests

Verifies the deterministic extraction classifier produces consistent results.
"""

import pytest
from core.rule_gate import evaluate_gate


class TestRuleGateFires:
    """Tests that the gate fires for memory-worthy messages."""

    def test_preference_statement(self):
        result = evaluate_gate("My preferred language is Kannada")
        assert result.fired is True
        assert "PREF_001" in result.matched_rules

    def test_negative_preference(self):
        result = evaluate_gate("Never call me before 9 AM")
        assert result.fired is True
        assert "PREF_002" in result.matched_rules

    def test_behavioral_instruction(self):
        result = evaluate_gate("Always use formal tone with me")
        assert result.fired is True
        assert "PREF_003" in result.matched_rules

    def test_temporal_commitment(self):
        result = evaluate_gate("Call me tomorrow after 11 AM")
        assert result.fired is True
        assert "TEMP_001" in result.matched_rules

    def test_named_entity(self):
        result = evaluate_gate("My doctor is Dr. Patel")
        assert result.fired is True
        assert "ENT_001" in result.matched_rules

    def test_self_disclosure(self):
        result = evaluate_gate("I'm a vegetarian")
        assert result.fired is True

    def test_correction(self):
        result = evaluate_gate("Actually, my preferred language is Hindi")
        assert result.fired is True
        assert "CORR_001" in result.matched_rules


class TestRuleGateDoesNotFire:
    """Tests that the gate does NOT fire for non-memory messages."""

    def test_phatic_ok(self):
        assert evaluate_gate("ok").fired is False

    def test_phatic_thanks(self):
        assert evaluate_gate("thanks").fired is False

    def test_greeting(self):
        assert evaluate_gate("hello").fired is False

    def test_question(self):
        assert evaluate_gate("What's the weather?").fired is False

    def test_procedural(self):
        assert evaluate_gate("yes").fired is False

    def test_go_ahead(self):
        assert evaluate_gate("go ahead").fired is False


class TestGateDeterminism:
    """Tests that the gate is a pure function (same input → same output)."""

    def test_same_input_same_output(self):
        msg = "My preferred language is Kannada"
        r1 = evaluate_gate(msg)
        r2 = evaluate_gate(msg)
        assert r1.fired == r2.fired
        assert r1.matched_rules == r2.matched_rules
