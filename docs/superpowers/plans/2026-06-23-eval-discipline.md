# Evaluation Discipline (§1.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Arbor's evaluation trustworthy — tamper-evident protected paths, split-tagged scores surfaced everywhere, and a non-blocking contamination check.

**Architecture:** A pure `integrity` module (SHA-256 manifest + best-effort OS read-only) wired into the executor worktree lifecycle so uncommitted tampering invalidates the dev score; two new `Node` fields carry split provenance recorded at executor + merge time and rendered in REPORT/dashboard/WebUI; a `contamination` module (declarative heuristic + canary scan working, LLM/web probes stubbed) surfaced in preflight and at coordinator INIT.

**Tech Stack:** Python 3.11+, pydantic v2 config, pytest, asyncio, git worktrees.

## Global Constraints

- Python ≥ 3.11; `from __future__ import annotations` at the top of every new module (matches the codebase).
- Cross-platform: code runs on Windows (dev) and POSIX (CI/runs). No POSIX-only calls without a guarded fallback.
- All new event-emitting/IO paths must **never raise into the run loop** — wrap in `try/except` + log a warning (matches existing `executor_run.py` hook handling).
- Backward compatibility: old `idea_tree.json` files must load unchanged. New `Node` fields default and are omitted from `to_dict` when at default.
- Follow existing patterns: tools/helpers are module-level `async def _name(...)`; git via `_run_git(cmd, cwd, timeout=60) -> tuple[str, int]`.
- Commit message footer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 1: `integrity` module — manifest + best-effort read-only

**Files:**
- Create: `src/coordinator/tools/integrity.py`
- Test: `tests/test_integrity.py`

**Interfaces:**
- Produces:
  - `build_protected_manifest(root: Path, protected_paths: list[str]) -> dict[str, str]` — `{posix_relpath: sha256_hex}`.
  - `@dataclass(frozen=True) ProtectedChange` with `path: str`, `kind: Literal["modified","added","removed"]`.
  - `verify_protected_manifest(root: Path, protected_paths: list[str], manifest: dict[str, str]) -> list[ProtectedChange]`.
  - `apply_readonly(root: Path, protected_paths: list[str]) -> None` and `clear_readonly(root: Path, protected_paths: list[str]) -> None`.
  - `iter_protected_files(root: Path, protected_paths: list[str]) -> Iterator[Path]` (internal helper, exported for tests).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integrity.py
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from src.coordinator.tools.integrity import (
    apply_readonly,
    build_protected_manifest,
    clear_readonly,
    verify_protected_manifest,
)


def _make_tree(root: Path) -> None:
    (root / "data").mkdir(parents=True)
    (root / "data" / "train.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "data" / "test.csv").write_text("a,b\n3,4\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "model.py").write_text("print('hi')\n", encoding="utf-8")


def test_manifest_covers_only_protected_globs(tmp_path: Path):
    _make_tree(tmp_path)
    manifest = build_protected_manifest(tmp_path, ["data/**"])
    assert set(manifest) == {"data/train.csv", "data/test.csv"}
    assert all(len(h) == 64 for h in manifest.values())


def test_manifest_is_deterministic(tmp_path: Path):
    _make_tree(tmp_path)
    assert build_protected_manifest(tmp_path, ["data/**"]) == build_protected_manifest(
        tmp_path, ["data/**"]
    )


def test_verify_detects_modify_add_remove(tmp_path: Path):
    _make_tree(tmp_path)
    manifest = build_protected_manifest(tmp_path, ["data/**"])
    # modify
    (tmp_path / "data" / "train.csv").write_text("a,b\n9,9\n", encoding="utf-8")
    # add
    (tmp_path / "data" / "leak.csv").write_text("x\n", encoding="utf-8")
    # remove
    (tmp_path / "data" / "test.csv").unlink()
    changes = verify_protected_manifest(tmp_path, ["data/**"], manifest)
    by_path = {c.path: c.kind for c in changes}
    assert by_path == {
        "data/train.csv": "modified",
        "data/leak.csv": "added",
        "data/test.csv": "removed",
    }


def test_verify_clean_returns_empty(tmp_path: Path):
    _make_tree(tmp_path)
    manifest = build_protected_manifest(tmp_path, ["data/**"])
    assert verify_protected_manifest(tmp_path, ["data/**"], manifest) == []


def test_readonly_roundtrip_never_raises_and_restores(tmp_path: Path):
    _make_tree(tmp_path)
    apply_readonly(tmp_path, ["data/**"])  # must not raise
    clear_readonly(tmp_path, ["data/**"])  # must not raise
    # after clearing, the file is writable again
    (tmp_path / "data" / "train.csv").write_text("a,b\n5,5\n", encoding="utf-8")


