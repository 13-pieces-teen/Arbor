"""``arbor benchmark verify`` — the gate that decides whether a benchmark enters the zoo.

The machine-checkable contract lives in the README **front-matter** (no separate
manifest file): metric direction, the dev/test split mechanism, the expected baseline,
and the editable surface. That restores the checks that matter most — that dev/test are
provably disjoint, that the baseline number is honest, and that the harness is protected
— while all human prose (setup, license, baseline write-up, contamination) stays in the
README body and ``PROVENANCE.md``.

:func:`verify_pack` returns one :class:`VerifyResult` per check; the CLI exits non-zero
if any has ``status == "fail"``.

The score parser and shell runner mirror :func:`arbor.mcp.session_ops.parse_score` /
``_run_shell`` rather than importing them, to keep ``arbor.zoo`` dependency-light
(stdlib + PyYAML) and free of import cycles with the CLI.
"""

from __future__ import annotations

import fnmatch
import glob
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .pack import Contract, find_eval_entrypoint, load_contract

DEFAULT_EVAL_TIMEOUT = 600

# Fixed README body sections (keyword → label), verified by heading presence.
README_SECTIONS = (
    ("task", "Task & metric"),
    ("run", "Run the baseline"),
    ("optimize", "Optimize with Arbor"),
    ("provenance", "Provenance"),
)

# Required PROVENANCE.md headings.
PROVENANCE_HEADINGS = (
    ("source", "Source"),
    ("setup", "Setup & environment"),
    ("license", "Data source & license"),
    ("implementation", "Baseline implementation"),
    ("reproduction", "Baseline reproduction"),
    ("contamination", "Contamination assessment"),
    ("caveat", "Caveats"),
)

_SCORE_RE = re.compile(r"\bscore\s*[:=]\s*([-+]?\d+(?:\.\d+)?)", re.I)
_DIRECTIONS = {"maximize", "minimize"}


@dataclass
class VerifyResult:
    """One check outcome. Same shape as ``arbor.cli.preflight.CheckResult`` but defined
    here to keep ``arbor.zoo`` free of any dependency on ``arbor.cli``."""

    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    hint: str | None = None


# ── small reused helpers (mirrors of session_ops) ─────────────────────────────

def _parse_score(text: str) -> float | None:
    matches = _SCORE_RE.findall(text)
    return float(matches[-1]) if matches else None


def _run_shell(cmd: str, cwd: Path, timeout: int) -> tuple[int, str, bool]:
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), shell=True, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={**os.environ, "TERM": "dumb"},
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode or 0, out, False
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        return -1, out + f"\n[timed out after {timeout}s]", True


def _eval_command(ctx: "_Ctx", split: str) -> str | None:
    """Eval command for *split*: contract ``eval.cmd`` if set, else by convention."""
    cmd = ctx.contract.eval.get("cmd")
    if cmd:
        return f"{cmd.replace('{cwd}', str(ctx.pack_dir))} {split}"
    entry = find_eval_entrypoint(ctx.pack_dir)
    if entry == "eval.sh":
        return f'bash "{ctx.pack_dir / "eval.sh"}" {split}'
    if entry == "eval.py":
        py = os.environ.get("PYTHON", "python3")
        return f'{py} "{ctx.pack_dir / "eval.py"}" --split {split}'
    return None


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def _headings(md_text: str) -> list[str]:
    return [ln.lstrip("#").strip().lower()
            for ln in md_text.splitlines() if ln.lstrip().startswith("#")]


def _within_tol(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-9)


# ── verification context + checks ─────────────────────────────────────────────

@dataclass
class _Ctx:
    pack_dir: Path
    contract: Contract
    run_eval: bool
    timeout: int
    dev_score: float | None = None
    dev_score2: float | None = None
    test_score: float | None = None
    dev_rc: int = 0
    test_rc: int = 0
    eval_ran: bool = False


