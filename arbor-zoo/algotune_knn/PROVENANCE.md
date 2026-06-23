# Provenance — algotune_knn

## Source

Modelled on [AlgoTune](https://algotune.io/) (NeurIPS 2025), a benchmark of
single-editable-solver optimization tasks. This benchmark is **not** a verbatim copy
of any AlgoTune task — it is an independent, self-contained re-implementation of the
same *structure* (one editable solver + a fixed problem generator, reference solver,
and correctness verifier) for a brute-force k-nearest-neighbours task. It originated
as the worked example in [`examples/algotune_knn`](../../examples/algotune_knn).

## Setup & environment

- **Hardware:** CPU only — no GPU.
- **Python:** ≥ 3.10.
- **Install:** `pip install -r requirements.txt` (just NumPy).
- **Services / network:** none — fully offline; nothing is downloaded at eval time.
- **Threads:** `eval.sh` exports `OMP_NUM_THREADS=1` (and the BLAS equivalents) so the
  measured time reflects the *algorithm*, not the core count. Do not remove this — the
  speedup ratio is only stable run-to-run under single-thread pinning.

## Data source & license

There is **no external dataset**. Every problem instance is generated deterministically
at eval time from an integer seed via `numpy.random.default_rng(seed)` (standard-normal
point clouds). Nothing is downloaded, scraped, or redistributed.

- Code license: **MIT** (same as the Arbor repository).
- Data license: **MIT** — the data is synthetic and produced by the bundled `task.py`;
  bundling is trivially allowed because there is nothing to redistribute beyond
  generator code.

The "data" is the generator: `task.generate_problem(seed, n_db, n_query, dim)` returns a
database/query pair; `eval.py` builds dev instances from seeds `1000..1002` and test
instances from `9000..9002`. No collection, labelling, or curation is involved —
re-running the generator reproduces the exact bytes.

## Baseline implementation

The shipped `solution.py` is the **naive brute-force baseline**, intentionally
identical to `task.reference_solver`:

1. Compute the full pairwise distance matrix between every query and every database
   point by broadcasting — `diff = queries[:, None, :] - database[None, :, :]`, then
   `d2 = (diff * diff).sum(axis=2)` — an `O(n_query · n_db · dim)` operation.
2. `argsort` every row of `d2` in full and slice the first `k` columns.

It is correct but deliberately unoptimised, so its speedup over the reference is **1.0x
by construction** — that is the number Arbor has to beat. The headroom (partial
selection via `argpartition`, the `|x−y|² = |x|² − 2x·y + |y|²` GEMM expansion, dtype
and blocking tweaks) is what makes the optimization loop interesting; none of it is
applied in the baseline.

## Baseline reproduction

- **Published baseline:** ~1.0x — the baseline equals the reference by construction.
- **Bundled baseline (measured):** `bash eval.sh dev` prints `score:` around
  **0.99–1.01x**, fluctuating a couple of percent with timing noise on a quiet
  single-thread CPU (the numerator and denominator run identical code).
- **Gap:** none. Any deviation is pure timing jitter, not an algorithmic difference.

## Contamination assessment

**No held-out leakage and no pre-training contamination.**

- **Dev/test isolation:** dev seeds `1000..1002` and test seeds `9000..9002` are
  disjoint integer ranges (see `eval.py` `DEV_SEED_BASE` / `TEST_SEED_BASE`). A solution
  tuned on dev has never seen the test instances.
- **No web/pre-training contamination:** the instances are random point clouds generated
  from seeds, not text or images from any corpus, so there is nothing a model could have
  memorised. The metric is *wall-clock speedup of a computation*, not recall of an
  answer — "fast but wrong" scores 0 via the independent `is_solution` gate, which
  recomputes the ground truth.

## Caveats

- **Timing metric is hardware-dependent.** The absolute speedup depends on the machine;
  the *ratio* `median(reference)/median(solution)` is what is compared, and it is stable
  run-to-run only under single-thread pinning (enforced by `eval.sh`).
- **Determinism is not bit-exact.** Because the score is a ratio of medians, two runs
  differ by a few percent; the verifier's `determinism` check is advisory for exactly
  this reason — a human confirms the variation is timing noise, not a correctness bug.
- **Seed bases live in `eval.py`.** `DEV_SEED_BASE` / `TEST_SEED_BASE` in
  [`eval.py`](eval.py) define the held-out split; if you change one, change both and
  re-confirm disjointness here.
