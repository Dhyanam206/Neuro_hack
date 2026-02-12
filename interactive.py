"""
NEUROHACK — Interactive Terminal Mode

• Uses persistent neurohack_memory.db
• Runs BOTH write path and response path
• Supports dynamic memory updates + supersession
• Outputs PS-style structured memory influence block
"""

import json

from core.config import load_config
from core.database import DatabaseManager
from core.llm_client import LLMClient
from core.retrieval import MemoryRetriever
from core.injection import MemoryInjector
from core.buffer import WriteAheadBuffer
from core.temporal import TemporalResolver, TemporalGarbageCollector
from core.conflict import ConflictHandler
from core.dead_letter import DeadLetterQueue
from core.structurer import MemoryStructurer
from core.models import Memory
from pipeline.response_path import ResponsePath
from pipeline.write_path import WritePath


# ─────────────────────────────────────────────
# INITIALIZE SYSTEM
# ─────────────────────────────────────────────

config = load_config()

# Use SAME DB as demo
db = DatabaseManager(config.database_path)
db.create_tables()

llm = LLMClient(config.llm)

retriever = MemoryRetriever({
    "top_k": config.retrieval.top_k,
    "confidence_threshold": config.confidence_threshold,
    "ranking_weights": {
        "recency": config.ranking_weights.recency,
        "confidence": config.ranking_weights.confidence,
        "specificity": config.ranking_weights.specificity,
    }
})

injector = MemoryInjector({
    "tier_1": config.token_budget.tier_1,
    "tier_2": config.token_budget.tier_2,
    "tier_3": config.token_budget.tier_3,
    "total": config.token_budget.total,
})

buffer = WriteAheadBuffer(
    config.buffer.max_capacity,
    config.buffer.ttl_turns
)

resolver = TemporalResolver(config.user_timezone or "Asia/Kolkata")
gc = TemporalGarbageCollector(
    config.gc.interval_turns,
    config.gc.interval_minutes
)

conflict_handler = ConflictHandler()
dead_letter = DeadLetterQueue()
structurer = MemoryStructurer(llm)

write_path = WritePath(
    structurer,
    resolver,
    conflict_handler,
    buffer,
    dead_letter
)

response_path = ResponsePath(
    llm,
    retriever,
    injector,
    buffer,
    gc
)

user_id = "interactive_user"
turn_number = 1

print("\nNEUROHACK Interactive Mode")
print("Type 'exit' to quit.\n")


# ─────────────────────────────────────────────
# INTERACTIVE LOOP
# ─────────────────────────────────────────────

while True:

    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    with db.session() as session:

        # ── WRITE PATH (memory update happens here) ──────────
        write_result = write_path.process(
            session,
            user_id,
            user_input,
            turn_number
        )

        # ── RESPONSE PATH (retrieval + injection + LLM) ─────
        response = response_path.process(
            session,
            user_id,
            user_input,
            turn_number
        )

        print("\nAssistant:")
        print(response.response_text)

        # ── Build PS-style structured memory output ──────────
        active_memories = []

        for mem_id in response.injection_block.memory_ids:
            mem = session.get(Memory, mem_id)
            if mem:
                active_memories.append({
                    "memory_id": mem.memory_id,
                    "content": f"{mem.key}: {mem.value}",
                    "origin_turn": mem.source_turn,
                    "last_used_turn": mem.last_accessed_turn
                })

        structured_output = {
            "active_memories": active_memories,
            "response_generated": True
        }

        print("\nStructured Output:")
        print(json.dumps(structured_output, indent=2))

        # Optional debug info
        if write_result.resolution:
            print(f"\n[Conflict Resolution]: {write_result.resolution.value}")

    turn_number += 1
