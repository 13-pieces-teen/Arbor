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

### 1.2 Evaluation discipline

- Stronger held-out guarantees and clearer reporting of which split a number came
  from.
- **Contamination checks** — flag when a benchmark's test set is likely already in
  pretraining data, since that makes the number meaningless.
- Tamper-proof evals — confirm protected paths are genuinely unwritable during a run
  (AutoSOTA has anti-tampering; we want the same guarantee).

### 1.3 Cost and scheduling

- Budget tiers (smoke → pilot → full) so larger sweeps stay predictable.
- Per-backend / per-run cost accounting surfaced before a run starts, not after.

---

## Direction 2 — External resources

### 2.1 Benchmark zoo, organized by domain

A curated collection of tasks already in Arbor's scorable-repo form, grouped by
domain (e.g. vision, NLP, time series, optimization), each using a published
paper's result as the baseline to beat. It lives in the repo as `arbor-zoo/`, one
folder per benchmark, and serves first as Arbor's own regression harness — not a
leaderboard of our wins. Below is the format we intend to standardize on; none of
it is built yet.

**Repo layout.** `arbor-zoo/<benchmark-name>/`, one folder per benchmark; folders
prefixed `_` (e.g. `_template`) are scaffolding and skipped by tooling.

**What each benchmark folder holds** — the existing scorable-repo contract plus
two metadata files and a human README:

| File | Role |
| --- | --- |
| `solution.py` | The editable artifact Arbor optimizes (the only edit surface). |
| `eval.sh` / `eval.py` | Protected eval; `bash eval.sh dev\|test` prints one `score: <float>` line. |
| `data/` | Bundled data, or a download script when it can't be redistributed. |
| `pack.yaml` | Machine-readable manifest (metric, splits, baseline, setup, license). |
| `PROVENANCE.md` | Source, license, baseline reproduction, contamination assessment. |
| `README.md` | Human intro with six fixed sections (see below). |

**The Task Pack format.** Promote today's implicit scorable-repo contract into one
versioned standard: an editable artifact, a protected eval invoked as
`bash eval.sh dev|test` that prints exactly one `score: <float>` line, disjoint
dev/test splits with test genuinely held out, plus the `pack.yaml` manifest and
`PROVENANCE.md` card. Manifest field names reuse the `plugin` vocabulary
(`eval_contract` / `protected_paths` / `profiles`) so a pack can lower into a
[plugin](plugins.md) without rework.

**Setup requirements, made explicit.** Because some benchmarks need extra API keys,
services, or a GPU to run, `pack.yaml` carries a machine-readable `setup:` block
(`hardware`, `python`, `install`, `env`, `services`) so tooling can warn before a
run, mirrored in prose in the README's "Setup & requirements" section.

**Provenance card.** `PROVENANCE.md` is what separates a trustworthy pack from a
plausible-looking one: source, data origin & license, how it was collected,
baseline reproduction (published vs. what the shipped baseline prints, and the
gap), a mandatory contamination assessment, and known caveats.

**Two READMEs.** A top-level `arbor-zoo/README.md` (the index, the format, how to
run a benchmark with Arbor, how to add one) and a per-benchmark `README.md` with a
fixed six-section order: Task & metric → Setup & requirements → Run the baseline →
Optimize with Arbor → Provenance.

**`arbor benchmark verify`.** A checker — and the verifier's spec — that confirms:
`pack.yaml`/`PROVENANCE.md` parse and are complete, the eval emits a parseable
score on dev and test, the baseline reproduces the claimed number, dev/test are
disjoint and held out, protected paths are unwritable, the eval is deterministic
and offline, and the license permits the shipped use. A pack that fails any check
doesn't enter the zoo — eval correctness is the foundation, and an unverified pack
is worse than none.

**Semi-automatic conversion.** Use the intake agent to *draft* a Task Pack from a
raw benchmark, then gate it behind the verifier and a human accept step. Automatic
means draft-automatic, accept-verified — never auto-accepted. The agent that
*implements* a baseline must be separate from the loop that later optimizes it, so
the evaluation isn't self-certifying.

**Licensing.** Ship data when redistribution is allowed; otherwise ship a download
script plus the provenance card.

Start small: 3–5 high-quality, human-checked packs across distinct task shapes,
using [`examples/algotune_knn`](https://github.com/RUC-NLPIR/Arbor/tree/main/examples/algotune_knn)
as the reference, then grow. Cap on quality, not count.


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
