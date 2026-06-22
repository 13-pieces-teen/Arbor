"""Build a WebUI snapshot from a *durable session directory* (no live runtime).

The push-based WebUI (:mod:`arbor.webui.server`) normally renders a live
``RunState`` fed by the native runtime's ``EventBus``. When a host coding agent
drives the loop instead, there is no orchestrator and no bus — the host agent
mutates session state through the ``arbor mcp`` tools, which persist to
``.arbor/sessions/<run>/``. This module reads that on-disk state and produces the
*same* snapshot dict shape the browser already understands
(:func:`arbor.webui.snapshot.empty_state_dict`), so the existing page renders
progress with no changes.

It is read-only and polled (the server's heartbeat calls it every ~1.5s), so the
browser reflects tree updates as the host agent makes them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .snapshot import empty_state_dict


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object, returning ``{}`` on any missing/invalid file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _node_to_tree_entry(node: dict[str, Any]) -> dict[str, Any]:
    """Map a stored IdeaTree node onto the browser's tree-entry shape.

    Mirrors the live ``snapshot._idea_to_dict`` contract. Timing fields
    (runtime/finished_elapsed) are unknown without a live run, so they are None.
    """
    return {
        "node_id": node.get("id"),
        "hypothesis": node.get("hypothesis", ""),
        "status": node.get("status", "pending"),
        "score": node.get("score"),
        "branch": node.get("code_ref"),
        "parent_id": node.get("parent_id"),
        "runtime_seconds": None,
        "finished_elapsed": None,
        "pruned_reason": node.get("pruned_reason"),
        "insight": node.get("insight") or None,
    }


def _best_score(meta: dict[str, Any], nodes: list[dict[str, Any]]) -> float | None:
    """Best score so far: prefer the recorded trunk score, else compute it.

    Falls back to the best score among completed/merged nodes, honouring
    ``metric_direction``.
    """
    trunk = meta.get("trunk_score")
    if isinstance(trunk, (int, float)):
        return float(trunk)
    scored = [
        float(n["score"])
        for n in nodes
        if isinstance(n.get("score"), (int, float)) and n.get("status") in ("done", "merged")
    ]
    if not scored:
        return None
    return min(scored) if meta.get("metric_direction") == "minimize" else max(scored)


def build_session_snapshot(session_dir: Path, run_name: str | None = None) -> dict[str, Any]:
    """Return a browser snapshot dict for the session at *session_dir*.

    Reads ``.coordinator/idea_tree.json`` (nodes + meta) and the optional
    ``run_info.json``. Always returns a valid snapshot — missing or partial
    sessions degrade gracefully to the empty shape.
    """
    session_dir = Path(session_dir)
    state = empty_state_dict()
    state["run_name"] = run_name or session_dir.name
    state["phase"] = "monitoring"

    run_info = _load_json(session_dir / "run_info.json")
    if run_info:
        state["task"] = run_info.get("task", "")
        state["cwd"] = run_info.get("cwd", "")
        state["model"] = run_info.get("model", "—")

    tree_json = _load_json(session_dir / ".coordinator" / "idea_tree.json")
    nodes_map: dict[str, Any] = tree_json.get("nodes", {}) if isinstance(tree_json.get("nodes"), dict) else {}
    meta: dict[str, Any] = tree_json.get("meta", {}) if isinstance(tree_json.get("meta"), dict) else {}
    root_id = tree_json.get("root_id", "ROOT")

    # Non-root nodes, preserving insertion order for a stable display.
    nodes = [n for nid, n in nodes_map.items() if nid != root_id and isinstance(n, dict)]

    # Root hypothesis is the research task when run_info didn't supply one.
    if not state["task"]:
        root = nodes_map.get(root_id, {})
        state["task"] = root.get("hypothesis", "") if isinstance(root, dict) else ""

    def _count(status: str) -> int:
        return sum(1 for n in nodes if n.get("status") == status)

    state["counters"] = {
        "proposed": len(nodes),
        "done": _count("done"),
        "pruned": _count("pruned"),
        "merged": _count("merged"),
        "running": _count("running"),
    }
    state["baseline_score"] = meta.get("baseline_score")
    state["metric_direction"] = meta.get("metric_direction", "maximize")
    state["best_score"] = _best_score(meta, nodes)
    state["tree"] = [_node_to_tree_entry(n) for n in nodes]
    return state
