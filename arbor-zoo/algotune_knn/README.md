---
name: algotune_knn
metric:
  direction: maximize          # higher speedup is better
eval:
  cmd: "bash eval.sh"          # the verifier appends `dev` / `test`
splits:
  kind: seed_range             # dev/test are disjoint seed windows (proved by verify)
  dev:  { base: 1000, count: 3 }   # must match DEV_SEED_BASE in eval.py
  test: { base: 9000, count: 3 }   # must match TEST_SEED_BASE in eval.py
baseline:
  score: 1.0                   # the shipped solution equals the reference (~1.0x)
  tolerance: 0.30              # relative margin for reproduce + determinism (timing noise)
  kind: timing                 # determinism uses a ratio tolerance, not bit-equality
edit: [solution.py]            # the only file Arbor may change; everything else is protected
---

# algotune_knn

An AlgoTune-style mini benchmark for Arbor: make a brute-force **k-nearest-neighbours**
computation *faster* without changing what it computes. CPU-only, no API key, fully
deterministic, sub-second — the simplest possible end-to-end benchmark of the
"edit the baseline → run eval → keep what improves the held-out score" loop.

## Task & metric

Given a database of points and a batch of queries, return each query's **k nearest
neighbours** (Euclidean distance). The reference implementation is intentionally
naive — full pairwise distances followed by a full sort. Your job is to compute the
**same** neighbours **faster**.

- **Edit surface:** `solution.py` (the `solve(problem)` function). The protected
  ground truth and harness — `task.py`, `eval.py`, `eval.sh` — must not change.
- **Metric:** `bash eval.sh` prints one line `score: <speedup>`, where
  `speedup = median(reference_time) / median(solution_time)` over a held-out set of
  instances, **after a correctness gate**. **Higher is better (maximize).**
- The shipped `solution.py` equals the reference, so the baseline is ~**1.0x**. A
  solution that fails the independent `is_solution` check on any instance scores
  **0.0** — "fast but wrong" cannot win.

| File | Role | Editable? |
| --- | --- | --- |
| `solution.py` | The solver Arbor optimises (`solve`). | **Yes — the edit surface.** |
| `task.py` | Problem generator, reference solver, `is_solution` verifier. | No — protected. |
| `eval.py` | Correctness gate + median-of-N timing; prints `score:`. | No — protected. |
| `eval.sh` | Pins a single BLAS/OpenMP thread, then runs `eval.py`. | No — protected. |

## Run the baseline

No setup beyond NumPy (see [`PROVENANCE.md`](PROVENANCE.md) → Setup & environment).
Dev and test use **disjoint seed ranges** (`1000+` vs `9000+`), so the signal you
iterate on is never the data you are finally judged on:

```bash
bash eval.sh dev     # iterate here   -> score: ~1.0
bash eval.sh test    # held-out gate  -> score: ~1.0
```

Problem size is tunable via env vars for a heavier benchmark — e.g.
`KNN_N_DB=8000 KNN_N_QUERY=500 KNN_DIM=32 bash eval.sh dev`.

## Optimize with Arbor

Arbor runs experiments in git worktrees off the repo root, so work from a **copy
outside the Arbor checkout**:

```bash
cp -r arbor-zoo/algotune_knn /tmp/algotune_knn
cd /tmp/algotune_knn
git init -q && git add -A && git commit -qm baseline
arbor   # confirm the contract in the intake chat
```

Suggested research contract: *maximize the `score:` from `bash eval.sh dev`; iterate
on dev, gate merges on `bash eval.sh test`; only edit `solution.py`; never touch
`task.py`, `eval.py`, or `eval.sh`; output must keep passing `is_solution`.* Real
headroom exists — `argpartition` partial selection, the
`|x−y|² = |x|² − 2x·y + |y|²` GEMM distance expansion, dtype and blocking tweaks —
so the idea tree has several genuine branches, not one trick.

## Provenance

See [`PROVENANCE.md`](PROVENANCE.md) for setup & environment, how the baseline is
implemented, baseline reproduction, source, license, and the contamination
assessment. Verify this benchmark with:

```bash
arbor benchmark verify arbor-zoo/algotune_knn
```
