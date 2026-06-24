"""
NEUROHACK — Visualizer

Pretty-prints memory state, retrieval logs, and injection blocks.
"""

from sqlalchemy.orm import Session
from core.models import Memory, MemoryStatus


def print_turn_summary(turn, message, write_result, response):
    """Print a concise summary of what happened at a turn."""
    print(f"  Turn {turn:>4d} | \"{message[:70]}{'...' if len(message) > 70 else ''}\"")

    # Write path
    if write_result.gate_fired:
        rules = ", ".join(write_result.matched_rules)
        if write_result.dead_lettered:
            print(f"           | WRITE: Gate [{rules}] -> DEAD-LETTERED: {write_result.error}")
        elif write_result.resolution:
            res = write_result.resolution.value
            mem_key = write_result.memory.key if write_result.memory else "N/A"
            mem_val = (write_result.memory.value[:40] if write_result.memory else "N/A")
            print(f"           | WRITE: Gate [{rules}] -> {res.upper()} ({mem_key}={mem_val})")
        else:
            print(f"           | WRITE: Gate [{rules}] -> stored")
    else:
        print(f"           | WRITE: Gate did not fire")

    # Response path
    inj = response.injection_block
    n_mem = len(inj.memory_ids)
    tokens = inj.total_tokens
    lat = response.retrieval_latency_ms

    print(f"           | READ:  {n_mem} memories, {tokens} tokens, {lat:.1f}ms")
    print()


def print_memory_state(session: Session, user_id: str):
    """Print the full memory state for a user."""
    print(f"\n{'='*70}")
    print(f"  MEMORY STATE")
    print(f"{'='*70}")

    all_mem = (
        session.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.created_at)
        .all()
    )

    active = [m for m in all_mem if m.status == MemoryStatus.ACTIVE]
    superseded = [m for m in all_mem if m.status == MemoryStatus.SUPERSEDED]
    expired = [m for m in all_mem if m.status == MemoryStatus.EXPIRED]
    conflicted = [m for m in all_mem if m.status == MemoryStatus.CONFLICTED]



    print(f"\n  Active ({len(active)}):")
    for m in active:
        val = m.value[:50] if m.value else ""
        print(f"    [{m.type.value:8s}] {m.key:25s} = {val} "
              f"(conf={m.confidence:.2f}, turn={m.source_turn})")

    if superseded:
        print(f"\n  Superseded ({len(superseded)}):")
        for m in superseded:
            val = m.value[:50] if m.value else ""
            print(f"    [{m.type.value:8s}] {m.key:25s} = {val} "
                  f"(turn={m.source_turn}, replaced_by={m.superseded_by})")

    if expired:
        print(f"\n  Expired ({len(expired)}):")
        for m in expired:
            val = m.value[:50] if m.value else ""
            print(f"    [{m.type.value:8s}] {m.key:25s} = {val} (turn={m.source_turn})")

    if conflicted:
        print(f"\n  Conflicted ({len(conflicted)}):")
        for m in conflicted:
            val = m.value[:50] if m.value else ""
            print(f"    [{m.type.value:8s}] {m.key:25s} = {val} (turn={m.source_turn})")

    print(f"\n  Total: {len(all_mem)} "
          f"(active={len(active)}, superseded={len(superseded)}, "
          f"expired={len(expired)}, conflicted={len(conflicted)})")
    print()


def print_metrics_summary(metrics):
    """Print evaluation metrics summary."""
    print(f"\n{'='*70}")
    print(f"  METRICS: {metrics.scenario_name}")
    print(f"{'='*70}")
    d = metrics.to_dict()
    for k, v in d.items():
        print(f"    {k:35s}: {v}")
    print()
