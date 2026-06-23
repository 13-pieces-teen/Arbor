# Evaluation Discipline (Roadmap §1.2) — Design

## Context

The roadmap's Direction 1 §1.2 ("Evaluation discipline") names three gaps in how
Arbor produces and trusts a number:

1. **Tamper-proof evals.** Protected paths (`data/**`, `evaluation/**`, …) are
   declared per-plugin but enforced *only at merge time* via a
   `git diff --name-only` + `fnmatch` check in `GitMergeBranch`
   (`src/coordinator/tools/git_ops.py`). The B_dev evaluation, however, runs
   *inside the executor's own worktree*, so an executor can write to `data/` or
   `evaluation/` before running B_dev and report an inflated dev score that the
   coordinator then trusts for ideation. Nothing makes protected paths
   genuinely unwritable, and nothing detects uncommitted tampering. AutoSOTA has
   anti-tampering; we want the same guarantee.
2. **Split provenance.** B_dev (`eval_cmd`) and B_test (`eval_cmd_test`) exist,
   and `meta` separates dev/test baseline/trunk scores, but a node carries a
   single untagged `score`, and reporting does not consistently say *which split
   a number came from*.
3. **Contamination checks.** There is no signal at all when a benchmark's test
   set is likely already in pretraining data, which makes the number meaningless.

This branch delivers §1.2. Cost & scheduling (§1.3) is deferred to a separate
follow-up branch.

## Goals / Non-goals

**Goals**
- Make protected paths tamper-evident during a run (portable) and best-effort
  unwritable (where the OS supports it), and refuse to trust or merge a tampered
  branch.
- Tag every recorded score with its split and surface that everywhere a score is
  shown (REPORT, dashboard, WebUI).
- Detect likely contamination cheaply and deterministically, surfaced before and
  during a run, and never let the check itself block a run.

**Non-goals**
- Preventing *reads* of protected files (label leakage) — out of scope; this is
  about write-tamper of data/eval.
- The fuzzy LLM membership-inference probe ships **stubbed behind the interface**
  in this branch (declarative heuristic + canary scan ship fully working); the
  LLM probe is a follow-up.
- Anything in §1.3 (budget tiers, pre-run cost accounting).

---

## Feature 1 — Tamper-proof protected paths (hybrid: manifest + best-effort RO)

### New module `src/coordinator/tools/integrity.py`
Pure, side-effect-light helpers (no git, easy to unit-test):

- `build_protected_manifest(root: Path, protected_paths: list[str]) -> dict[str, str]`
  — expand each glob under `root`, return `{relpath: sha256}` for every matched
  file. Deterministic ordering.
- `verify_protected_manifest(root, protected_paths, manifest) -> list[Change]`
  — recompute and diff against `manifest`; `Change` records `path` and
  `kind ∈ {modified, added, removed}`. Empty list ⇒ untampered.
- `apply_readonly(root, protected_paths) -> None` and `clear_readonly(...)`
  — best-effort OS read-only: POSIX `chmod 0o444` (files) / `0o555` (dirs);
  Windows sets `FILE_ATTRIBUTE_READONLY`. Every operation is wrapped so any
  failure is a logged warning, never fatal. `clear_readonly` is called before
  worktree removal so cleanup never fails on read-only files.

### Integration points
1. **Worktree creation** — in `executor_run.py` right after `_create_worktree`
   succeeds (keeps `worktree.py` git-only): build the manifest, persist it to a
   run-log sidecar (`<log_dir>/protected/<safe-branch>.json`), then
   `apply_readonly`. Gated on `config.enforce_protected` and a non-empty
   protected-path set.
2. **Executor finalize** — in `executor_run.py` after the executor returns and
   before `_finalize_worktree`: `clear_readonly`, then
   `verify_protected_manifest`. **This is the new runtime guarantee.** On a
   non-empty change list:
   - emit a `PROTECTED_TAMPER` event (new event type) with the changed paths;
   - set `node.eval_status = "tampered"`, `node.score = None`,
     `node.status = "needs_retry"` (or pruned), and record the reason in
     `node.insight`;
   - the branch is thereby ineligible to merge (no trusted score).
3. **Merge** — in `GitMergeBranch` (`git_ops.py`): keep the existing committed
   `git diff` + `fnmatch` rejection; add a manifest cross-check of the fresh
   B_test worktree against the trunk manifest as defense-in-depth before B_test
   runs. A tampered branch is rejected with a clear message.

### Resolving the protected-path set
Source order: `config.protected_paths` (new) → `plugin.protected_paths` →
`tree.meta["protected_paths"]` (new, for non-plugin runs). A small helper
`resolve_protected_paths(config, plugin, meta)` centralizes this.

### Config
Add to the coordinator config / `eval` group: `enforce_protected: bool = True`.
When false, manifests and RO are skipped entirely (escape hatch / debugging).

---

## Feature 2 — Split provenance (everywhere scores live)

### Data model (`src/coordinator/idea_tree.py::Node`)
- Add `score_split: str = "dev"` — which split `score` came from.
- Add `test_score: float | None = None` — the verified B_test score, set at merge.
- Wire both into `MUTABLE_FIELDS`, `to_dict` (omit when default/None), and
  `from_dict` (defaulting for old trees → fully backward-compatible; bump
  `IdeaTree.VERSION` is **not** required since loading is additive).

### Recording
- Executor outcome path sets `score` with `score_split="dev"` (explicit).
- `GitMergeBranch` already computes a verified test score; make it write
  `node.test_score` and `meta["test_trunk_score"]` directly (today it only
  *instructs the LLM* to do so via the returned message). The instruction text
  stays as a human-facing confirmation.

