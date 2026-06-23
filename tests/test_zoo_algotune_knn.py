"""End-to-end: the shipped ``arbor-zoo`` packs verify clean.

Runs the real verifier (which executes each pack's ``eval.sh``) against the packs
checked into the repo, plus the CLI exit-code contract. Skipped where numpy is
unavailable, since the algotune_knn eval needs it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from arbor.cli.app import app
from arbor.zoo import discover_packs, verify_pack

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ZOO = _REPO_ROOT / "arbor-zoo"


def _eval_python_has_numpy() -> bool:
    """The pack's eval.sh runs under ``python3`` (not the test runner), so probe
    that interpreter — numpy may be present there even when the runner lacks it."""
    py = shutil.which("python3") or shutil.which("python")
    if not py:
        return False
    return subprocess.run([py, "-c", "import numpy"], capture_output=True).returncode == 0


requires_numpy = pytest.mark.skipif(
    not _eval_python_has_numpy(),
    reason="zoo eval needs numpy in python3",
)
requires_zoo = pytest.mark.skipif(not _ZOO.is_dir(), reason="arbor-zoo not present")


@requires_zoo
@requires_numpy
def test_algotune_knn_verifies_clean() -> None:
    results = verify_pack(_ZOO / "algotune_knn")
    fails = [(r.name, r.message) for r in results if r.status == "fail"]
    assert fails == [], f"algotune_knn should verify clean, got fails: {fails}"


@requires_zoo
@requires_numpy
def test_every_shipped_pack_verifies() -> None:
    """The CI gate: no unverified pack enters the zoo."""
    packs = discover_packs(_ZOO)
    assert packs, "expected at least one pack in arbor-zoo"
    for summary in packs:
        results = verify_pack(Path(summary.path))
        fails = [(r.name, r.message) for r in results if r.status == "fail"]
        assert fails == [], f"pack {summary.name} has failures: {fails}"


@requires_zoo
@requires_numpy
def test_cli_verify_exit_code_zero() -> None:
    result = CliRunner().invoke(app, ["benchmark", "verify", str(_ZOO / "algotune_knn")])
    assert result.exit_code == 0, result.output


def test_cli_verify_missing_pack_errors(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["benchmark", "verify", str(tmp_path)])
    assert result.exit_code == 2  # not a benchmark dir (no README/eval here)
