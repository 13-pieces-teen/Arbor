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


def test_path_split_creates_data_dirs(tmp_path: Path) -> None:
    res = scaffold_benchmark(tmp_path, name="demo", metric_direction="minimize",
                             splits=_PATH_SPLITS, style="light")
    assert "data/dev/.gitkeep" in res.created
    assert "data/test/.gitkeep" in res.created


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
