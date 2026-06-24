"""Agent-driven collection stages (Stage 2: baseline bring-up).

The collection *spine* (:mod:`arbor.zoo.collect`) is deterministic — it acquires
materials and scaffolds a draft. This module is the agent-driven part: given a live
LLM provider, :func:`bringup` spawns one agent in the draft folder to make a baseline
actually run — install deps, get the reference working, wrap a clean ``eval`` that
prints ``score:``, and write the README + PROVENANCE — then checks its work by running
the eval and the structural verifier.

It reuses the core :class:`~arbor.core.agent.Agent` runtime (the same one the executor
uses) but stays a standalone flow: it never wires into the Coordinator/Executor research
loop (a §2.1 correctness requirement).

The agent run is behind an injected ``run_agent`` callable so the orchestration is
testable without a live LLM (a fake runner writes the files a real agent would). The real
runner — :func:`real_agent_runner` — constructs the ``Agent`` with bash + file tools and
needs a configured provider (API key); validating its *reasoning* needs live iteration.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Protocol

from .pack import find_eval_entrypoint
from .verify import VerifyResult, verify_pack


class AgentRunner(Protocol):
    """Runs an agent to completion in *cwd* and returns its final transcript text."""

    def __call__(self, *, cwd: Path, system_prompt: str, task: str,
                 max_turns: int) -> Awaitable[str]: ...


BRINGUP_SYSTEM_PROMPT = """\
You are a benchmark bring-up assistant. You turn an acquired research repo into a runnable
Arbor benchmark in the current directory. You write the *measurement plumbing and a working
baseline* — never an optimized solution.

Produce, in the current directory:
  * a runnable eval: `bash eval.sh dev|test` (or `python eval.py --split dev|test`) prints
    exactly one line `score: <float>`, after a correctness check. dev and test must use
    DISJOINT data (the held-out split).
  * the editable baseline (e.g. `solution.py`) — the simplest correct reference, the thing
    Arbor will later optimize. Do NOT optimize it.
  * `README.md` — plain language: the task, the metric (and whether higher/lower is better),
    which file(s) Arbor may edit, and how dev/test differ.
  * `PROVENANCE.md` — for humans: Source, Setup & environment, Baseline, Contamination
    assessment, Caveats.

Use the acquired source materials at the path you are told. Install dependencies as needed.
You are DONE only when `bash eval.sh dev` prints a `score:` line and `arbor benchmark verify .`
would pass. If you are blocked, write what you have and explain the blocker clearly.
"""


@dataclass
class BringupResult:
    """Outcome of a bring-up run."""

    transcript: str = ""
    dev_score: float | None = None
    verify: list[VerifyResult] = field(default_factory=list)
    ok: bool = False
    notes: list[str] = field(default_factory=list)


def _parse_score(text: str) -> float | None:
    # Mirrors arbor.mcp.session_ops.parse_score for the documented `score: <float>` line,
    # kept local so arbor.zoo stays dependency-light.
    import re
    matches = re.findall(r"\bscore\s*[:=]\s*([-+]?\d+(?:\.\d+)?)", text, re.I)
    return float(matches[-1]) if matches else None


def _run_eval_dev(pack_dir: Path, timeout: int) -> tuple[float | None, str]:
    """Run the eval on the dev split and parse a score (the bring-up success check)."""
    entry = find_eval_entrypoint(pack_dir)
    if entry == "eval.sh":
        cmd = ["bash", str(pack_dir / "eval.sh"), "dev"]
    elif entry == "eval.py":
        cmd = [os.environ.get("PYTHON", "python3"), str(pack_dir / "eval.py"), "--split", "dev"]
    else:
        return None, "no eval entrypoint"
    try:
        proc = subprocess.run(cmd, cwd=str(pack_dir), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"eval timed out after {timeout}s"
    out = proc.stdout + proc.stderr
    return _parse_score(out), out[-2000:]


async def bringup(
    pack_dir: Path,
    *,
    run_agent: AgentRunner,
    materials_dir: Path | None = None,
    max_turns: int = 40,
    eval_timeout: int = 600,
) -> BringupResult:
    """Run the bring-up agent in *pack_dir*, then check its work (eval runs + verify).

    *run_agent* does the actual agent work (real: an :class:`Agent`; in tests: a fake that
    writes the files). *materials_dir* is the acquired source the agent should draw from.
    """
    result = BringupResult()
    where = f"\n\nThe acquired source materials are at: {materials_dir}" if materials_dir else ""
    task = (
        f"Bring up the benchmark in this directory ({pack_dir}). Make the baseline run and "
        f"the eval print a `score:` line on dev and test, and write README.md + "
        f"PROVENANCE.md.{where}"
    )
    try:
        result.transcript = await run_agent(
            cwd=pack_dir, system_prompt=BRINGUP_SYSTEM_PROMPT, task=task, max_turns=max_turns)
    except Exception as exc:  # noqa: BLE001 — surface agent/provider errors as a blocker
        result.notes.append(f"agent run failed: {exc}")
        return result

    # ── success check: the eval actually runs and scores, and the pack verifies ──
    result.dev_score, eval_out = _run_eval_dev(pack_dir, eval_timeout)
    if result.dev_score is None:
        result.notes.append(f"eval did not print a parseable score:\n{eval_out}")
    result.verify = verify_pack(pack_dir)
    verify_ok = not any(r.status == "fail" for r in result.verify)
    result.ok = result.dev_score is not None and verify_ok
    if not verify_ok:
        result.notes.append("structural verify still has failures")
    return result


def real_agent_runner(
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AgentRunner:
    """Build the real :class:`Agent`-backed runner. Needs a configured provider / API key.

    Heavy imports are deferred so importing :mod:`arbor.zoo` stays light.
    """
    async def _run(*, cwd: Path, system_prompt: str, task: str, max_turns: int) -> str:
        from arbor.core import Agent, AgentConfig, create_provider
        from arbor.core.tools import get_all_tools

        # Only pass provider fields that were set, so AgentConfig's defaults (which read
        # the env / user config) apply when they're omitted.
        llm_kw = {k: v for k, v in
                  {"provider": provider, "model": model, "api_key": api_key,
                   "base_url": base_url}.items() if v is not None}
        cfg = AgentConfig(cwd=str(cwd), max_turns=max_turns, auto_git=False, **llm_kw)
        prov = create_provider(cfg)
        tools = get_all_tools(cwd=str(cwd), config=cfg)
        agent = Agent(provider=prov, tools=tools, system_prompt=system_prompt, config=cfg)
        return await agent.run(task)

    return _run
