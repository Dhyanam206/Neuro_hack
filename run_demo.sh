#!/bin/bash
# NEUROHACK — Run the 1000-turn demo
# Usage: bash run_demo.sh

set -e

echo "============================================"
echo "  NEUROHACK — Long-Form Memory System"
echo "  1000-Turn Demo"
echo "============================================"
echo ""

# Check Python
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# Install deps if needed
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt

# Check config
if [ ! -f config/settings.yaml ]; then
    echo "[!] No config/settings.yaml found."
    echo "[!] Copying from example and running with MockLLM..."
    cp config/settings.yaml.example config/settings.yaml
fi

# Clean previous runs
rm -f neurohack_memory.db neurohack_vector.index

echo ""
echo "[*] Running 1000-turn demo..."
echo ""

# THE MAIN EVENT: 1000-turn conversation
python3 -m demo.scenarios --scenario full_1000

echo ""
echo "============================================"
echo "  Demo complete. See evaluation/results.json"
echo "============================================"
