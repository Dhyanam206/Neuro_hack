# NEUROHACK — Long-Form Conversational Memory System

> Deterministic · Auditable · Real-Time · 1,000+ Turns

A production-grade memory system for AI agents where information introduced at turn 1 correctly influences behavior at turn 1,000 — without replaying the conversation and without growing the prompt.

---

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/bhavyaPawar22/Neuro_hack
cd neurohack

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp config/settings.yaml.example config/settings.yaml
# Add your LLM API key to config/settings.yaml (for interactive mode)

# 4. Run the demo
bash run_demo.sh
```

---

## What You'll See

The demo runs a 1000-turn conversation showcasing four scenarios:

1. **Long-range recall** — Preference set at turn 1, correctly applied at turn 50+
2. **Supersession** — User changes preference mid-conversation, old value never resurfaces
3. **Temporal expiration** — "Call me tomorrow" stored with absolute timestamp, excluded after date passes
4. **Flat token budget** — Injected token count printed at every turn, never exceeds 800

---

## Execution Modes

NEUROHACK supports two execution modes:

| Mode | Description | LLM Required |
|------|-------------|--------------|
| **Benchmark Mode** | Automated 1000-turn stress test with simulated conversations | No |
| **Interactive Mode** | Live chat with memory-enabled responses via Ollama | Yes (Ollama) |

---

## Benchmark Mode (No LLM Required)

Benchmark mode validates the memory system through automated testing without requiring any LLM backend.

### Running the 1000-Turn Benchmark

```bash
# Run the full 1000-turn benchmark
python -m demo.scenarios --scenario full_1000
```

### What the Benchmark Tests

- **Long-range recall**: Verifies information from turn 1 influences turn 1000
- **Supersession protocol**: Confirms old values never resurface after updates
- **Token cap enforcement**: Ensures injection never exceeds 800 tokens
- **Temporal expiration**: Validates time-bound memories are excluded after expiration

### Benchmark Output

The benchmark generates:

```
evaluation/
└── results.json          # Quantitative metrics and test results
```
---

## Interactive Mode (Requires Ollama)

Interactive mode enables live conversations with real-time memory storage and retrieval using Ollama as the LLM backend.

### Step 1: Install Ollama

**macOS/Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from [ollama.com/download](https://ollama.com/download)

### Step 2: Start Ollama Server

```bash
ollama serve
```

Keep this terminal running. The server will be available at `http://localhost:11434`.

### Step 3: Pull the Model

```bash
ollama pull llama3
```

### Step 4: Configure NEUROHACK

Edit `config/settings.yaml`:

```yaml
llm:
  provider: ollama
  model: llama3
  base_url: http://localhost:11434/v1
```

### Step 5: Launch Interactive Mode

```bash
python interactive.py  #cmd to run interactive mode
```

## Database File

NEUROHACK uses SQLite as the source of truth for all memory storage:

```
neurohack/
└── neurohack.db          # Auto-created on first run
```

The database file is:
- **Created automatically** when the system first runs
- **Persistent** across sessions — memories survive restarts
- **Portable** — single file, easy to backup or migrate
- **Inspectable** — use any SQLite browser to view tables


## Switching Between Modes

| Task | Command |
|------|---------|
| Run benchmark (fast, no LLM) | `python -m demo.scenarios --scenario full_1000 --quiet` |
| Run interactive mode | `python interactive.py` |
| Check database contents | `sqlite3 neurohack.db "SELECT * FROM memories;"` |
| View benchmark results | `cat evaluation/results.json \| jq` |

---


## Project Structure

```
neurohack/
├── README.md
├── requirements.txt
├── run_demo.sh              # Quick 100-turn demo
├── interactive.py           # Live chat mode
├── neurohack.db             # Auto-created SQLite database
├── config/
│   ├── settings.yaml.example
│   └── settings.yaml        # Your configuration
├── core/
│   ├── models.py            # Memory schema (SQLAlchemy)
│   ├── database.py          # DB init & connection
│   ├── rule_gate.py         # Deterministic extraction classifier
│   ├── structurer.py        # LLM structuring (post-gate only)
│   ├── temporal.py          # Time resolution & garbage collector
│   ├── retrieval.py         # 4-level precedence chain + token budget
│   ├── injection.py         # Memory → behavioral directive formatter
│   ├── conflict.py          # Supersession & contradiction detection
│   ├── buffer.py            # Write-ahead buffer
│   └── dead_letter.py       # Failed extraction logging
├── pipeline/
│   ├── response_path.py     # Latency-critical response pipeline
│   └── write_path.py        # Async memory write pipeline
├── demo/
│   ├── sample_conversations.json
│   ├── scenarios.py         # Scenario runner (benchmark mode)
│   └── visualizer.py        # Memory state printer
├── tests/
│   ├── test_rule_gate.py
│   ├── test_temporal.py
│   ├── test_retrieval.py
│   ├── test_supersession.py
│   ├── test_conflict.py
│   └── test_e2e.py
├── evaluation/
    ├── metrics.py           # Recall, accuracy, latency
    ├── report.py            # Generate quantitative results
    └── results.json         # Benchmark output (auto-generated)
```

---

## Tech Stack

- **Python 3.11+**
- **SQLite** — Zero-setup relational store (source of truth)
- **SQLAlchemy** — ORM for schema + queries
- **FAISS** — Local vector index (fallback only)
- **Ollama** — Local LLM for interactive mode


---