### Rendering — label every score with its split
- `REPORT.md`: `src/run.py` (headline + per-node) and `src/report/generator.py`
  — annotate scores as `… (dev)` / `… (test)`; the headline already separates
  dev/test, so this is mostly per-node tags.
- CLI dashboard: `src/cli/run_dashboard.py` — add a split tag/column to node rows.
- WebUI: `src/webui/` — show the split alongside the node score in the detail
  view (and snapshot serialization in `src/webui/snapshot.py` / `session_source.py`
  if scores are projected there).

---

## Feature 3 — Contamination checks (active probe interface, declarative+canary working, LLM probe stubbed)

### Declarative contract
Extend `eval_contract` with an optional `contamination` block (parsed by
`src/plugins/base.py` — it already passes `eval_contract` through verbatim, so no
parser change needed, but document the shape):

```yaml
eval_contract:
  contamination:
    release_date: "2024-01-01"   # when the test set became public (ISO date)
    is_public: true              # test set / answers are publicly posted
    source_url: "https://..."    # where it lives (for the web-search probe later)
    canaries: ["BENCHMARK-CANARY-GUID-..."]  # strings that must not appear in outputs
```

### New module `src/coordinator/contamination.py`
- `@dataclass ContaminationReport` — `status: Literal["clean","warn","contaminated","unknown"]`,
  `reasons: list[str]`, `signals: dict[str, Any]`.
- `class ContaminationProbe` with
  `async assess(*, dataset_info, eval_contract, model: str | None,
  outputs: Iterable[str] = (), provider=None, search_tool=None,
  timeout: float) -> ContaminationReport`:
  - **Active layer (primary):**
    - **Canary scan (working):** if `canaries` are declared, scan provided
      `outputs` (model INIT text, submission preview) for any canary string ⇒
      `contaminated`.
    - **LLM membership-inference (stubbed):** `_llm_membership_probe(...)` exists
      behind the interface and currently returns `None` (no signal); a follow-up
      fills it in. Documented as a stub.
    - **Web-search probe (optional):** only if a `search_tool` is supplied;
      reuses `ResearchSearchTool`. Off by default (no backend ⇒ skipped). Also
      stubbed-light: wired but conservative.
  - **Fallback layer (declarative heuristic, working):** on any active-layer
    error/timeout/empty signal — compare `release_date` against the model's
    knowledge cutoff (best-effort table; unknown ⇒ `unknown`) and read
    `is_public` ⇒ `warn`/`contaminated`.
  - The whole body is wrapped in `try/except` + `asyncio.wait_for(timeout)`;
    on timeout/exception it returns `ContaminationReport(status="unknown", …)`.
    **It never raises and never blocks the run.**

### Surface
- **Preflight (always-on, zero-network):** add `_check_contamination` as check #5
  in `src/cli/preflight.py`, using only the declarative `contamination` block /
  available dataset metadata → emits a `warn` `CheckResult`. (Active probe is
  *not* run here — preflight stays token-free.)
- **Coordinator INIT (active probe):** run `ContaminationProbe.assess(...)` once
  after `dataset_info` / `eval_contract` are known; store the report in
  `meta["contamination"]`, emit a `CONTAMINATION_ASSESSED` event, and render it
  in `REPORT.md`.

### Config
`eval.contamination_probe: bool = True` (auto-falls-back to declarative),
`eval.contamination_timeout: int = 60`.

---

## Tests
- `tests/test_integrity.py` — manifest build is deterministic; verify detects
  modified/added/removed; `apply_readonly`/`clear_readonly` never raise on either
  OS (and a round-trip leaves files writable again).
- `tests/test_contamination.py` — canary scan flags a planted canary; declarative
  heuristic warns on `is_public`/old `release_date`; a probe that raises or times
  out returns `status="unknown"` and does not propagate.
- Extend `tests/test_idea_tree.py` — `Node` round-trips `score_split`/`test_score`;
  old-format dicts load with defaults.
- Extend `tests/test_plugin_manifest.py` — a plugin with a `contamination` block
  loads and exposes it on `eval_contract`.

## Verification (end-to-end)
1. `pytest tests/test_integrity.py tests/test_contamination.py tests/test_idea_tree.py tests/test_plugin_manifest.py -q`.
2. Mini-benchmark smoke: a fixture workspace with `data/` + a plugin declaring
   `protected_paths`; run an executor that writes to `data/` →
   confirm `PROTECTED_TAMPER` event, `node.score` invalidated,
   `node.eval_status == "tampered"`, and `GitMergeBranch` refuses the branch.
3. Merge a clean improving node → confirm `node.test_score` + `meta.test_trunk_score`
   are set automatically and the dev/test split labels render in `REPORT.md`, the
   CLI dashboard, and the WebUI.
4. A plugin with a `contamination` block declaring `is_public: true` → confirm
   the preflight warning and the `meta["contamination"]` record in REPORT.

## Risks / Open questions
- **Best-effort RO on Windows** is genuinely weak (read-only attribute is easily
  cleared); the manifest is the real guarantee. Documented as such.
- **Score-split rendering touches the WebUI**, which was recently reworked on a
  separate branch — keep the change additive (one label) to avoid conflict.
- **Manifest cost** for very large `data/` trees: hashing every protected file at
  each worktree creation could be slow. Mitigate by hashing file size+mtime first
  and only SHA-256 on suspicion? Decision: start with full SHA-256 (correctness),
  revisit if it shows up as a cost.
