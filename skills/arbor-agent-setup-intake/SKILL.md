---
name: arbor-agent-setup-intake
description: "Setup, intake, preflight, and launch-contract phase for open-source Arbor/research_agent runs. Use when confirming a target project, metric, baseline, dev/test split, config/plugin settings, branch guard, session directory, or when translating a user goal into the precise contract consumed by the coordinator."
---

# Arbor Setup And Intake

Use this before the coordinator starts. The output is a concrete research
contract plus a clean workspace/session ready for the Arbor cycle.

## Fast Path

1. Confirm the target project directory. Treat the launch cwd as the default
   unless evidence says it is wrong.
2. Inspect README/config/eval files yourself. Do not ask the user to recite
   data you can read.
3. Identify the primary metric, direction, and real evaluation command.
4. Determine B_dev and B_test. If only one split exists, call it B_dev and
   record that no separate B_test is available.
5. Run or locate a cheap baseline when feasible. If not feasible, state
   `baseline unknown - measure during INIT`.
6. Propose one complete contract and ask for a single yes/edit confirmation.
7. Initialize or select `.arbor/sessions/<run_name>/` and hand the contract
   to the coordinator.

For smoke/forward tests, never run expensive setup, data prep, training, GPU
jobs, or the discovered full eval command. Locate an existing score in cached
metadata/logs or use a clearly labelled mocked score, and include
`smoke-only` in the contract.

## Research Contract

The instruction passed to the coordinator must contain all five components:

- **Metric**: exact score name, command that prints it, and maximize/minimize.
- **Baseline anchor**: current value if known, otherwise say it will be
  measured in INIT.
- **Ambition**: beat baseline, reach a target, or push as high as possible
  within the cycle budget.
- **Scope preference**: novelty-leaning, effect-leaning, or mixed. Infer it
  from the repo/task when possible.
- **Hard constraints**: at minimum, B_test is not for iteration, data/eval
  harness must not be modified to game the metric, and project-specific
  protected paths must be respected.

Do not prescribe a specific approach in the contract. The coordinator owns
idea generation.

## Preflight Checks

Mirror `arbor run` preflight:

- LLM credentials or provider config exist if using the real CLI.
- `cwd` exists and is non-empty.
- `git` exists. A git repo should be clean before a fresh run.
- An eval entry point exists or can be discovered (`eval.sh`, `run_eval.py`,
  `evaluate.py`, README instructions, Makefile targets, etc.).
- If the repo is on a non-base branch, either switch to the base branch or
  explicitly allow starting from that branch.

For skill-only smoke tests, do not require external API credentials unless an
LLM call will actually be made.

## Session Layout

Use the open-source layout:

```text
<project>/.arbor/sessions/<run_name>/
  REPORT.md
  COORDINATOR_FINAL_REPORT.txt
  events.jsonl
  run_stats.json
  conversation.md
  .coordinator/
    idea_tree.json
    idea_tree.md
    checkpoint.json
    messages.jsonl
    baseline_cache.json
  experiments/<node_id>/
    report.md
    metrics.json
    diff.patch
  submissions/
```

When no native Arbor runtime exists, initialize the same layout with:

```bash
python /path/to/arbor-agent-tools/scripts/arbor_state.py init \
  --cwd <project> --run-name <run_name> --task "<contract>"
```

## Config And Plugins

Honor this precedence:

```text
pydantic defaults < plugin.config_overrides < profile < project YAML < CLI
```

Recognize auto config names in the target project:

- `research_config.yaml`
- `arbor.yaml`
- `autoresearch.yaml`

If `plugin: mle_kaggle` is selected, load
`arbor-agent-plugins-hitl-budget` before INIT because the plugin pre-fills
eval contract, protected paths, required outputs, time budget, and skill
behavior.

## Baseline Metadata

The setup phase can discover metadata, but the coordinator must persist it:

- `baseline_score`
- `trunk_score`
- `test_baseline_score`
- `test_trunk_score`
- `eval_cmd`
- `eval_cmd_test`
- `eval_timeout`
- `eval_retries`
- `dataset_info`
- `metric_direction`
- `submission_path`
- `sample_submission_path`

Use command templates:

```text
cd {cwd} && <eval command> --run-name {node_id}
```

Never bake the main checkout path into executor commands.

In smoke mode, if a cached baseline log exists, parse only metric lines with
`arbor_state.py parse-log` or an equivalent parser that normalizes carriage
returns. Do not `cat`, raw `rg`, raw `grep`, or `tail` long training logs; if
debugging requires context, cap output to 20 lines.

## Launch Commands

Native runtime examples:

```bash
arbor setup
arbor doctor
arbor run "<contract>" --yes --yes-cwd <project> --config <config> --max-cycles 3
arbor report <project>/.arbor/sessions/<run_name>
```

Skill-only smoke tests should use `arbor-agent-tools` and a copied project
directory unless the user explicitly wants to modify the live repo.
