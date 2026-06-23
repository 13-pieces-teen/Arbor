---
name: TODO_pack_name
metric:
  direction: maximize          # maximize | minimize
eval:
  cmd: "bash eval.sh"          # optional; omit to use the eval.sh/eval.py convention.
                               # the verifier appends `dev` / `test`
splits:                        # how dev/test differ — lets the verifier prove they're disjoint
  kind: seed_range             # seed_range | path
  dev:  { base: 1000, count: 3 }
  test: { base: 9000, count: 3 }
  # path example:
  #   kind: path
  #   dev:  ["data/dev/**"]
  #   test: ["data/test/**"]
baseline:
  score: 0.0                   # what `eval dev` prints today (verifier checks reality matches)
  tolerance: 0.0               # relative margin for reproduce + determinism
  kind: exact                  # exact | timing  (timing uses a ratio tolerance)
edit: [solution.py]            # the editable surface (1+ files/globs); everything else is protected
---

# TODO_pack_name

One-line summary of the benchmark. Fill in the front-matter above (the machine contract)
and the four sections below — the verifier checks both, and they are what users and Arbor
read.

## Task & metric

What is the task, what does a solution look like, what number is optimized, and which
direction is better (maximize / minimize)? Name the **edit surface** — the baseline
code Arbor may change (one file like `solution.py`, or a whole set of files / a
directory) — and what is off-limits (the eval harness and any ground-truth files).

## Run the baseline

The exact commands and the score the shipped baseline prints. The eval entrypoint is
`eval.sh` (or `eval.py`), invoked with a split:

```bash
bash eval.sh dev     # iterate here
bash eval.sh test    # held-out gate
```

Point to [`PROVENANCE.md`](PROVENANCE.md) → Setup & environment for install / hardware
/ keys.

## Optimize with Arbor

How to point Arbor at this benchmark (copy it out of the Arbor checkout first, it uses
git worktrees) and the suggested research contract — metric, dev/test discipline, what
may and may not be edited.

## Provenance

See [`PROVENANCE.md`](PROVENANCE.md). Verify the benchmark with:

```bash
arbor benchmark verify arbor-zoo/<name>
```
