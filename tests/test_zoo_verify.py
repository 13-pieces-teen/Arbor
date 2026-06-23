"""Tests for the zoo verifier (``arbor.zoo.verify``).

Each test builds a minimal valid benchmark in ``tmp_path`` and toggles a single defect,
asserting the relevant check flips to ``fail`` (or ``warn``). The default ``eval.sh``
prints a constant ``score: 1.0`` so eval-running checks are fast and deterministic.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from arbor.zoo import verify_pack

_CONTRACT: dict = {
    "name": "demo",
    "metric": {"direction": "maximize"},
    "splits": {"kind": "seed_range", "dev": {"base": 1000, "count": 3},
               "test": {"base": 9000, "count": 3}},
    "baseline": {"score": 1.0, "tolerance": 0.0, "kind": "exact"},
    "edit": ["solution.py"],
}
_BODY = (
    "# demo\n\nA demo benchmark.\n\n## Task & metric\nx\n## Run the baseline\nx\n"
    "## Optimize with Arbor\nx\n## Provenance\nx\n"
)
_PROVENANCE = (
    "# Provenance\n\n## Source\nx\n## Setup & environment\nx\n## Data source & license\nx\n"
    "## Baseline implementation\nx\n## Baseline reproduction\nx\n"
    "## Contamination assessment\nx\n## Caveats\nx\n"
)
_EVAL_OK = '#!/usr/bin/env bash\necho "score: 1.0"\n'


def _build(tmp_path: Path, *, contract: dict | None = "default", body: str = _BODY,
           provenance: str = _PROVENANCE, eval_sh: str | None = _EVAL_OK,
           eval_py: str | None = None, files: dict | None = None) -> Path:
    pack = tmp_path / "demo"
    pack.mkdir(parents=True, exist_ok=True)
    c = copy.deepcopy(_CONTRACT) if contract == "default" else contract
    readme = _BODY if c is None else f"---\n{yaml.safe_dump(c)}---\n{body}"
    (pack / "README.md").write_text(readme)
    (pack / "PROVENANCE.md").write_text(provenance)
    (pack / "solution.py").write_text("# baseline\n")
    if eval_sh is not None:
        (pack / "eval.sh").write_text(eval_sh)
    if eval_py is not None:
        (pack / "eval.py").write_text(eval_py)
    for rel, content in (files or {}).items():
        f = pack / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    return pack


def _by_name(results) -> dict:
    return {r.name: r for r in results}


# ── happy path ────────────────────────────────────────────────────────────────

def test_valid_pack_has_no_fails(tmp_path: Path) -> None:
    results = verify_pack(_build(tmp_path))
    fails = [(r.name, r.message) for r in results if r.status == "fail"]
    assert fails == [], f"unexpected fails: {fails}"
    assert {r.name for r in results if r.status == "warn"} == {"contamination"}


# ── contract (front-matter) ───────────────────────────────────────────────────

def test_missing_front_matter_fails(tmp_path: Path) -> None:
    r = _by_name(verify_pack(_build(tmp_path, contract=None)))["contract"]
    assert r.status == "fail" and "front-matter" in r.message


def test_missing_contract_field_fails(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    del c["baseline"]["score"]
    r = _by_name(verify_pack(_build(tmp_path, contract=c)))["contract"]
    assert r.status == "fail" and "baseline.score" in r.message


def test_bad_metric_direction_fails(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    c["metric"]["direction"] = "highest"
    r = _by_name(verify_pack(_build(tmp_path, contract=c)))["contract"]
    assert r.status == "fail" and "metric.direction" in r.message


# ── sections ──────────────────────────────────────────────────────────────────

def test_missing_readme_section_fails(tmp_path: Path) -> None:
    body = _BODY.replace("## Optimize with Arbor\nx\n", "")
    r = _by_name(verify_pack(_build(tmp_path, body=body)))["readme-sections"]
    assert r.status == "fail" and "Optimize" in r.message


def test_missing_provenance_heading_fails(tmp_path: Path) -> None:
    prov = _PROVENANCE.replace("## Baseline implementation\nx\n", "")
    r = _by_name(verify_pack(_build(tmp_path, provenance=prov)))["provenance"]
    assert r.status == "fail" and "Baseline implementation" in r.message


# ── splits disjoint ───────────────────────────────────────────────────────────

def test_seed_ranges_overlap_fails(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    c["splits"]["test"] = {"base": 1001, "count": 3}
    r = _by_name(verify_pack(_build(tmp_path, contract=c)))["splits-disjoint"]
    assert r.status == "fail" and "overlap" in r.message


def test_path_splits_disjoint_pass(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    c["splits"] = {"kind": "path", "dev": ["data/dev/**"], "test": ["data/test/**"]}
    pack = _build(tmp_path, contract=c, files={"data/dev/a.txt": "1", "data/test/b.txt": "2"})
    assert _by_name(verify_pack(pack))["splits-disjoint"].status == "pass"


# ── edit surface ──────────────────────────────────────────────────────────────

def test_edit_pattern_matches_nothing_fails(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    c["edit"] = ["does_not_exist.py"]
    r = _by_name(verify_pack(_build(tmp_path, contract=c)))["edit-surface"]
    assert r.status == "fail"


def test_editable_harness_fails(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    c["edit"] = ["solution.py", "eval.sh"]  # eval.sh must stay protected
    r = _by_name(verify_pack(_build(tmp_path, contract=c)))["edit-surface"]
    assert r.status == "fail" and "eval.sh" in r.message


# ── eval running ──────────────────────────────────────────────────────────────

def test_eval_without_score_fails(tmp_path: Path) -> None:
    r = _by_name(verify_pack(_build(tmp_path, eval_sh='#!/usr/bin/env bash\necho "nope"\n')))
    assert r["eval-dev"].status == "fail"


def test_eval_py_entrypoint_works(tmp_path: Path) -> None:
    r = _by_name(verify_pack(_build(tmp_path, eval_sh=None, eval_py='print("score: 1.0")\n')))
    assert r["eval-dev"].status == "pass" and r["eval-test"].status == "pass"


# ── baseline reproduction ─────────────────────────────────────────────────────

def test_baseline_out_of_tolerance_fails(tmp_path: Path) -> None:
    r = _by_name(verify_pack(_build(tmp_path, eval_sh='#!/usr/bin/env bash\necho "score: 2.0"\n')))
    assert r["baseline-reproduces"].status == "fail"


# ── determinism ───────────────────────────────────────────────────────────────

def test_nondeterministic_exact_fails(tmp_path: Path) -> None:
    r = _by_name(verify_pack(_build(tmp_path, eval_sh='#!/usr/bin/env bash\necho "score: ${RANDOM}.0"\n')))
    assert r["determinism"].status == "fail"


def test_timing_metric_within_tolerance_pass(tmp_path: Path) -> None:
    c = copy.deepcopy(_CONTRACT)
    c["baseline"] = {"score": 1.0, "tolerance": 0.15, "kind": "timing"}
    assert _by_name(verify_pack(_build(tmp_path, contract=c)))["determinism"].status == "pass"


# ── run_eval=False ────────────────────────────────────────────────────────────

def test_no_eval_flag_skips_eval_checks(tmp_path: Path) -> None:
    r = _by_name(verify_pack(_build(tmp_path), run_eval=False))
    assert r["eval-dev"].status == "warn" and r["baseline-reproduces"].status == "warn"
    assert r["splits-disjoint"].status == "pass"  # structural still runs
