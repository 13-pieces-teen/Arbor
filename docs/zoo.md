# Benchmark Zoo

The **benchmark zoo** is a curated set of benchmarks packaged in one standard,
verifiable format so that anyone can re-run them with Arbor and check the numbers.
It lives in [`arbor-zoo/`](https://github.com/RUC-NLPIR/Arbor/tree/main/arbor-zoo),
one folder per benchmark.

The zoo is **quality-capped, not quantity-driven**. Its first job is to be Arbor's own
regression harness — a small set of hand-checked, reproducible tasks that exercise the
Coordinator/Executor loop — and only secondarily an outward showcase. It is deliberately
**not** a leaderboard of our own results. An unverified benchmark does not enter the zoo:
eval correctness is the bedrock, and a benchmark you cannot trust is worse than none.

The format is **documentation-first with a tiny machine contract**. A benchmark is a
well-documented repo; the few facts a verifier and an unattended harness genuinely need —
and which prose cannot be checked against — live in a small YAML **front-matter** block at
the top of the README (no separate manifest file). Everything human stays in prose.

## What a benchmark folder contains

Each `arbor-zoo/<name>/` is one self-contained benchmark holding four things — a guide
for the **user**, a description for **Arbor**, a runnable **baseline**, and a protected
**eval**:

| File / dir | Role | For |
| --- | --- | --- |
| `README.md` | A YAML **front-matter** contract (metric, splits, baseline, edit surface) + prose body in four fixed sections. | machine + user + Arbor |
| baseline code | The **baseline implementation** and Arbor's edit surface — `solution.py`, *or a whole set of files / a subdirectory*. | Arbor edits |
| `eval.sh` *or* `eval.py` | Protected eval entrypoint. `bash eval.sh dev\|test` (or `python eval.py --split …`) prints one line `score: <float>`. | protected |
| `task.py` *(if used)* | Protected ground truth: problem generator, reference solver, independent verifier. | protected |
| `data/` | Bundled data; or a `download.sh` when the data may not be redistributed. | — |
| `PROVENANCE.md` | Source, setup & environment, license, baseline implementation, baseline reproduction, contamination, caveats. Seven fixed sections. | human review |

The **baseline can be more than one file** — the `edit:` list in the front-matter names
the editable surface; everything else (the eval harness, ground-truth files, data) is the
protected remainder.

Folders whose name begins with `_` (e.g.
[`_template`](https://github.com/RUC-NLPIR/Arbor/tree/main/arbor-zoo/_template)) are
scaffolding and are skipped by every tool.

### `README.md` front-matter — the machine contract

A small YAML block fenced by `---` at the very top of the README. It carries only the
facts that are not prose and that the verifier / an unattended run need:

```yaml
---
name: algotune_knn
metric:
  direction: maximize          # maximize | minimize
eval:
  cmd: "bash eval.sh"          # optional; omit to use the eval.sh/eval.py convention.
                               # the verifier appends `dev` / `test`
splits:                        # how dev/test differ — lets verify prove they're disjoint
  kind: seed_range             # seed_range | path
  dev:  { base: 1000, count: 3 }
  test: { base: 9000, count: 3 }
baseline:
  score: 1.0                   # what `eval dev` prints today (verify checks reality matches)
  tolerance: 0.30              # relative margin for reproduce + determinism
  kind: timing                 # exact | timing  (timing uses a ratio tolerance)
edit: [solution.py]            # editable files/globs (1+); everything else is protected
---
```

For a path-based split, write `splits: {kind: path, dev: ["data/dev/**"], test: ["data/test/**"]}`.
The same field names reuse the [plugin](plugins.md) vocabulary, so a verified benchmark
can be turned into a plugin with little rework.

### `README.md` body — four fixed sections

In this order, so every benchmark reads the same way:

1. **Task & metric** — what the task is, what a solution looks like, the edit surface,
   what is off-limits.
2. **Run the baseline** — the exact `eval` commands and what they print (point to
   PROVENANCE → Setup & environment for install/hardware/keys).
3. **Optimize with Arbor** — how to point Arbor at the benchmark and the suggested
   research contract.
4. **Provenance** — a pointer to `PROVENANCE.md`.

### `PROVENANCE.md` — seven fixed sections

`PROVENANCE.md` is the line between a trustworthy benchmark and one that merely looks the
part. Required headings: **Source**, **Setup & environment**, **Data source & license**,
**Baseline implementation**, **Baseline reproduction**, **Contamination assessment**,
**Caveats**. The verifier checks the headings are present; the *content* is read and
accepted by a human — never auto-accepted.

## Run Arbor on a benchmark

Arbor runs experiments in git worktrees off the repo root, so work from a copy
**outside** the Arbor checkout:

```bash
cp -r arbor-zoo/algotune_knn /tmp/algotune_knn
cd /tmp/algotune_knn
git init -q && git add -A && git commit -qm baseline
arbor   # confirm the contract in the intake chat
```

## Verify a benchmark

```bash
arbor benchmark verify arbor-zoo/<name>             # exits non-zero on any failure
arbor benchmark verify arbor-zoo/<name> --no-eval   # structural checks only
arbor benchmark list arbor-zoo                       # plain index of benchmarks
```

The checks prove what the contract makes provable and defer judgement calls to human
review:

| Check | Tier | What it proves |
| --- | --- | --- |
| `contract` | strong | README front-matter is present and its required fields are valid. |
| `readme-sections` | strong | README body has the four fixed sections. |
| `provenance` | strong | PROVENANCE has all seven headings (incl. baseline implementation + contamination). |
| `splits-disjoint` | strong | Dev/test are provably disjoint for the declared split mechanism. |
| `edit-surface` | strong | The declared editable files exist; the harness/ground-truth/data are not editable. |
| `eval-dev` / `eval-test` | strong | `eval dev` and `eval test` each run and print a parseable score. |
| `baseline-reproduces` | strong | The bundled baseline reproduces `baseline.score` within `tolerance`. |
| `determinism` | strong | Two dev runs agree (ratio tolerance for `kind: timing`, exact equality otherwise). |
| `contamination` | advisory | The contamination assessment is present; its content needs human acceptance. |

What is still **left to human review** (the contract cannot prove intent): that the
contamination assessment is honest, and that the declared baseline/split reflect a real
held-out protocol rather than a convenient fiction.

## Add a benchmark

1. Copy the scaffold: `cp -r arbor-zoo/_template arbor-zoo/<name>`.
2. Fill in the front-matter contract + baseline (one or more code files), the protected
   eval (`eval.sh` / `eval.py`, `task.py`), the four-section `README.md`, and the
   seven-section `PROVENANCE.md`.
3. Run `arbor benchmark verify arbor-zoo/<name>` until it exits 0.
4. A maintainer reviews the PROVENANCE card and accepts the benchmark. **Drafting may be
   automated; acceptance is not** — and the agent that implements a baseline must be
   separate from the loop that later optimizes it, or the evaluation is self-certifying.

!!! note "Coming next"
    A `arbor benchmark add "<paper / repo / dataset>"` flow will let Arbor search for,
    download, and *draft* a benchmark from one you name — then hand it to the verifier and
    to you for acceptance. The format and verifier on this page are the landing pad for
    that flow.
