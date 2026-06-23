"""Pack discovery + the README front-matter *contract* for the ``arbor-zoo`` format.

A *benchmark* is a directory under ``arbor-zoo/`` holding a self-contained task:
a ``README.md`` whose YAML **front-matter** is a tiny machine-readable contract and
whose body is human/agent prose, a ``PROVENANCE.md`` card, a runnable **baseline**
(one or more code files), and a protected eval entrypoint (``eval.sh``/``eval.py``)
that prints one ``score: <float>`` line for ``dev`` and ``test``.

There is no separate manifest file. The few facts a verifier and an unattended
harness genuinely need — and which prose cannot be checked against — live in the
README front-matter (metric direction, dev/test split, expected baseline, editable
surface). Everything human (setup, license, baseline write-up, contamination) lives
in prose in the README body and ``PROVENANCE.md``. See ``docs/zoo.md``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Eval entrypoints recognised by convention, in preference order.
EVAL_ENTRYPOINTS = ("eval.sh", "eval.py")

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


@dataclass(frozen=True)
class PackSummary:
    """Lightweight index entry for ``arbor benchmark list`` / the zoo README."""

    name: str
    description: str
    path: str


@dataclass
class Contract:
    """The README front-matter contract. Every field defaults empty so a partial
    contract still loads; the verifier decides whether an omission is fatal."""

    name: str = ""
    metric: dict[str, Any] = field(default_factory=dict)    # {direction}
    eval: dict[str, Any] = field(default_factory=dict)      # {cmd}  (optional; convention otherwise)
    splits: dict[str, Any] = field(default_factory=dict)    # {kind, dev, test}
    baseline: dict[str, Any] = field(default_factory=dict)  # {score, tolerance, kind}
    edit: list[str] = field(default_factory=list)           # editable globs (1+); rest is protected
    present: bool = False                                    # was there front-matter at all?


def read_front_matter(md_path: Path) -> tuple[dict[str, Any] | None, str]:
    """Split *md_path* into (front-matter dict | None, body).

    Front-matter is a leading ``---``-fenced YAML block. Returns ``(None, full_text)``
    when there is none.
    """
    if not md_path.exists():
        return None, ""
    text = md_path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return None, text
    try:
        import yaml
        data = yaml.safe_load(m.group(1))
    except ImportError:
        raise ImportError("PyYAML is required to read pack front-matter")
    if not isinstance(data, dict):
        return None, text
    return data, m.group(2)


def load_contract(pack_dir: Path) -> Contract:
    """Parse the README front-matter contract for *pack_dir* (empty if absent)."""
    data, _ = read_front_matter(pack_dir / "README.md")
    if data is None:
        return Contract()
    return Contract(
        name=data.get("name", pack_dir.name),
        metric=data.get("metric", {}) or {},
        eval=data.get("eval", {}) or {},
        splits=data.get("splits", {}) or {},
        baseline=data.get("baseline", {}) or {},
        edit=data.get("edit", []) or [],
        present=True,
    )


def find_eval_entrypoint(pack_dir: Path) -> str | None:
    """Return the eval entrypoint filename in *pack_dir*, or None if absent."""
    for name in EVAL_ENTRYPOINTS:
        if (pack_dir / name).exists():
            return name
    return None


def is_pack_dir(path: Path) -> bool:
    """True when *path* looks like a benchmark: a non-scaffold dir with a README
    and an eval entrypoint."""
    if not path.is_dir() or path.name.startswith((".", "_")):
        return False
    return (path / "README.md").exists() and find_eval_entrypoint(path) is not None


def _readme_description(pack_dir: Path) -> str:
    """First non-heading, non-blank line of the README body — a one-line description."""
    _, body = read_front_matter(pack_dir / "README.md")
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return "(no description)"


def discover_packs(zoo_dir: Path) -> list[PackSummary]:
    """Return every benchmark under *zoo_dir*, skipping ``_``-prefixed scaffolds."""
    out: list[PackSummary] = []
    if not zoo_dir.exists() or not zoo_dir.is_dir():
        return out
    for child in sorted(zoo_dir.iterdir()):
        if not is_pack_dir(child):
            continue
        out.append(PackSummary(
            name=child.name,
            description=_readme_description(child),
            path=str(child),
        ))
    return sorted(out, key=lambda p: p.name)
