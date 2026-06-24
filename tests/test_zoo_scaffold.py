"""Tests for the zoo scaffolder (``arbor.zoo.scaffold``)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from arbor.zoo import ScaffoldResult, scaffold_benchmark, verify_pack

_SEED_SPLITS = {
    "kind": "seed_range",
    "dev": {"base": 1000, "count": 3},
    "test": {"base": 9000, "count": 3},
}
_PATH_SPLITS = {"kind": "path", "dev": ["data/dev/**"], "test": ["data/test/**"]}


def test_light_scaffold_creates_eval_split_and_solution(tmp_path: Path) -> None:
    res = scaffold_benchmark(
        tmp_path, name="demo", metric_direction="maximize",
        splits=_SEED_SPLITS, style="light",
    )
    assert isinstance(res, ScaffoldResult)
    assert "eval.py" in res.created
    assert "solution.py" in res.created
    assert (tmp_path / "eval.py").exists()
    assert (tmp_path / "solution.py").exists()
    assert res.verify == []  # light style does not verify


def test_light_eval_template_prints_parseable_score(tmp_path: Path) -> None:
    scaffold_benchmark(tmp_path, name="demo", metric_direction="maximize",
                       splits=_SEED_SPLITS, style="light")
    proc = subprocess.run(
        [sys.executable, str(tmp_path / "eval.py"), "--split", "dev"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "score:" in proc.stdout


def test_zoo_readme_run_commands_match_entrypoint(tmp_path: Path) -> None:
    # eval.sh entrypoint → the README "Run the baseline" block uses bash eval.sh,
    # not python eval.py.
    scaffold_benchmark(tmp_path / "sh", name="demo", metric_direction="maximize",
                       splits=_SEED_SPLITS, style="zoo", eval_entrypoint="eval.sh")
    readme = (tmp_path / "sh" / "README.md").read_text()
    assert "bash eval.sh dev" in readme and "python eval.py" not in readme
    # eval.py entrypoint → python eval.py
    scaffold_benchmark(tmp_path / "py", name="demo", metric_direction="maximize",
                       splits=_SEED_SPLITS, style="zoo", eval_entrypoint="eval.py")
    assert "python eval.py --split dev" in (tmp_path / "py" / "README.md").read_text()


def test_path_split_creates_data_dirs(tmp_path: Path) -> None:
    res = scaffold_benchmark(tmp_path, name="demo", metric_direction="minimize",
                             splits=_PATH_SPLITS, style="light")
    # Visible placeholders (not hidden .gitkeep) so path globs can match them.
    assert "data/dev/example_001.txt" in res.created
    assert "data/test/example_001.txt" in res.created


def test_zoo_path_split_passes_structural_verify(tmp_path: Path) -> None:
    # Regression: path-kind zoo packs must also pass splits-disjoint, which
    # requires glob-matchable (non-dotfile) data instances on both sides.
    scaffold_benchmark(tmp_path, name="demo", metric_direction="maximize",
                       splits=_PATH_SPLITS, style="zoo")
    results = verify_pack(tmp_path, run_eval=False)
    fails = [r for r in results if r.status == "fail"]
    assert not fails, f"path-kind structural verify failed: {[(r.name, r.message) for r in fails]}"


def test_generated_eval_sh_uses_lf_line_endings(tmp_path: Path) -> None:
    # Regression: a CRLF shebang ("…bash\r") is a broken interpreter on Unix.
    scaffold_benchmark(tmp_path, name="demo", metric_direction="maximize",
                       splits=_SEED_SPLITS, style="light", eval_entrypoint="eval.sh")
    raw = (tmp_path / "eval.sh").read_bytes()
    assert b"\r\n" not in raw
    assert raw.split(b"\n", 1)[0] == b"#!/usr/bin/env bash"


def test_zoo_scaffold_passes_structural_verify(tmp_path: Path) -> None:
    res = scaffold_benchmark(
        tmp_path, name="demo", metric_direction="maximize",
        splits=_SEED_SPLITS, baseline={"score": 0.0, "tolerance": 0.0, "kind": "exact"},
        edit=["solution.py"], style="zoo",
    )
    assert "README.md" in res.created
    assert "PROVENANCE.md" in res.created
    # Re-verify directly to prove the round-trip is real (not just trusting res.verify).
    results = verify_pack(tmp_path, run_eval=False)
    fails = [r for r in results if r.status == "fail"]
    assert not fails, f"structural verify failed: {[(r.name, r.message) for r in fails]}"


def test_scaffold_is_idempotent(tmp_path: Path) -> None:
    scaffold_benchmark(tmp_path, name="demo", metric_direction="maximize",
                       splits=_SEED_SPLITS, style="zoo")
    res2 = scaffold_benchmark(tmp_path, name="demo", metric_direction="maximize",
                              splits=_SEED_SPLITS, style="zoo")
    assert res2.created == []
    assert "solution.py" in res2.skipped


def test_invalid_style_and_direction_raise(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        scaffold_benchmark(tmp_path, name="x", metric_direction="maximize",
                           splits=_SEED_SPLITS, style="bogus")
    with pytest.raises(ValueError):
        scaffold_benchmark(tmp_path, name="x", metric_direction="up",
                           splits=_SEED_SPLITS, style="light")