def _check_contract(ctx: _Ctx) -> VerifyResult:
    """Front-matter contract is present and its required fields are valid."""
    c = ctx.contract
    if not c.present:
        return VerifyResult(
            "contract", "fail", "README has no front-matter contract",
            "add a leading ---...--- YAML block — see docs/zoo.md",
        )
    missing: list[str] = []
    if not c.name:
        missing.append("name")
    if c.metric.get("direction") not in _DIRECTIONS:
        missing.append("metric.direction (maximize|minimize)")
    if not c.splits.get("kind"):
        missing.append("splits.kind")
    if not c.splits.get("dev") or not c.splits.get("test"):
        missing.append("splits.dev/test")
    if not isinstance(c.baseline.get("score"), (int, float)):
        missing.append("baseline.score")
    if not c.edit:
        missing.append("edit (editable files)")
    if missing:
        return VerifyResult(
            "contract", "fail",
            f"front-matter missing/invalid: {', '.join(missing)}",
            "see the front-matter schema in docs/zoo.md",
        )
    return VerifyResult("contract", "pass", "front-matter contract complete")


def _check_readme_sections(ctx: _Ctx) -> VerifyResult:
    _, body = _split_readme(ctx)
    heads = _headings(body)
    missing = [label for kw, label in README_SECTIONS if not any(kw in h for h in heads)]
    if missing:
        return VerifyResult("readme-sections", "fail",
                            f"README missing sections: {', '.join(missing)}",
                            "use the fixed section order from docs/zoo.md")
    return VerifyResult("readme-sections", "pass", "all fixed README sections present")


def _check_provenance(ctx: _Ctx) -> VerifyResult:
    prov = ctx.pack_dir / "PROVENANCE.md"
    if not prov.exists():
        return VerifyResult("provenance", "fail", "PROVENANCE.md missing",
                            "a benchmark without a provenance card is not trustworthy")
    heads = _headings(prov.read_text(encoding="utf-8"))
    missing = [label for kw, label in PROVENANCE_HEADINGS if not any(kw in h for h in heads)]
    if missing:
        return VerifyResult("provenance", "fail",
                            f"PROVENANCE missing sections: {', '.join(missing)}",
                            "baseline implementation + contamination assessment are mandatory")
    return VerifyResult("provenance", "pass", "all required PROVENANCE sections present")


def _check_splits_disjoint(ctx: _Ctx) -> VerifyResult:
    """dev/test provably disjoint — reasons about the declared split mechanism."""
    splits = ctx.contract.splits
    kind = splits.get("kind")
    dev, test = splits.get("dev"), splits.get("test")
    if kind == "seed_range":
        if not isinstance(dev, dict) or not isinstance(test, dict):
            return VerifyResult("splits-disjoint", "fail",
                                "seed_range dev/test must be mappings with base+count")
        try:
            dev_set = set(range(int(dev["base"]), int(dev["base"]) + int(dev["count"])))
            test_set = set(range(int(test["base"]), int(test["base"]) + int(test["count"])))
        except (KeyError, TypeError, ValueError) as exc:
            return VerifyResult("splits-disjoint", "fail", f"seed_range malformed: {exc}")
        overlap = dev_set & test_set
        if overlap:
            return VerifyResult("splits-disjoint", "fail",
                                f"dev/test seed ranges overlap on {sorted(overlap)}",
                                "held-out test must not share seeds with dev")
        return VerifyResult("splits-disjoint", "pass",
                            f"seed ranges disjoint (dev {len(dev_set)}, test {len(test_set)})")
    if kind == "path":
        def expand(globs: Any) -> set[str]:
            out: set[str] = set()
            for g in globs or []:
                for m in glob.glob(g, root_dir=str(ctx.pack_dir), recursive=True):
                    if (ctx.pack_dir / m).is_file():
                        out.add(m)
            return out
        dev_files, test_files = expand(dev), expand(test)
        path_overlap = dev_files & test_files
        if path_overlap:
            return VerifyResult("splits-disjoint", "fail",
                                f"dev/test path globs share files: {sorted(path_overlap)[:5]}")
        if not dev_files or not test_files:
            return VerifyResult("splits-disjoint", "fail",
                                "path splits matched no files on one side")
        return VerifyResult("splits-disjoint", "pass",
                            f"path splits disjoint (dev {len(dev_files)}, test {len(test_files)})")
    return VerifyResult("splits-disjoint", "fail", f"unknown splits.kind: {kind!r}",
                        "splits.kind must be 'seed_range' or 'path'")


