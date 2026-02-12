"""
NEUROHACK — Evaluation Metrics

Measures: recall@K, accuracy, retrieval latency, token budget compliance.
Used to generate quantitative results for Slide 9 of the presentation.
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class TurnMetrics:
    """Metrics collected at a single turn."""
    turn_number: int
    gate_fired: bool
    memories_injected: int
    tokens_injected: int
    retrieval_latency_ms: float
    memory_found: bool = False  # Was the target memory retrieved?


@dataclass
class ScenarioMetrics:
    """Aggregated metrics for a scenario run."""
    scenario_name: str
    total_turns: int
    turns: List[TurnMetrics] = field(default_factory=list)

    @property
    def recall_at_k(self) -> float:
        """Fraction of turns where the target memory was successfully retrieved."""
        relevant = [t for t in self.turns if t.memory_found is not None]
        if not relevant:
            return 0.0
        return sum(1 for t in relevant if t.memory_found) / len(relevant)

    @property
    def avg_retrieval_latency_ms(self) -> float:
        if not self.turns:
            return 0.0
        return sum(t.retrieval_latency_ms for t in self.turns) / len(self.turns)

    @property
    def max_tokens_injected(self) -> int:
        if not self.turns:
            return 0
        return max(t.tokens_injected for t in self.turns)

    @property
    def token_budget_violations(self) -> int:
        """Count of turns where injection exceeded 800 tokens."""
        return sum(1 for t in self.turns if t.tokens_injected > 800)

    def to_dict(self) -> Dict:
        return {
            "scenario": self.scenario_name,
            "total_turns": self.total_turns,
            "recall@k": round(self.recall_at_k, 3),
            "avg_retrieval_latency_ms": round(self.avg_retrieval_latency_ms, 2),
            "max_tokens_injected": self.max_tokens_injected,
            "token_budget_violations": self.token_budget_violations,
        }
