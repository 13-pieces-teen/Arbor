"""``arbor.zoo.scaffold`` — create the reference benchmark folder structure.

Deterministic, keyless file writer. Given the contract facts the host model
decided during intake, it writes the *measurement plumbing* (eval entrypoint,
dev/test split layout, an editable ``solution.py`` placeholder) and, for the
``zoo`` style, the README front-matter contract + PROVENANCE card. It never
writes the solution logic itself.

Idempotent and non-destructive: an existing file is recorded under ``skipped``
and never overwritten. Templates are rendered in-package (not copied from
``arbor-zoo/_template``, which is not shipped in the wheel) so the front-matter
is guaranteed to round-trip through :func:`arbor.zoo.pack.read_front_matter`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .pack import find_eval_entrypoint
from .verify import VerifyResult, verify_pack

_STYLES = ("light", "zoo")
_ENTRYPOINTS = ("eval.py", "eval.sh")
_DIRECTIONS = ("maximize", "minimize")


@dataclass
class ScaffoldResult:
    """Outcome of one scaffold call."""

    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    verify: list[VerifyResult] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


# ── templates ──────────────────────────────────────────────────────────────

_SOLUTION = '''"""solution.py — the ONLY editable artifact (Arbor's edit surface).

Replace this with a working baseline. It must be correct first; Arbor then
optimizes it to improve the score. Keep the entry-point signature stable —
``eval.py`` calls into it.
"""

from __future__ import annotations


def solve(problem):
    """TODO: return a solution for *problem* (the simplest correct baseline)."""
    raise NotImplementedError("fill in the baseline solver")
'''

_EVAL_SH = '''#!/usr/bin/env bash
# eval.sh — PROTECTED wrapper. Do not edit during a research run.
#   bash eval.sh dev    # Arbor iterates here
#   bash eval.sh test   # held-out gate
# Prints a single "score: <float>" line.
set -euo pipefail
SPLIT="${1:-dev}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONHASHSEED=0
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" "$HERE/eval.py" --split "$SPLIT"
'''

_PROVENANCE = """# Provenance

All seven headings below are required. The verifier checks they are present; a
maintainer reads and accepts the content before the benchmark ships.

## Source

Where the benchmark comes from — paper, repo, or competition, with a link, and
how the data was collected or generated.

## Setup & environment

Hardware (CPU / GPU), Python version, install command, env vars, and any API
keys, downloads, or services the user must provision. State whether it is offline.

## Data source & license

Where the data comes from, its license, and whether it may be redistributed.

## Baseline implementation

How the shipped baseline works — the approach, why it scores what it does, and
what headroom it leaves for Arbor.

## Baseline reproduction

The number `eval dev` prints today (must match `baseline.score` in the README
front-matter) and any gap from a published number.

## Contamination assessment

**Mandatory.** Could the test split be in a model's pre-training data? Is the
held-out split truly disjoint from dev?

## Caveats

Known limitations — hardware sensitivity, metric noise, scope.
"""


def _eval_py(splits: dict[str, Any]) -> str:
    """Render a protected eval.py stub for the declared split kind.

    The stub catches NotImplementedError and prints ``score: 0.0`` so the metric
    is always parseable before the baseline is filled in.
    """
    if splits.get("kind") == "path":
        body = (
            "    data_dir = Path(__file__).parent / \"data\" / split\n"
            "    _instances = sorted(p for p in data_dir.glob(\"*\") if p.is_file())\n"
            "    raise NotImplementedError(\"score solution.solve over the split's instances\")\n"
        )
        head = "from pathlib import Path\n"
    else:
        dev = splits.get("dev", {}) or {}
        test = splits.get("test", {}) or {}
        head = (
            f"DEV_SEED_BASE = {int(dev.get('base', 1000))}\n"
            f"TEST_SEED_BASE = {int(test.get('base', 9000))}\n"
            f"DEV_COUNT = {int(dev.get('count', 3))}\n"
            f"TEST_COUNT = {int(test.get('count', 3))}\n"
        )
        body = (
            "    base = DEV_SEED_BASE if split == \"dev\" else TEST_SEED_BASE\n"
            "    count = DEV_COUNT if split == \"dev\" else TEST_COUNT\n"
            "    _seeds = [base + i for i in range(count)]\n"
            "    raise NotImplementedError(\"compute the score from solution.solve\")\n"
        )
    return (
        '"""eval.py — PROTECTED evaluation harness. Do not edit during a research run.\n\n'
        "Prints exactly one line ``score: <float>`` for ``--split dev|test``. dev/test use\n"
        "disjoint data; keep any constants in sync with the README front-matter ``splits:``.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "import argparse\n"
        f"{head}\n\n"
        "def evaluate(split: str) -> float:\n"
        f"{body}\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument(\"--split\", choices=[\"dev\", \"test\"], default=\"dev\")\n"
        "    args = parser.parse_args()\n"
        "    try:\n"
        "        score = evaluate(args.split)\n"
        "    except NotImplementedError:\n"
        "        score = 0.0\n"
        "    print(f\"score: {score:.4f}\")\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def _readme(name: str, direction: str, splits: dict, baseline: dict,
            edit: list[str], eval_cmd: str | None, eval_entrypoint: str = "eval.py") -> str:
    fm: dict[str, Any] = {"name": name, "metric": {"direction": direction}}
    if eval_cmd:
        fm["eval"] = {"cmd": eval_cmd}
    fm["splits"] = splits
    fm["baseline"] = baseline
    fm["edit"] = edit
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    if eval_entrypoint == "eval.sh":
        run = ("bash eval.sh dev    # iterate here\n"
               "bash eval.sh test   # held-out gate\n")
    else:
        run = ("python eval.py --split dev    # iterate here\n"
               "python eval.py --split test   # held-out gate\n")
    body = (
        f"# {name}\n\n"
        "One-line summary of the benchmark.\n\n"
        "## Task & metric\n"
        "What the task is, what a solution looks like, the edit surface, and what is "
        "off-limits (the eval harness and any ground-truth files).\n\n"
        "## Run the baseline\n"
        "```bash\n"
        f"{run}"
        "```\n"
        "Each prints one `score: <float>` line.\n\n"
        "## Optimize with Arbor\n"
        "Copy this folder out of the Arbor checkout (it uses git worktrees), then run "
        "`arbor` and confirm the contract.\n\n"
        "## Provenance\n"
        "See [`PROVENANCE.md`](PROVENANCE.md).\n"
    )
    return f"---\n{front}---\n\n{body}"


