"""
NEUROHACK — Evaluation Report Generator

Runs the 1000-turn demo and outputs quantitative results.
Usage: python -m evaluation.report
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.scenarios import run_1000_turn_demo


def generate_report():
    """Run the full 1000-turn demo and generate evaluation report."""
    print("Running full 1000-turn evaluation...")
    metrics = run_1000_turn_demo(verbose=True)
    print("\nReport generation complete.")
    return metrics


if __name__ == "__main__":
    generate_report()
