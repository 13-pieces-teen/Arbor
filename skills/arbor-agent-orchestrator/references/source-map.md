# Open-Source Research Agent Source Map

Use this file when auditing the skill suite against the `open-source` branch.

## Entry Points

- `README.md`: product behavior, CLI commands, session layout, B_dev/B_test
  discipline, long-running experiment policy.
- `research_agent/cli/commands/run.py`: `arbor run`, intake, preflight,
  Research Contract, session directory, EventBus, dashboard, report, resume.
- `research_agent/cli/intake/system_prompt.py`: planning assistant contract
  and fast-path behavior.
- `research_agent/cli/intake/launch_tool.py`: `LaunchExperiment` schema.
- `research_agent/cli/preflight.py`: LLM/cwd/git/eval checks.
- `research_agent/cli/branch_guard.py`: base-branch guard.

## Coordinator

- `research_agent/coordinator/orchestrator.py`: single persistent ReAct loop,
  gitignore enforcement, dirty repo check, trunk checkout, lifecycle hooks,
  tree init/resume, plugin eval contract, checkpoint writes, final report.
- `research_agent/coordinator/prompts.py`: coordinator identity and full Arbor
  cycle protocol.
- `research_agent/coordinator/config.py`: config, budget policy, search config,
  skill flags, tree paths.
- `research_agent/coordinator/idea_tree.py`: `IdeaTree.VERSION = 3`, node
  fields, metadata defaults, rendering, constraints view.
- `research_agent/coordinator/checkpoint.py`: checkpoint and messages schema.

## Coordinator Tools

- `research_agent/coordinator/tools/tree_ops.py`: `TreeView`, `TreeAddNode`,
  `TreeUpdateNode`, `TreePrune`, `TreeSetMeta`, `TreePropagate`.
- `research_agent/coordinator/tools/executor_run.py`: `RunExecutor`,
  `RunExecutorParallel`, worktree lifecycle, executor prompt, artifact saving,
  report parsing, cycle caps, HITL review gates.
- `research_agent/coordinator/tools/git_ops.py`: `GitMergeBranch`, protected
  branch guard, B_test worktree eval, retry/backoff, protected paths, required
  outputs, medal handling.
- `research_agent/coordinator/tools/search_ctx.py`: `SearchIdeaContext`,
  `SearchIdeaContextParallel`, `SearchStatus`, background SearchAgent tasks,
  validated-node gate.

## Executor

- `research_agent/executor/prompts.py`: executor identity, code discipline,
  workflow, RunTraining policy, report format.
- `research_agent/core/tools/run_training.py`: long command execution, metric
  extraction, idle timeout, partial log handling.
- `research_agent/core/git_artifacts.py`: commit/artifact path filtering.

## Skills And Plugins

- `research_agent/core/skill_registry.py`: built-in and project skill loading.
- `research_agent/core/tools/skill.py`: `LoadSkill` tool.
- `research_agent/skills/idea_drafting.md`: strict IDEATE methodology.
- `research_agent/skills/first_principles_probe.md`: diagnostic probe.
- `research_agent/plugins/base.py`: plugin schema and load/discover logic.
- `research_agent/plugins/mle_kaggle.yaml`: performance-first plugin,
  eval contract, protected paths, required outputs, profiles, lifecycle
  behavior.
- `docs/plugins.md`: user-facing plugin and skill contract.

## Reports And Observability

- `research_agent/events/types.py`: event names.
- `research_agent/events/payloads.py`: typed payload contract.
- `research_agent/report/generator.py`: `REPORT.md` rendering from session
  artifacts.
- `research_agent/cli/run_dashboard.py`, `research_agent/webui/*`: dashboard
  and browser monitor behavior.

## Key Differences From The Wrong Single-Skill Extraction

- The open-source branch uses the `arbor` CLI, intake planning, session
  directories, dashboard, EventBus, checkpoint/resume, plugins, and reports.
- IDEATE is skill-driven through `LoadSkill("idea_drafting")` unless disabled
  by config/plugin.
- Executors are isolated worktree agents with automatic eval metadata
  injection, artifact capture, and insight propagation.
- Related-work search is a background SearchAgent with a validated-node gate.
- Merge is not a shell `git merge`; it auto-runs B_test and enforces guards.
- Long experiments should use `RunTraining`, not polling loops.
