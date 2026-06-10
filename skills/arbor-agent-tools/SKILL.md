---
name: arbor-agent-tools
description: "Deterministic helper layer for emulating Arbor/research_agent tools in Codex or Claude Code when native TreeView, TreeAddNode, TreeSetMeta, RunExecutor, GitMergeBranch, or report tooling is unavailable. Use for local state management, eval score capture, executor prompt generation, merge checks, and skill forward tests."
---

# Arbor Agent Tools

Use this skill when the host does not provide native Arbor tools. The bundled
script stores state in the same style as open-source Arbor:

```text
<cwd>/.arbor/sessions/<run_name>/.coordinator/idea_tree.json
<cwd>/.arbor/sessions/<run_name>/.coordinator/idea_tree.md
```

## Script

`scripts/arbor_state.py` is stdlib-only.

Common commands:

```bash
python scripts/arbor_state.py init --cwd <project> --run-name <run> --task "<contract>"
python scripts/arbor_state.py view --cwd <project> --run-name <run> --format constraints
python scripts/arbor_state.py meta --cwd <project> --run-name <run> --set baseline_score=42 --set trunk_score=42
python scripts/arbor_state.py add --cwd <project> --run-name <run> --parent-id ROOT --hypothesis "<four-line hypothesis>"
python scripts/arbor_state.py update --cwd <project> --run-name <run> --node-id 1 --status done --score 45 --insight "..."
python scripts/arbor_state.py prompt-executor --cwd <project> --run-name <run> --node-id 1
python scripts/arbor_state.py prompt-executor --cwd <project> --run-name <run> --node-id 1 --smoke
python scripts/arbor_state.py record --cwd <project> --run-name <run> --node-id 1 --score 45 --insight "..." --result "..."
python scripts/arbor_state.py eval --cwd <project> --run-name <run> --split dev --cmd "bash {cwd}/eval.sh" --set-meta baseline
python scripts/arbor_state.py parse-log --log <project>/run.log --metric val_bpb
python scripts/arbor_state.py report --cwd <project> --run-name <run>
```

Read `references/tool-mapping.md` when deciding which script command maps to a
native Arbor tool.

## State Rules

- Keep scores absolute.
- Keep eval commands templated with `{cwd}` and `{node_id}`.
- Do not run B_test during executor iteration.
- Use `record` for executor outcomes so artifacts and tree updates stay in
  one place.
- Use `check` before trusting a hand-edited tree.

## Forward Testing

For a smoke test, copy the target project to `/tmp`, initialize a short run,
record metadata, add one idea, generate an executor prompt, and run only cheap
commands. Do not run full long training unless explicitly requested.

Smoke-specific rules:

- Use `prompt-executor --smoke`.
- If a real eval command invokes training, data prep, downloads, GPU work, or a
  minute-scale benchmark, do not execute it; store a cached-score parser,
  harmless echo, or mocked score instead.
- Parse existing logs with `parse-log`; it normalizes carriage-return progress
  logs before extracting metrics. Avoid full `cat`, raw `rg`, raw `grep`, or
  `tail` output; cap diagnostic log snippets at 20 lines.
- Finish with `check` and `report` so the smoke produces a real `REPORT.md`.
