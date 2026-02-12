"""
NEUROHACK — Configuration Loader

Reads settings.yaml and provides typed access to all system parameters.
This was MISSING — causing the demo to never connect to the real LLM.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class LLMConfig:
    provider: str = "ollama"
    api_key: str = ""
    model: str = "llama3"
    base_url: Optional[str] = "http://localhost:11434/v1"

    def __post_init__(self):
        # If api_key not provided in config, use environment variable
        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY", "")


@dataclass
class TokenBudgetConfig:
    tier_1: int = 300
    tier_2: int = 300
    tier_3: int = 200
    total: int = 800


@dataclass
class RetrievalConfig:
    top_k: int = 5


@dataclass
class BufferConfig:
    max_capacity: int = 10
    ttl_turns: int = 2


@dataclass
class GCConfig:
    interval_turns: int = 50
    interval_minutes: int = 5


@dataclass
class RankingConfig:
    recency: float = 0.3
    confidence: float = 0.3
    specificity: float = 0.4


@dataclass
class VectorConfig:
    enabled: bool = True
    dimension: int = 384
    index_path: str = "neurohack_vector.index"


@dataclass
class NeurohackConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    database_path: str = "neurohack_memory.db"
    database_echo: bool = False
    confidence_threshold: float = 0.7
    token_budget: TokenBudgetConfig = field(default_factory=TokenBudgetConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    buffer: BufferConfig = field(default_factory=BufferConfig)
    gc: GCConfig = field(default_factory=GCConfig)
    ranking_weights: RankingConfig = field(default_factory=RankingConfig)
    user_timezone: Optional[str] = None
    vector: VectorConfig = field(default_factory=VectorConfig)


def load_config(config_path: str = None) -> NeurohackConfig:
    """
    Load configuration from settings.yaml.
    Searches in order: provided path, ./config/settings.yaml, ./settings.yaml
    """
    if config_path is None:
        search_paths = [
            os.path.join(os.getcwd(), "config", "settings.yaml"),
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "config", "settings.yaml"),
            os.path.join(os.getcwd(), "settings.yaml"),
        ]
        for p in search_paths:
            if os.path.exists(p):
                config_path = p
                break

    if config_path is None or not os.path.exists(config_path):
        print("[WARN] No settings.yaml found. Using defaults (MockLLM).")
        return NeurohackConfig()

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if not raw:
        return NeurohackConfig()

    llm_raw = raw.get("llm", {})
    db_raw = raw.get("database", {})
    tb_raw = raw.get("token_budget", {})
    ret_raw = raw.get("retrieval", {})
    buf_raw = raw.get("buffer", {})
    gc_raw = raw.get("gc", {})
    rw_raw = raw.get("ranking_weights", {})
    vec_raw = raw.get("vector", {})
    ud_raw = raw.get("user_defaults", {})

    return NeurohackConfig(
        llm=LLMConfig(
            provider=llm_raw.get("provider", "openai"),
            api_key=llm_raw.get("api_key", ""),
            model=llm_raw.get("model", "gpt-4o-mini"),
            base_url=llm_raw.get("base_url"),
        ),
        database_path=db_raw.get("path", "neurohack_memory.db"),
        database_echo=db_raw.get("echo", False),
        confidence_threshold=raw.get("confidence_threshold", 0.7),
        token_budget=TokenBudgetConfig(
            tier_1=tb_raw.get("tier_1", 300),
            tier_2=tb_raw.get("tier_2", 300),
            tier_3=tb_raw.get("tier_3", 200),
            total=tb_raw.get("total", 800),
        ),
        retrieval=RetrievalConfig(top_k=ret_raw.get("top_k", 5)),
        buffer=BufferConfig(
            max_capacity=buf_raw.get("max_capacity", 10),
            ttl_turns=buf_raw.get("ttl_turns", 2),
        ),
        gc=GCConfig(
            interval_turns=gc_raw.get("interval_turns", 50),
            interval_minutes=gc_raw.get("interval_minutes", 5),
        ),
        ranking_weights=RankingConfig(
            recency=rw_raw.get("recency", 0.3),
            confidence=rw_raw.get("confidence", 0.3),
            specificity=rw_raw.get("specificity", 0.4),
        ),
        user_timezone=ud_raw.get("timezone"),
        vector=VectorConfig(
            enabled=vec_raw.get("enabled", True),
            dimension=vec_raw.get("dimension", 384),
            index_path=vec_raw.get("index_path", "neurohack_vector.index"),
        ),
    )
