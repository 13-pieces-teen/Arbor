# Roadmap

This is a direction document, not a release schedule. It lists the directions we
want to push on and a few concrete ideas under each. Items move, merge, or get
dropped as we learn.

## Positioning

A few autonomous-research systems already overlap with parts of this plan.
[AutoSOTA](https://github.com/tsinghua-fib-lab/AutoSOTA) is the closest: a
closed-loop system that reviews literature, edits research code, runs
experiments, and maintains a per-paper leaderboard across 100+ papers organized
by domain, with reproduced baselines and tamper-protected evals.

That overlap is real, so we are explicit about where Arbor is *not* trying to be a
second "auto-optimize published papers" leaderboard:

- The value we want to build is a **reusable, checkable benchmark format** anyone
  can re-run, not a catalog of our own wins.
- We lean on **held-out discipline** — a change is kept only if it clears a margin
  on a protected test split — over "produced a higher number".
- We treat the benchmark collection first as **our own regression harness** for the
  Coordinator/Executor, and only second as something public-facing.

---

## Direction 1 — Core functionality

### 1.1 Search and literature-grounded ideation ✅ *(shipped)*

Originally search lived in an isolated `SearchAgent`; idea generation and the
Coordinator could not search the open web. That kept benchmark runs fair — the
system couldn't copy a finished idea off the web — but it was too strict for real
research, where you read prior work before proposing a direction.

Shipped (default-off, so benchmark runs stay fair). See the
[Search & External Knowledge](search.md) guide for usage:

- **Grounded ideation** (`search.grounded_ideation`, default off) — the
  coordinator gets a `ResearchSearch` tool during ideation (intents:
  related-work / survey / lookup / explore).
- **Separation, not prohibition** — the grounding lane and the novelty-audit lane
  don't share state; a source that shapes an idea is recorded on the node's
  `grounding` field, separate from the audit's `related_work`.
- **Pluggable backends** behind `search.backends`, fanned out and merged:
  alphaXiv + Jina (keyless), Serper + Exa REST (keyed), **Exa via MCP** (keyless),
  and the legacy self-hosted endpoint. Keyless page reading via the Jina reader
  (raw-`requests` fallback), no browse endpoint needed.
- **Full-text and PDF ingestion** — the grounded lane reads with a larger token
  budget (`research_visit_tokens`) and parses PDFs, so a model can read a paper's
  method/results sections, not just its abstract.

Still open: enforcing the per-search round/visit caps as a hard cost bound, and
surfacing per-run search cost (tracked under [1.3](#13-cost-and-scheduling)).

### 1.2 Evaluation discipline ✅ *(shipped)*

Shipped:

- **Split provenance** — every score is tagged with the split it came from
  (`dev`/`test`) at the data-model level and rendered labeled in REPORT.md, the
  CLI dashboard, and the WebUI. The verified B_test score is recorded on the node
  and trunk meta automatically at merge.
- **Tamper-proof evals** — protected paths are hash-verified at runtime, not only
  at merge. Each executor worktree gets a SHA-256 manifest of its protected files
  plus best-effort OS read-only; any mid-run change discards the node's dev score
  and blocks the merge (emitting `eval.protected_tamper`). This closes the gap
  where an executor could inflate B_dev by writing to `data/`/`evaluation/`.
- **Contamination checks** — a declarative `eval_contract.contamination` block
  (release date, `is_public`, canaries) drives a non-blocking preflight warning
  and an INIT-time probe (`eval.contamination_assessed`, recorded in tree meta).
  The declarative heuristic + canary scan ship now; an LLM membership-inference
  probe is a planned follow-up.

See the [Plugins](plugins.md) guide for the `contamination` block and runtime
protected-path enforcement.

### 1.3 Cost and scheduling

- Budget tiers (smoke → pilot → full) so larger sweeps stay predictable.
- Per-backend / per-run cost accounting surfaced before a run starts, not after.

---

## Direction 2 — External resources

### 2.1 Benchmark zoo, organized by domain 🚧 *(format + tooling shipped; collection growing)*

A curated collection of tasks in one standard format, grouped by domain (e.g.
vision, NLP, time series, optimization), each using a published paper's result as
the baseline to beat. It lives in the repo as `arbor-zoo/`, one folder per
benchmark, and serves first as Arbor's own regression harness — not a leaderboard
of our wins.

Shipped — the Task Pack format, the verifier, and a first reference pack. See the
[Benchmark Zoo](zoo.md) guide for the full spec and the verifier's check list:

- **Task Pack format**, one folder per benchmark, with the contract carried in the
  **README front-matter** (metric, dev/test split, baseline, edit surface) — there
  is *no separate manifest file*. Alongside it: a runnable baseline (e.g.
  `solution.py`), a protected eval entrypoint (`eval.sh` / `eval.py`) that prints
  exactly one `score: <float>` line for `dev`|`test`, an optional protected
  `task.py` (deterministic `generate_problem` + an *independent* `is_solution`
  verifier, so "fast but wrong" can't score), and a `PROVENANCE.md` card (source,
  license, setup/environment, baseline reproduction, contamination, caveats).
- **`arbor benchmark verify`** gates a pack: front-matter + `PROVENANCE.md` parse
  and are complete, the eval emits a parseable score on dev and test, the baseline
  reproduces its claimed number, dev/test are held out, protected paths hold, and
  the eval is deterministic/offline. Exits non-zero on any failure — an unverified
  pack does not enter the zoo. **`arbor benchmark list`** indexes a zoo directory
  (a plain index, not a leaderboard).
- **Reference pack + scaffolding**:
  [`algotune_knn`](https://github.com/RUC-NLPIR/Arbor/tree/main/arbor-zoo/algotune_knn)
  (verified) and a `_template` to copy. Folders prefixed `_` are skipped by tooling.

Still open:

- **Grow the collection** to 3–5 high-quality, human-checked packs across distinct
  task shapes, using `algotune_knn` as the reference. Cap on quality, not count.
- **`arbor benchmark add`** — semi-automatic conversion: from a one-line request the
  agent finds the dataset, asks (on an interactive terminal) which dataset to use and
  where the baseline comes from (harvest an existing one / implement the method you
  described / find one online), and brings up a runnable draft — gated behind the
  verifier and a human accept step (draft-automatic, accept-verified — never
  auto-accepted). The baseline-implementing agent stays separate from the loop that
  later optimizes it, so evaluation isn't self-certifying. *(Built: discovery +
  interactive bring-up; bring-up reasoning still maturing.)*
- **Lower a pack into a [plugin](plugins.md)** for one-line retargeting — the
  front-matter contract reuses the `plugin` vocabulary (`eval_contract` /
  `protected_paths`), so it should fall out with little rework (pairs with 2.2).


### 2.2 Plugin gallery

More worked domain plugins beyond `mle_kaggle`, paired with the Task Packs above,
so retargeting Arbor to a domain is a one-line `plugin:` change.

### 2.3 Search backends ✅ *(shipped)*

The pluggable backends from Direction 1 (alphaXiv, Jina, Serper, Exa REST, Exa
via MCP, self-hosted endpoint) are also external resources users wire in once and
reuse across runs. See [1.1](#11-search-and-literature-grounded-ideation-shipped)
and the [Search guide](search.md).

---

## Direction 3 — User presentation

### 3.1 Zoo / leaderboard view

A browsable page over the benchmark zoo: per domain, show the paper baseline, the
Arbor result, the gain, and the exact command to reproduce it. The point is
reproducibility — every row is something a reader can re-run — not a scoreboard.

### 3.2 Run comparison

- Diff two runs of the same benchmark.
- Compare Idea Trees across models/providers on the same task.

### 3.3 Reports and export

Build on today's `REPORT.md` and HTML export with citations (the grounding
sources behind each idea) and a per-run cost breakdown.

---

Have an idea or want to own one of these threads? Open a
[discussion](https://github.com/RUC-NLPIR/Arbor/discussions) or see
[Contributing](contributing.md).