def test_apply_readonly_on_missing_path_is_noop(tmp_path: Path):
    apply_readonly(tmp_path, ["does/not/exist/**"])  # must not raise
    clear_readonly(tmp_path, ["does/not/exist/**"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .claude/worktrees/feat+eval-discipline && python -m pytest tests/test_integrity.py -q`
Expected: FAIL — `ModuleNotFoundError: src.coordinator.tools.integrity`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/coordinator/tools/integrity.py
"""Integrity guard for protected paths.

Pure helpers (no git): build a SHA-256 manifest of the files matched by a set
of protected globs, verify a worktree against that manifest, and best-effort
mark those files read-only. The manifest is the portable tamper-detection
guarantee; read-only is opportunistic prevention (strong on POSIX, weak on
Windows) and every OS operation is wrapped so it can never fail a run.
"""

from __future__ import annotations

import hashlib
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

log = logging.getLogger(__name__)

_CHUNK = 1 << 20  # 1 MiB


def iter_protected_files(root: Path, protected_paths: list[str]) -> Iterator[Path]:
    """Yield every existing file under *root* matching any protected glob.

    Globs are interpreted relative to *root* (e.g. ``data/**``). Directories
    and symlinks-to-dirs are skipped; only regular files are yielded. Order is
    sorted for determinism. Duplicate matches are de-duplicated.
    """
    seen: set[Path] = set()
    for pattern in protected_paths:
        for path in sorted(root.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            yield path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def build_protected_manifest(root: Path, protected_paths: list[str]) -> dict[str, str]:
    """Map ``posix-relpath -> sha256`` for every protected file under *root*."""
    manifest: dict[str, str] = {}
    for path in iter_protected_files(root, protected_paths):
        rel = path.relative_to(root).as_posix()
        manifest[rel] = _sha256(path)
    return manifest


@dataclass(frozen=True)
class ProtectedChange:
    path: str
    kind: Literal["modified", "added", "removed"]


def verify_protected_manifest(
    root: Path, protected_paths: list[str], manifest: dict[str, str]
) -> list[ProtectedChange]:
    """Return the changes between *manifest* and the current files under *root*."""
    current = build_protected_manifest(root, protected_paths)
    changes: list[ProtectedChange] = []
    for rel, digest in current.items():
        if rel not in manifest:
            changes.append(ProtectedChange(rel, "added"))
        elif manifest[rel] != digest:
            changes.append(ProtectedChange(rel, "modified"))
    for rel in manifest:
        if rel not in current:
            changes.append(ProtectedChange(rel, "removed"))
    return sorted(changes, key=lambda c: c.path)


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError as exc:  # pragma: no cover - platform dependent
        log.warning("integrity: chmod failed on %s: %s", path, exc)


def apply_readonly(root: Path, protected_paths: list[str]) -> None:
    """Best-effort: make protected files read-only. Never raises."""
    for path in iter_protected_files(root, protected_paths):
        _chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def clear_readonly(root: Path, protected_paths: list[str]) -> None:
    """Best-effort: restore writability so cleanup never fails. Never raises."""
    for path in iter_protected_files(root, protected_paths):
        _chmod(path, stat.S_IWRITE | stat.S_IREAD)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_integrity.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/coordinator/tools/integrity.py tests/test_integrity.py
git commit -m "feat(integrity): protected-path manifest + best-effort read-only

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Config fields + protected-path resolver

**Files:**
- Modify: `src/coordinator/config.py:431-435` (Evaluation block)
- Create: `src/coordinator/tools/protected.py`
- Test: `tests/test_protected_resolve.py`

**Interfaces:**
- Consumes: `Plugin.protected_paths` (`src/plugins/base.py`), `IdeaTree.meta` dict.
- Produces:
  - New `CoordinatorConfig` fields: `enforce_protected: bool = True`, `protected_paths: list[str] = []`, `contamination_probe: bool = True`, `contamination_timeout: int = 60`.
  - `resolve_protected_paths(config, plugin, meta) -> list[str]` in `protected.py` — union of `config.protected_paths`, `plugin.protected_paths` (if plugin), and `meta.get("protected_paths", [])`, de-duplicated, order-stable.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_protected_resolve.py
from __future__ import annotations

from src.coordinator.tools.protected import resolve_protected_paths


class _Plugin:
    def __init__(self, paths):
        self.protected_paths = paths


class _Cfg:
    def __init__(self, paths):
        self.protected_paths = paths


def test_union_dedup_order_stable():
    cfg = _Cfg(["a/**", "b/**"])
    plugin = _Plugin(["b/**", "c/**"])
    meta = {"protected_paths": ["c/**", "d/**"]}
    assert resolve_protected_paths(cfg, plugin, meta) == ["a/**", "b/**", "c/**", "d/**"]


def test_handles_none_plugin_and_missing_meta():
    cfg = _Cfg(["x/**"])
    assert resolve_protected_paths(cfg, None, {}) == ["x/**"]


def test_empty_everywhere():
    assert resolve_protected_paths(_Cfg([]), None, {}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_protected_resolve.py -q`
Expected: FAIL — `ModuleNotFoundError: src.coordinator.tools.protected`.

- [ ] **Step 3: Write minimal implementation**

Create `src/coordinator/tools/protected.py`:

```python
"""Resolve the effective protected-path set from config + plugin + tree meta."""

from __future__ import annotations

from typing import Any


def resolve_protected_paths(config: Any, plugin: Any, meta: dict[str, Any]) -> list[str]:
    """Union of config, plugin, and tree-meta protected globs (order-stable)."""
    out: list[str] = []
    seen: set[str] = set()
    sources = [
        getattr(config, "protected_paths", None) or [],
        (getattr(plugin, "protected_paths", None) or []) if plugin else [],
        meta.get("protected_paths") or [],
    ]
    for source in sources:
        for pattern in source:
            if pattern not in seen:
                seen.add(pattern)
                out.append(pattern)
    return out
```

Add the config fields. In `src/coordinator/config.py`, replace the Evaluation block:

```python
    # ── Evaluation ───────────────────────────────────────────────────
    merge_threshold: float = 5.0  # soft guideline for the LLM
    eval_retries: int = 1  # extra B_test attempts after a transient failure
    eval_retry_base_delay: float = 5.0
    eval_retry_max_delay: float = 30.0
    # Tamper-proofing: hash protected paths at worktree creation and verify
    # before trusting a dev score; best-effort OS read-only on top.
    enforce_protected: bool = True
    protected_paths: list[str] = PydField(default_factory=list)
    # Contamination check (non-blocking; auto-falls-back to declarative).
    contamination_probe: bool = True
    contamination_timeout: int = 60
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_protected_resolve.py -q && python -c "from src.coordinator.config import CoordinatorConfig; c=CoordinatorConfig(); print(c.enforce_protected, c.protected_paths, c.contamination_probe, c.contamination_timeout)"`
Expected: tests PASS; print → `True [] True 60`.

- [ ] **Step 5: Commit**

```bash
git add src/coordinator/config.py src/coordinator/tools/protected.py tests/test_protected_resolve.py
git commit -m "feat(config): eval-discipline knobs + protected-path resolver

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: New event types

**Files:**
- Modify: `src/events/types.py` (Evaluation section)
- Test: `tests/test_eval_events.py`

**Interfaces:**
- Produces: `PROTECTED_TAMPER = "eval.protected_tamper"`, `CONTAMINATION_ASSESSED = "eval.contamination_assessed"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eval_events.py
from src.events import types as ev


def test_new_event_constants_present_and_stable():
    assert ev.PROTECTED_TAMPER == "eval.protected_tamper"
    assert ev.CONTAMINATION_ASSESSED == "eval.contamination_assessed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_eval_events.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'PROTECTED_TAMPER'`.

- [ ] **Step 3: Write minimal implementation**

In `src/events/types.py`, after the `EVAL_END` line, add:

```python
# Emitted when a protected path was changed during a run (manifest mismatch);
# the node's dev score is invalidated and the branch becomes merge-ineligible.
PROTECTED_TAMPER = "eval.protected_tamper"   # {node_id, branch, changes}
# Emitted once at INIT with the contamination assessment for the benchmark.
CONTAMINATION_ASSESSED = "eval.contamination_assessed"  # {status, reasons}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_eval_events.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/events/types.py tests/test_eval_events.py
git commit -m "feat(events): protected-tamper + contamination-assessed events

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Wire tamper-proofing into the executor lifecycle

**Files:**
- Modify: `src/coordinator/tools/executor_run.py` (`_run_executor`, ~lines 444-529)
- Test: `tests/test_executor_tamper.py`

**Interfaces:**
- Consumes: Task 1 (`build_protected_manifest`, `verify_protected_manifest`, `apply_readonly`, `clear_readonly`), Task 2 (`resolve_protected_paths`, `config.enforce_protected`), Task 3 (`ev.PROTECTED_TAMPER`).
- Produces: helper `_guard_protected(config, tree, worktree_path) -> list[str]` (build manifest + apply RO; returns the resolved path set) and `_check_tamper(config, tree, worktree_path, paths, manifest, node_id, branch) -> list[ProtectedChange]` (clear RO + verify + emit + return changes). Both no-ops when `enforce_protected` is false or the path set is empty.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_executor_tamper.py
from __future__ import annotations

from pathlib import Path

import pytest

from src.coordinator.tools.executor_run import _check_tamper, _guard_protected


class _Cfg:
    enforce_protected = True
    protected_paths: list[str] = []
    plugin = None


class _Tree:
    def __init__(self):
        self.meta = {"protected_paths": ["data/**"]}
        self.events = []

        class _Bus:
            def __init__(self, sink):
                self._sink = sink

            def emit(self, name, payload):
                self._sink.append((name, payload))

        self.bus = _Bus(self.events)


def test_guard_then_clean_check_returns_no_changes(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "train.csv").write_text("a\n1\n", encoding="utf-8")
    cfg, tree = _Cfg(), _Tree()
    paths, manifest = _guard_protected(cfg, tree, tmp_path)
    assert paths == ["data/**"]
    changes = _check_tamper(cfg, tree, tmp_path, paths, manifest, "1", "branch-x")
    assert changes == []
    assert tree.events == []  # no tamper event on clean run


def test_tamper_is_detected_and_emitted(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "train.csv").write_text("a\n1\n", encoding="utf-8")
    cfg, tree = _Cfg(), _Tree()
    paths, manifest = _guard_protected(cfg, tree, tmp_path)
    (tmp_path / "data" / "train.csv").write_text("a\n9999\n", encoding="utf-8")
    changes = _check_tamper(cfg, tree, tmp_path, paths, manifest, "1", "branch-x")
    assert [c.path for c in changes] == ["data/train.csv"]
    assert tree.events and tree.events[0][0] == "eval.protected_tamper"
    assert tree.events[0][1]["node_id"] == "1"


def test_disabled_enforcement_is_noop(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "train.csv").write_text("a\n1\n", encoding="utf-8")
    cfg, tree = _Cfg(), _Tree()
    cfg.enforce_protected = False
    paths, manifest = _guard_protected(cfg, tree, tmp_path)
    assert paths == [] and manifest == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_executor_tamper.py -q`
Expected: FAIL — `ImportError: cannot import name '_guard_protected'`.

- [ ] **Step 3: Write minimal implementation**

At the top of `executor_run.py`, add imports near the other `.worktree` import:

```python
from .integrity import (
    apply_readonly,
    build_protected_manifest,
    clear_readonly,
    verify_protected_manifest,
)
from .protected import resolve_protected_paths
```

Add the two helpers (place them just above `async def _run_executor`):

```python
def _guard_protected(config, tree, worktree_path: Path):
    """Snapshot + lock protected paths in a fresh worktree.

    Returns (resolved_paths, manifest). Both empty when enforcement is off or
    no protected paths are configured. Never raises.
    """
    if not getattr(config, "enforce_protected", True):
        return [], {}
    paths = resolve_protected_paths(config, getattr(config, "plugin", None), tree.meta)
    if not paths:
        return [], {}
    try:
        manifest = build_protected_manifest(worktree_path, paths)
        apply_readonly(worktree_path, paths)
        return paths, manifest
    except Exception as exc:  # noqa: BLE001
        log.warning("integrity: failed to guard protected paths: %s", exc)
        return [], {}


def _check_tamper(config, tree, worktree_path: Path, paths, manifest, node_id: str, branch: str):
    """Clear read-only + verify the manifest. Emits PROTECTED_TAMPER on change."""
    if not paths:
        return []
    from ...events import types as ev

    clear_readonly(worktree_path, paths)
    try:
        changes = verify_protected_manifest(worktree_path, paths, manifest)
    except Exception as exc:  # noqa: BLE001
        log.warning("integrity: verify failed (treating as clean): %s", exc)
        return []
    if changes:
        tree.bus.emit(ev.PROTECTED_TAMPER, {
            "node_id": node_id,
            "branch": branch,
            "changes": [{"path": c.path, "kind": c.kind} for c in changes],
        })
        log.warning(
            "integrity: node %s tampered with protected paths: %s",
            node_id, ", ".join(f"{c.path}({c.kind})" for c in changes),
        )
    return changes
```

Wire into `_run_executor`. After a successful `_create_worktree` (right after the `EXECUTOR_START` emit, ~line 458), capture the guard:

```python
    protected_paths, protected_manifest = _guard_protected(config, tree, worktree_path)
```

In the finalize block, **before** `_finalize_worktree` (line 479), add the tamper check:

```python
    tamper_changes = _check_tamper(
        config, tree, worktree_path, protected_paths, protected_manifest,
        node_id, actual_branch,
    )
```

Then, where the score is resolved (after `score = parsed.get("score")`, line 504), invalidate on tamper:

```python
    if tamper_changes:
        score = None
        eval_status = "tampered"
        insight_override = (
            "Protected path(s) modified during the run: "
            + ", ".join(f"{c.path}({c.kind})" for c in tamper_changes)
            + ". Dev score discarded; branch is not mergeable."
        )
    else:
        insight_override = ""
```

In the `tree.async_update_node(...)` call (line 519), add `score_split="dev"` (the field lands in Task 5) and prefer the override insight:

```python
    await tree.async_update_node(
        node_id,
        status=new_status,
        score=score,
        score_split="dev",
        insight=insight_override or insight or ("Timed out" if raw_report.startswith("[Timed out") else ""),
        result=result_text or raw_report[:300],
        code_ref=code_ref,
        eval_status=eval_status,
        stop_reason=stop_reason,
        attempt=attempt,
    )
```

> Note: `_classify_executor_outcome` already maps `score=None` to `needs_retry`, so a tampered node becomes `needs_retry` with no score — exactly the intent. `score_split` is accepted now because Task 5 adds it to `MUTABLE_FIELDS`; sequence Task 5 before running the full suite, or land both before the integration test in Step 4.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_executor_tamper.py -q`
Expected: PASS (3 passed). (The helper tests don't touch `async_update_node`, so they pass independently of Task 5.)

- [ ] **Step 5: Commit**

```bash
git add src/coordinator/tools/executor_run.py tests/test_executor_tamper.py
git commit -m "feat(executor): tamper-evident protected paths invalidate dev score

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `Node` split-provenance fields + recording

**Files:**
- Modify: `src/coordinator/idea_tree.py:42-117` (`Node`)
- Modify: `src/coordinator/tools/git_ops.py` (`GitMergeBranch.execute`, after successful merge ~line 540)
- Test: `tests/test_idea_tree.py` (extend)

**Interfaces:**
- Consumes: Task 4 passes `score_split="dev"` into `async_update_node`.
- Produces: `Node.score_split: str = "dev"`, `Node.test_score: float | None = None`, both in `MUTABLE_FIELDS`, `to_dict`, `from_dict`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_idea_tree.py
from src.coordinator.idea_tree import Node


def test_node_roundtrips_split_fields():
    n = Node(id="1", parent_id="ROOT", score=42.0, score_split="dev", test_score=40.0)
    d = n.to_dict()
    assert d["score_split"] == "dev"
    assert d["test_score"] == 40.0
    back = Node.from_dict(d)
    assert back.score_split == "dev"
    assert back.test_score == 40.0


def test_old_node_dict_defaults_split_fields():
    # a node persisted before this feature has neither key
    back = Node.from_dict({"id": "1", "parent_id": "ROOT", "score": 10.0})
    assert back.score_split == "dev"
    assert back.test_score is None


def test_default_split_omitted_from_dict():
    n = Node(id="1", parent_id="ROOT")  # no score
    d = n.to_dict()
    assert "score_split" not in d  # omitted when there is no score
    assert "test_score" not in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_idea_tree.py -k split -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'score_split'`.

- [ ] **Step 3: Write minimal implementation**

In `Node` (after `score: float | None = None`, line 42):

```python
    score: float | None = None  # Absolute score (e.g. 45.2%)
    score_split: str = "dev"  # which split `score` came from: "dev" | "test"
    test_score: float | None = None  # verified B_test score, set at merge
```

Add to `MUTABLE_FIELDS` (after `"score",`):

```python
        "score",
        "score_split",
        "test_score",
```

In `to_dict`, after the `if self.score is not None:` block:

```python
        if self.score is not None:
            d["score"] = self.score
            if self.score_split != "dev":
                d["score_split"] = self.score_split
        if self.test_score is not None:
            d["test_score"] = self.test_score
```

> The `score_split` key is only written when non-default to keep diffs small; `test_node_roundtrips_split_fields` sets a `test_score` and keeps `score_split="dev"`, so adjust that assertion: when `score_split == "dev"` it is omitted. Update the test accordingly:
> ```python
>     assert d.get("score_split", "dev") == "dev"
> ```

In `from_dict`, after `score=...`:

```python
            score=data.get("score", data.get("score_delta")),
            score_split=data.get("score_split", "dev"),
            test_score=data.get("test_score"),
```

In `git_ops.py` `GitMergeBranch.execute`, after the merge succeeds and `test_score` is known (just before building the `result` string ~line 549), record the verified test score on the node and trunk meta:

```python
        try:
            await self._tree.async_update_node(node_id, test_score=test_score, status="merged")
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to record test_score on node %s: %s", node_id, exc)
        self._tree.meta["test_trunk_score"] = test_score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_idea_tree.py -q`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/coordinator/idea_tree.py src/coordinator/tools/git_ops.py tests/test_idea_tree.py
git commit -m "feat(tree): split-tagged scores; record verified test_score at merge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Render split provenance (REPORT, dashboard, WebUI)

**Files:**
- Modify: `src/run.py` (per-node rendering in the report builder, ~lines 247-260)
- Modify: `src/webui/snapshot.py:80` (node record serialization)
- Modify: `src/cli/run_dashboard.py:1309-1312` (per-node row) and `:1322-1327` (baseline/trunk → add test)
- Test: `tests/test_split_render.py`

**Interfaces:**
- Consumes: Task 5 (`Node.score_split`, `Node.test_score`, `meta.test_trunk_score`).
- Produces: a small pure helper `format_score_with_split(score, split) -> str` in `src/report/generator.py` reused by REPORT rendering.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_split_render.py
from src.report.generator import format_score_with_split


def test_format_dev_and_test():
    assert format_score_with_split(45.2, "dev") == "45.2 (dev)"
    assert format_score_with_split(40.0, "test") == "40.0 (test)"


def test_format_none_score():
    assert format_score_with_split(None, "dev") == "—"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_split_render.py -q`
Expected: FAIL — `ImportError: cannot import name 'format_score_with_split'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/report/generator.py` (module level):

```python
def format_score_with_split(score: float | None, split: str = "dev") -> str:
    """Render a score tagged with the split it came from, e.g. ``45.2 (dev)``."""
    if score is None:
        return "—"
    return f"{score:.1f} ({split})"
```

In `src/run.py`, where per-node scores are rendered in the report, import and use it. For each node line that prints a score, wrap with the node's split:

```python
    from .report.generator import format_score_with_split
    # ... where a node's score is printed:
    score_str = format_score_with_split(node.get("score"), node.get("score_split", "dev"))
```

(Apply at every node-score render site in `_render_*` of `run.py`; the headline already separates dev/test and stays as-is.)

In `src/webui/snapshot.py`, extend the per-node record (line ~80) to carry the split and test score:

```python
        "score": rec.score,
        "score_split": getattr(rec, "score_split", "dev"),
        "test_score": getattr(rec, "test_score", None),
```

In `src/cli/run_dashboard.py`, the per-node row (line ~1309):

```python
            split = getattr(rec, "score_split", "dev")
            score = f" {rec.score:.4f} ({split})" if rec.score is not None else ""
```

And add the trunk test score next to the dev trunk score (after line 1327):

```python
        test_trunk = getattr(s, "test_trunk_score", None)
        trunk_test_str = (
            f"[dim]trunk·test[/] {test_trunk:.4f}" if test_trunk is not None else ""
        )
```

(Append `trunk_test_str` to the same meta line the existing `trunk` value is rendered on. If `RunState`/`s` has no `test_trunk_score` attribute, read it from the tree meta the dashboard already loads — grep `trunk_score` in `run_dashboard.py` to find the source struct and mirror it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_split_render.py -q && python -m pytest tests/test_run_dashboard_helpers.py tests/test_webui_session.py -q`
Expected: PASS (new test + existing dashboard/webui tests still green).

- [ ] **Step 5: Commit**

```bash
git add src/report/generator.py src/run.py src/webui/snapshot.py src/cli/run_dashboard.py tests/test_split_render.py
git commit -m "feat(report): label every score with its split (dev/test)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `contamination` module (declarative + canary working, probes stubbed)

**Files:**
- Create: `src/coordinator/contamination.py`
- Test: `tests/test_contamination.py`

**Interfaces:**
- Produces:
  - `@dataclass ContaminationReport` — `status: Literal["clean","warn","contaminated","unknown"]`, `reasons: list[str]`, `signals: dict[str, Any]`.
  - `scan_canaries(outputs: Iterable[str], canaries: list[str]) -> list[str]` — returns canaries found.
  - `declarative_assess(contamination: dict, model: str | None) -> ContaminationReport`.
  - `class ContaminationProbe` with `async assess(*, dataset_info, eval_contract, model=None, outputs=(), provider=None, search_tool=None, timeout=60.0) -> ContaminationReport`.
  - `_MODEL_CUTOFFS: dict[str, str]` (best-effort ISO cutoff dates).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contamination.py
from __future__ import annotations

import asyncio

import pytest

from src.coordinator.contamination import (
    ContaminationProbe,
    ContaminationReport,
    declarative_assess,
    scan_canaries,
)


def test_scan_canaries_finds_planted_string():
    found = scan_canaries(["...BENCHMARK-CANARY-XYZ appears here..."], ["BENCHMARK-CANARY-XYZ"])
    assert found == ["BENCHMARK-CANARY-XYZ"]


def test_scan_canaries_clean():
    assert scan_canaries(["nothing to see"], ["CANARY"]) == []


def test_declarative_public_dataset_warns():
    report = declarative_assess({"is_public": True}, model="claude-sonnet-4-20250514")
    assert report.status in {"warn", "contaminated"}
    assert report.reasons


def test_declarative_no_signal_is_unknown():
    report = declarative_assess({}, model=None)
    assert report.status == "unknown"


def test_probe_canary_hit_is_contaminated():
    probe = ContaminationProbe()
    report = asyncio.run(probe.assess(
        dataset_info="titanic",
        eval_contract={"contamination": {"canaries": ["LEAK-1"]}},
        outputs=["my output contains LEAK-1"],
        timeout=5.0,
    ))
    assert report.status == "contaminated"


def test_probe_never_raises_on_timeout(monkeypatch):
    probe = ContaminationProbe()

    async def _slow(*a, **k):
        await asyncio.sleep(10)

    monkeypatch.setattr(probe, "_llm_membership_probe", _slow)
    report = asyncio.run(probe.assess(
        dataset_info="x",
        eval_contract={"contamination": {"is_public": True}},
        model="claude-sonnet-4-20250514",
        provider=object(),  # truthy → would trigger the (stubbed/slow) probe
        timeout=0.2,
    ))
    # falls back to declarative; never raises
    assert report.status in {"warn", "contaminated", "unknown"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contamination.py -q`
Expected: FAIL — `ModuleNotFoundError: src.coordinator.contamination`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/coordinator/contamination.py
"""Contamination assessment — is the benchmark's test set already in pretraining?

Two layers. The declarative heuristic + canary scan are fully implemented and
deterministic. The LLM membership-inference and web-search probes are stubbed
behind the interface (return no signal) and are a follow-up. The whole thing is
non-blocking: any error or timeout degrades to the declarative result and never
raises into the run loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Literal

log = logging.getLogger(__name__)

Status = Literal["clean", "warn", "contaminated", "unknown"]

# Best-effort model knowledge-cutoff dates (ISO). Unknown models → no date signal.
_MODEL_CUTOFFS: dict[str, str] = {
    "claude-sonnet-4-20250514": "2025-03-01",
    "claude-opus-4-8": "2026-01-01",
    "gpt-4o": "2023-10-01",
}


@dataclass
class ContaminationReport:
    status: Status = "unknown"
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reasons": list(self.reasons), "signals": dict(self.signals)}


def scan_canaries(outputs: Iterable[str], canaries: list[str]) -> list[str]:
    """Return the canary strings that appear in any of *outputs*."""
    blob = "\n".join(o for o in outputs if o)
    return [c for c in canaries if c and c in blob]


def _cutoff_date(model: str | None) -> date | None:
    iso = _MODEL_CUTOFFS.get(model or "")
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def declarative_assess(contamination: dict[str, Any], model: str | None) -> ContaminationReport:
    """Heuristic assessment from the declared contamination block. Never raises."""
    reasons: list[str] = []
    signals: dict[str, Any] = {}
    status: Status = "unknown"

    if contamination.get("is_public"):
        status = "warn"
        reasons.append("test set / answers are declared public (is_public: true)")
        signals["is_public"] = True

    release = contamination.get("release_date")
    cutoff = _cutoff_date(model)
    if release and cutoff:
        try:
            rel = date.fromisoformat(str(release))
            signals["release_date"] = str(release)
            if rel <= cutoff:
                status = "contaminated"
                reasons.append(
                    f"test set released {rel} ≤ model knowledge cutoff {cutoff}"
                )
        except ValueError:
            pass

    return ContaminationReport(status=status, reasons=reasons, signals=signals)


class ContaminationProbe:
    """Active probe with a declarative fallback. Non-blocking by construction."""

    async def assess(
        self,
        *,
        dataset_info: Any,
        eval_contract: dict[str, Any],
        model: str | None = None,
        outputs: Iterable[str] = (),
        provider: Any = None,
        search_tool: Any = None,
        timeout: float = 60.0,
    ) -> ContaminationReport:
        contamination = (eval_contract or {}).get("contamination", {}) or {}
        outputs = list(outputs)

        # 1. Canary scan (deterministic, cheap, authoritative when it hits).
        canaries = contamination.get("canaries") or []
        hits = scan_canaries(outputs, canaries)
        if hits:
            return ContaminationReport(
                status="contaminated",
                reasons=[f"canary string(s) leaked into output: {', '.join(hits)}"],
                signals={"canaries": hits},
            )

        # 2. Active probe (stubbed) — guarded by timeout, degrades to declarative.
        if provider is not None:
            try:
                signal = await asyncio.wait_for(
                    self._llm_membership_probe(
                        dataset_info=dataset_info, model=model, provider=provider,
                    ),
                    timeout=timeout,
                )
                if signal is not None:
                    return signal
            except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
                log.warning("contamination: active probe failed/timed out: %s", exc)

        # 3. Declarative fallback.
        return declarative_assess(contamination, model)

    async def _llm_membership_probe(
        self, *, dataset_info: Any, model: str | None, provider: Any
    ) -> ContaminationReport | None:
        """STUB — follow-up. Will ask the model to reproduce held-out rows /
        recognize the dataset and infer membership. Returns None (no signal)
        for now so `assess` falls through to the declarative heuristic."""
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contamination.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/coordinator/contamination.py tests/test_contamination.py
git commit -m "feat(contamination): declarative heuristic + canary scan (LLM probe stubbed)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Surface contamination (preflight check + INIT probe)

**Files:**
- Modify: `src/cli/preflight.py` (add check #5; register in `run_all_collect`)
- Modify: `src/coordinator/orchestrator.py` (run the probe at INIT; store in `meta["contamination"]`; emit event)
- Test: `tests/test_contamination_surface.py`

**Interfaces:**
- Consumes: Task 7 (`ContaminationProbe`, `declarative_assess`), Task 3 (`ev.CONTAMINATION_ASSESSED`), `eval_contract` from `config.plugin` / `tree.meta`.
- Produces: `PreflightChecker._check_contamination() -> CheckResult`; orchestrator helper `async _assess_contamination(self) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contamination_surface.py
from __future__ import annotations

from pathlib import Path

from src.cli.preflight import PreflightChecker


def test_preflight_contamination_warns_on_public(tmp_path: Path, monkeypatch):
    checker = PreflightChecker(tmp_path, provider="anthropic")
    # inject the declared contract the way the real caller will
    checker.eval_contract = {"contamination": {"is_public": True}}
    result = checker._check_contamination()
    assert result.status == "warn"
    assert "public" in result.message.lower()


def test_preflight_contamination_pass_when_no_block(tmp_path: Path):
    checker = PreflightChecker(tmp_path, provider="anthropic")
    checker.eval_contract = {}
    result = checker._check_contamination()
    assert result.status == "pass"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contamination_surface.py -q`
Expected: FAIL — `AttributeError: 'PreflightChecker' object has no attribute '_check_contamination'`.

- [ ] **Step 3: Write minimal implementation**

In `src/cli/preflight.py`, give `__init__` an optional contract and add the check. Add a parameter `eval_contract: dict | None = None` to `__init__` and store `self.eval_contract = eval_contract or {}`. Then:

```python
    def _check_contamination(self) -> CheckResult:
        from ..coordinator.contamination import declarative_assess

        block = (self.eval_contract or {}).get("contamination", {}) or {}
        if not block:
            return CheckResult("contamination", "pass", "no contamination signals declared")
        report = declarative_assess(block, model=None)
        if report.status in {"warn", "contaminated"}:
            return CheckResult(
                "contamination", "warn",
                "; ".join(report.reasons) or "benchmark may be in pretraining data",
                hint="held-out numbers may be inflated — interpret with care",
            )
        return CheckResult("contamination", "pass", "no contamination signals declared")
```

Register it in `run_all_collect`'s `checks` list (after `self._check_eval`):

```python
            self._check_eval,
            self._check_contamination,
```

In `src/coordinator/orchestrator.py`, add an INIT-time assessment. Find where `dataset_info` / `eval_cmd` meta is established (grep `eval_cmd` in orchestrator ~line 501/637). Add:

```python
    async def _assess_contamination(self) -> None:
        """Run the contamination probe once and record it in meta + an event."""
        if not getattr(self.config, "contamination_probe", True):
            return
        from .contamination import ContaminationProbe
        from ..events import types as ev

        plugin = getattr(self.config, "plugin", None)
        eval_contract = dict(getattr(plugin, "eval_contract", {}) or {})
        # allow a tree-meta override/addition
        if self.tree.meta.get("contamination"):
            eval_contract.setdefault("contamination", self.tree.meta["contamination"])
        try:
            report = await ContaminationProbe().assess(
                dataset_info=self.tree.meta.get("dataset_info"),
                eval_contract=eval_contract,
                model=getattr(self.config, "model", None),
                provider=None,  # active probe stays stubbed for now
                timeout=getattr(self.config, "contamination_timeout", 60),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("contamination: assessment failed: %s", exc)
            return
        self.tree.meta["contamination"] = report.to_dict()
        self.tree.bus.emit(ev.CONTAMINATION_ASSESSED, {
            "status": report.status, "reasons": report.reasons,
        })
```

Call `await self._assess_contamination()` once during INIT, right after the meta block that sets `eval_cmd`/`dataset_info` is populated (the same place §1.1 grounding is kicked off). Wrap the call site so it can't break INIT.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contamination_surface.py tests/test_quickstart.py -q`
Expected: PASS (new tests + preflight smoke still green).

- [ ] **Step 5: Commit**

```bash
git add src/cli/preflight.py src/coordinator/orchestrator.py tests/test_contamination_surface.py
git commit -m "feat(contamination): preflight check + INIT probe recorded in meta

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Plugin manifest contamination block + docs + full suite

**Files:**
- Modify: `tests/test_plugin_manifest.py` (extend)
- Modify: `docs/plugins.md` (document the `contamination` block + `protected_paths` runtime enforcement)
- Modify: `docs/roadmap.md` (mark §1.2 shipped, mirroring how §1.1 was marked)

**Interfaces:**
- Consumes: `load_plugin` / `Plugin.eval_contract` (`src/plugins/base.py`) — already passes `eval_contract` through verbatim, so no parser change.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_plugin_manifest.py
def test_plugin_contamination_block_round_trips(tmp_path):
    from src.plugins.base import load_plugin

    p = tmp_path / "demo.yaml"
    p.write_text(
        "name: demo\n"
        "eval_contract:\n"
        "  metric_direction: maximize\n"
        "  contamination:\n"
        "    is_public: true\n"
        "    canaries: [\"CANARY-1\"]\n",
        encoding="utf-8",
    )
    plugin = load_plugin("demo", search_dirs=[tmp_path], strict=True)
    contamination = plugin.eval_contract["contamination"]
    assert contamination["is_public"] is True
    assert contamination["canaries"] == ["CANARY-1"]
```

- [ ] **Step 2: Run test to verify it fails (or passes trivially)**

Run: `python -m pytest tests/test_plugin_manifest.py -k contamination -q`
Expected: PASS already if `eval_contract` is passed through verbatim — this test **locks in** that contract so a future parser change can't silently drop the block. If it fails, fix `_load_plugin_from_path` to preserve nested `eval_contract` keys.

- [ ] **Step 3: Documentation**

In `docs/plugins.md`, under the eval-contract section, add a `contamination` subsection showing the block shape (copy from the design spec) and note that `protected_paths` are now hash-verified at runtime (tamper invalidates the dev score), not only checked at merge.

In `docs/roadmap.md`, mark §1.2 items shipped in the same style §1.1 uses (a `✅ *(shipped)*` tag + a short "Shipped" paragraph linking the new behavior).

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (whole suite green). Then `python -m ruff check src tests` and `python -m mypy src` — expected clean (match repo baseline; fix any new findings in the files this branch touched).

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_manifest.py docs/plugins.md docs/roadmap.md
git commit -m "docs(eval-discipline): contamination block + runtime protection; mark §1.2 shipped

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (completed)

- **Spec coverage:** Tamper-proofing → Tasks 1,2,4,5(merge meta); split provenance → Tasks 5,6; contamination (declarative+canary working, LLM stubbed) → Tasks 7,8,9; config → Task 2; events → Task 3. All three spec features mapped.
- **Type consistency:** `score_split`/`test_score` defined in Task 5 are consumed in Tasks 4 (`async_update_node(... score_split=...)`) and 6 (render). `ContaminationReport`/`declarative_assess`/`ContaminationProbe.assess` signatures defined in Task 7 are used unchanged in Task 8. `resolve_protected_paths` defined in Task 2 used in Task 4. `ProtectedChange` from Task 1 used in Task 4.
- **Sequencing note:** Task 4 emits `score_split="dev"` into `async_update_node`; that kwarg is only accepted after Task 5 adds it to `MUTABLE_FIELDS`. **Land Task 5 before exercising Task 4's full executor path** (Task 4's unit tests don't hit `async_update_node`, so they pass standalone, but the integration is only valid once both land).
- **Placeholder scan:** No TBD/TODO; every code step shows real code. Dashboard/WebUI edits name exact line anchors and a grep fallback where the surrounding struct must be confirmed in-context.
