"""
NEUROHACK Core — Memory management engine.

Modules:
    config      - Configuration loader (reads settings.yaml)
    llm_client  - Unified LLM client (OpenAI/Anthropic/Groq/Ollama/Mock)
    models      - SQLAlchemy schema (memories, dead_letter, clarifications, audit_log)
    database    - DB initialization and session management
    rule_gate   - Deterministic extraction classifier (NO LLM)
    structurer  - LLM-based schema structuring (ONLY after gate fires)
    temporal    - Time resolution, timezone handling, garbage collector
    retrieval   - 4-level precedence chain with tiered token budget
    injection   - Memory -> behavioral directive formatter
    conflict    - Supersession, contradiction detection, clarification queue
    buffer      - Write-ahead buffer (in-memory FIFO)
    dead_letter - Failed extraction logging and retry
"""