def _check_edit_surface(ctx: _Ctx) -> VerifyResult:
    """The declared editable files exist; the harness/data are not editable."""
    patterns = ctx.contract.edit
    # Every edit glob must match at least one existing file.
    unmatched = [
        g for g in patterns
        if not glob.glob(g, root_dir=str(ctx.pack_dir), recursive=True)
    ]
    if unmatched:
        return VerifyResult("edit-surface", "fail",
                            f"edit patterns match no files: {', '.join(unmatched)}",
                            "list the baseline file(s) Arbor may change")
    # The harness and data must NOT be editable.
    must_protect = [f for f in ("eval.sh", "eval.py", "task.py") if (ctx.pack_dir / f).exists()]
    if (ctx.pack_dir / "data").is_dir():
        must_protect.append("data/_probe")
    leaked = [f for f in must_protect if _matches_any(f, patterns)]
    if leaked:
        return VerifyResult("edit-surface", "fail",
                            f"editable surface includes protected files: {', '.join(leaked)}",
                            "the eval harness, ground truth, and data must stay protected")
    return VerifyResult("edit-surface", "pass", "editable surface declared; harness protected")


def _run_evals(ctx: _Ctx) -> None:
    if not ctx.run_eval:
        return
    dev_cmd, test_cmd = _eval_command(ctx, "dev"), _eval_command(ctx, "test")
    if not dev_cmd or not test_cmd:
        return
    ctx.eval_ran = True
    ctx.dev_rc, dev_out, _ = _run_shell(dev_cmd, ctx.pack_dir, ctx.timeout)
    ctx.dev_score = _parse_score(dev_out)
    _, out2, _ = _run_shell(dev_cmd, ctx.pack_dir, ctx.timeout)
    ctx.dev_score2 = _parse_score(out2)
    ctx.test_rc, test_out, _ = _run_shell(test_cmd, ctx.pack_dir, ctx.timeout)
    ctx.test_score = _parse_score(test_out)


def _check_eval_dev(ctx: _Ctx) -> VerifyResult:
    if not ctx.eval_ran:
        return VerifyResult("eval-dev", "warn", "eval not run (run_eval=False)")
    if ctx.dev_rc != 0 or ctx.dev_score is None:
        return VerifyResult("eval-dev", "fail", f"eval dev rc={ctx.dev_rc}, score={ctx.dev_score}",
                            "eval must exit 0 and print one `score: <float>` line")
    return VerifyResult("eval-dev", "pass", f"dev score parsed: {ctx.dev_score}")


def _check_eval_test(ctx: _Ctx) -> VerifyResult:
    if not ctx.eval_ran:
        return VerifyResult("eval-test", "warn", "eval not run (run_eval=False)")
    if ctx.test_rc != 0 or ctx.test_score is None:
        return VerifyResult("eval-test", "fail", f"eval test rc={ctx.test_rc}, score={ctx.test_score}",
                            "the held-out test split must also print a parseable score")
    return VerifyResult("eval-test", "pass", f"test score parsed: {ctx.test_score}")