def _next_steps(style: str, res: ScaffoldResult) -> list[str]:
    steps = [
        "Fill in `solution.py` with the simplest correct baseline.",
        "Implement `evaluate()` in `eval.py` to score `solution.solve`.",
    ]
    if style == "zoo":
        steps.append("Complete `PROVENANCE.md` (all seven sections) before submitting.")
        steps.append("Run `arbor benchmark verify <dir>` until it exits 0.")
    return steps


def scaffold_benchmark(
    target: Path,
    *,
    name: str,
    metric_direction: str,
    splits: dict,
    baseline: dict | None = None,
    edit: list[str] | None = None,
    eval_cmd: str | None = None,
    style: str = "light",
    eval_entrypoint: str = "eval.py",
) -> ScaffoldResult:
    """Scaffold the Arbor reference folder under *target*. See module docstring."""
    if style not in _STYLES:
        raise ValueError(f"style must be one of {_STYLES}, got {style!r}")
    if metric_direction not in _DIRECTIONS:
        raise ValueError(f"metric_direction must be one of {_DIRECTIONS}")
    if eval_entrypoint not in _ENTRYPOINTS:
        raise ValueError(f"eval_entrypoint must be one of {_ENTRYPOINTS}")

    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    edit = edit or ["solution.py"]
    baseline = baseline or {"score": 0.0, "tolerance": 0.0, "kind": "exact"}
    res = ScaffoldResult()

    def write(rel: str, content: str) -> None:
        p = target / rel
        if p.exists():
            res.skipped.append(rel)
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        # Force LF: a CRLF-translated eval.sh shebang ("…bash\r") is a broken
        # interpreter on Unix, and the rest of the pack should stay LF too.
        p.write_text(content, encoding="utf-8", newline="\n")
        res.created.append(rel)

    existing = find_eval_entrypoint(target)
    if existing is None:
        write("eval.py", _eval_py(splits))
        if eval_entrypoint == "eval.sh":
            write("eval.sh", _EVAL_SH)
    else:
        res.skipped.append(existing)

    if splits.get("kind") == "path":
        # Visible placeholder instances (not hidden .gitkeep): globs like
        # `data/dev/**` skip dotfiles, so empty .gitkeep dirs would fail the
        # splits-disjoint check. One example per split keeps the pack
        # structurally verifiable; the user replaces them with real data.
        write("data/dev/example_001.txt", "# replace with a real dev instance\n")
        write("data/test/example_001.txt", "# replace with a real held-out test instance\n")

    write("solution.py", _SOLUTION)

    if style == "zoo":
        write("README.md", _readme(name, metric_direction, splits, baseline, edit, eval_cmd,
                                   eval_entrypoint))
        write("PROVENANCE.md", _PROVENANCE)
        write("requirements.txt", "# add runtime dependencies here\n")
        res.verify = verify_pack(target, run_eval=False)

    res.next_steps = _next_steps(style, res)
    return res
