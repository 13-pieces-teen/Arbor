"""eval.py — PROTECTED evaluation harness. Do not edit during a research run.

Contract: it must accept a split, run the candidate from solution.py through a
correctness gate, and print exactly one machine-readable line:

    score: <float>

A candidate that fails correctness should still print a score (e.g. `score: 0.0`)
so the metric is always parseable. dev and test MUST use disjoint data — declare the
split in the README front-matter (`splits:`) so the verifier can prove disjointness, and
keep these constants in sync with it.
"""

from __future__ import annotations

import argparse

# The held-out split. Keep in sync with `splits:` in the README front-matter — the
# verifier proves disjointness against that declaration.
DEV_SEED_BASE = 1000
TEST_SEED_BASE = 9000
N_INSTANCES = 3


def evaluate(split: str) -> float:
    """TODO: build instances for *split*, gate on correctness, return the metric."""
    base = DEV_SEED_BASE if split == "dev" else TEST_SEED_BASE
    _seeds = [base + i for i in range(N_INSTANCES)]
    raise NotImplementedError("compute and return the score")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    args = parser.parse_args()
    try:
        score = evaluate(args.split)
    except NotImplementedError:
        score = 0.0
    print(f"score: {score:.4f}")


if __name__ == "__main__":
    main()