def _check_baseline(ctx: _Ctx) -> VerifyResult:
    """The bundled baseline reproduces the declared score within tolerance."""
    if not ctx.eval_ran:
        return VerifyResult("baseline-reproduces", "warn", "eval not run (run_eval=False)")
    if ctx.dev_score is None:
        return VerifyResult("baseline-reproduces", "fail", "no dev score to compare")
    declared = ctx.contract.baseline.get("score")
    if not isinstance(declared, (int, float)):
        return VerifyResult("baseline-reproduces", "fail", f"baseline.score not numeric: {declared!r}")
    tol = float(ctx.contract.baseline.get("tolerance", 0.0))
    if not _within_tol(ctx.dev_score, float(declared), tol):
        return VerifyResult("baseline-reproduces", "fail",
                            f"dev score {ctx.dev_score} not within {tol:.0%} of declared {declared}",
                            "the declared baseline must match what the bundled solution prints")
    return VerifyResult("baseline-reproduces", "pass",
                        f"dev score {ctx.dev_score} matches declared baseline {declared} (±{tol:.0%})")


def _check_determinism(ctx: _Ctx) -> VerifyResult:
    """Two dev runs agree. Timing metrics use tolerance + a >0 correctness invariant;
    other metrics require exact equality."""
    if not ctx.eval_ran:
        return VerifyResult("determinism", "warn", "eval not run (run_eval=False)")
    s1, s2 = ctx.dev_score, ctx.dev_score2
    if s1 is None or s2 is None:
        return VerifyResult("determinism", "fail", f"a dev run produced no score ({s1}, {s2})")
    if ctx.contract.baseline.get("kind") == "timing":
        if s1 <= 0 or s2 <= 0:
            return VerifyResult("determinism", "fail",
                                f"a dev run failed the correctness gate (scores {s1}, {s2})")
        tol = float(ctx.contract.baseline.get("tolerance", 0.0))
        if not _within_tol(s1, s2, tol):
            return VerifyResult("determinism", "fail",
                                f"dev scores diverge beyond {tol:.0%}: {s1} vs {s2}",
                                "widen baseline.tolerance or pin threads if this is timing noise")
        return VerifyResult("determinism", "pass", f"two timing runs agree ({s1} ≈ {s2})")
    if s1 != s2:
        return VerifyResult("determinism", "fail", f"non-timing metric not reproducible: {s1} vs {s2}",
                            "a deterministic eval must return the same score every run")
    return VerifyResult("determinism", "pass", f"two runs identical ({s1})")


def _check_contamination(ctx: _Ctx) -> VerifyResult:
    return VerifyResult("contamination", "warn",
                        "contamination assessment present — requires human acceptance, never auto-accepted",
                        "a maintainer must confirm the test set isn't pre-trained on")


# README body is parsed once and cached on the context via a module helper.
def _split_readme(ctx: _Ctx) -> tuple[dict[str, Any] | None, str]:
    from .pack import read_front_matter
    return read_front_matter(ctx.pack_dir / "README.md")


_STRUCTURAL_CHECKS: tuple[Callable[[_Ctx], VerifyResult], ...] = (
    _check_contract,
    _check_readme_sections,
    _check_provenance,
    _check_splits_disjoint,
    _check_edit_surface,
    _check_contamination,
)
_EVAL_CHECKS: tuple[Callable[[_Ctx], VerifyResult], ...] = (
    _check_eval_dev,
    _check_eval_test,
    _check_baseline,
    _check_determinism,
)


def verify_pack(
    pack_dir: Path,
    *,
    run_eval: bool = True,
    timeout: int = DEFAULT_EVAL_TIMEOUT,
) -> list[VerifyResult]:
    """Verify the benchmark in *pack_dir*. Returns one :class:`VerifyResult` per check.

    Set ``run_eval=False`` to skip the four eval-running checks (they become ``warn``).
    """
    pack_dir = pack_dir.resolve()
    ctx = _Ctx(pack_dir=pack_dir, contract=load_contract(pack_dir),
               run_eval=run_eval, timeout=timeout)

    def _safe(check: Callable[[_Ctx], VerifyResult]) -> VerifyResult:
        try:
            return check(ctx)
        except Exception as exc:  # noqa: BLE001 — a check bug must not crash verify
            return VerifyResult(check.__name__, "fail", f"check raised: {exc}")

    results = [_safe(c) for c in _STRUCTURAL_CHECKS]
    _run_evals(ctx)
    results += [_safe(c) for c in _EVAL_CHECKS]
    return results
