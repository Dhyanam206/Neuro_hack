"""
NEUROHACK — Response Path (Section 1.1.1 of Framework)

FIX: Single session.commit() for all access updates (was N commits).
Target: <500ms excluding LLM inference time.
"""

import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.retrieval import IntentClassifier, MemoryRetriever, IntentObject
from core.injection import MemoryInjector, InjectionBlock
from core.buffer import WriteAheadBuffer
from core.temporal import TemporalGarbageCollector


@dataclass
class ResponseOutput:
    """Complete response with metadata for evaluation."""
    response_text: str
    injection_block: InjectionBlock
    intent: IntentObject
    retrieval_latency_ms: float
    total_latency_ms: float
    turn_number: int
    clarification_prompt: Optional[str] = None


class ResponsePath:
    """
    Orchestrates the latency-critical response pipeline.

    Step 1: Intent Classification (rule-based, no LLM)
    Step 2: Memory Retrieval (4-level precedence)
    Step 3: Prompt Construction (tiered injection)
    Step 4: LLM Inference
    Step 5: Response Delivery
    """

    def __init__(
        self,
        llm_client,
        retriever: MemoryRetriever,
        injector: MemoryInjector,
        buffer: WriteAheadBuffer,
        gc: TemporalGarbageCollector,
        system_prompt: str = "You are a helpful AI assistant.",
    ):
        self.llm = llm_client
        self.classifier = IntentClassifier()
        self.retriever = retriever
        self.injector = injector
        self.buffer = buffer
        self.gc = gc
        self.system_prompt = system_prompt

    def process(
        self,
        session: Session,
        user_id: str,
        message: str,
        turn_number: int,
    ) -> ResponseOutput:
        t_start = time.perf_counter()

        # ── Run GC if due ────────────────────────────────────────
        if self.gc.should_run(turn_number):
            self.gc.run(session, turn_number)

        # ── Step 1: Intent Classification ────────────────────────
        intent = self.classifier.classify(message)

        # ── Step 2: Memory Retrieval ─────────────────────────────
        t_retrieve_start = time.perf_counter()

        # Tier 1: Always-inject
        always_inject = self.retriever.get_always_inject(session, user_id)

        # Tier 2: Intent-matched
        pending = self.buffer.get_pending(turn_number)
        intent_results = self.retriever.retrieve(
            session, user_id, intent, turn_number, pending
        )

        # Update last_accessed_turn — SINGLE commit, not N
        try:
            for result in intent_results:
                if result.memory.memory_id:
                    result.memory.last_accessed_turn = turn_number
            for mem in always_inject:
                mem.last_accessed_turn = turn_number
            session.commit()
        except Exception:
            session.rollback()

        t_retrieve_end = time.perf_counter()
        retrieval_latency = (t_retrieve_end - t_retrieve_start) * 1000

        # ── Step 3: Prompt Construction ──────────────────────────
        injection = self.injector.build_injection(
            always_inject=always_inject,
            intent_matched=intent_results,
            vector_fallback=[],
        )

        memory_block = self.injector.format_prompt_block(injection)
        full_prompt = self._build_prompt(message, memory_block)

        # ── Step 4: LLM Inference ────────────────────────────────
        response_text = self.llm.complete(full_prompt)

        # ── Step 5: Return ───────────────────────────────────────
        t_end = time.perf_counter()

        return ResponseOutput(
            response_text=response_text,
            injection_block=injection,
            intent=intent,
            retrieval_latency_ms=retrieval_latency,
            total_latency_ms=(t_end - t_start) * 1000,
            turn_number=turn_number,
        )

    def _build_prompt(self, user_message: str, memory_block: str) -> str:
        parts = [self.system_prompt]
        if memory_block:
            parts.append(f"\n--- ACTIVE MEMORY ---\n{memory_block}\n--- END MEMORY ---")
        parts.append(f"\nUser: {user_message}")
        parts.append("\nAssistant:")
        return "\n".join(parts)
