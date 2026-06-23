"""Tests for zoo pack discovery + front-matter contract (``arbor.zoo.pack``)."""

from __future__ import annotations

from pathlib import Path

from arbor.zoo import (
    discover_packs,
    find_eval_entrypoint,
    is_pack_dir,
    load_contract,
    read_front_matter,
)

_FM = """\
---
name: demo
metric: {direction: maximize}
splits: {kind: seed_range, dev: {base: 1000, count: 3}, test: {base: 9000, count: 3}}
baseline: {score: 1.0, tolerance: 0.1, kind: timing}
edit: [solution.py]
---
# title

A demo benchmark.
"""


def _make_pack(zoo: Path, name: str, *, readme: str = _FM, entry: str = "eval.sh") -> Path:
    pack = zoo / name
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "README.md").write_text(readme, encoding="utf-8")
    (pack / entry).write_text("echo 'score: 1.0'\n", encoding="utf-8")
    return pack


def test_is_pack_dir(tmp_path: Path) -> None:
    assert is_pack_dir(_make_pack(tmp_path, "demo"))


def test_is_pack_dir_requires_readme_and_eval(tmp_path: Path) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    assert not is_pack_dir(bare)
    (bare / "README.md").write_text("# x")
    assert not is_pack_dir(bare)  # README but no eval entrypoint


def test_find_eval_entrypoint_prefers_sh(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    pack.mkdir()
    (pack / "eval.py").write_text("x")
    assert find_eval_entrypoint(pack) == "eval.py"
    (pack / "eval.sh").write_text("x")
    assert find_eval_entrypoint(pack) == "eval.sh"


def test_read_front_matter(tmp_path: Path) -> None:
    md = tmp_path / "README.md"
    md.write_text(_FM)
    fm, body = read_front_matter(md)
    assert fm is not None and fm["name"] == "demo"
    assert "A demo benchmark." in body
    assert "---" not in body  # front-matter stripped from the body


def test_read_front_matter_absent(tmp_path: Path) -> None:
    md = tmp_path / "README.md"
    md.write_text("# no front matter\n\nbody")
    fm, body = read_front_matter(md)
    assert fm is None and "body" in body


def test_load_contract(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path, "demo")
    c = load_contract(pack)
    assert c.present
    assert c.metric["direction"] == "maximize"
    assert c.splits["kind"] == "seed_range"
    assert c.baseline["score"] == 1.0
    assert c.edit == ["solution.py"]


def test_load_contract_absent_is_not_present(tmp_path: Path) -> None:
    pack = _make_pack(tmp_path, "demo", readme="# no front matter\n\nbody\n")
    assert load_contract(pack).present is False


def test_discover_skips_underscore_and_non_packs(tmp_path: Path) -> None:
    _make_pack(tmp_path, "real")
    _make_pack(tmp_path, "_template")
    (tmp_path / "not_a_pack").mkdir()
    (tmp_path / "README.md").write_text("index", encoding="utf-8")
    assert [p.name for p in discover_packs(tmp_path)] == ["real"]


def test_discover_description_from_body(tmp_path: Path) -> None:
    _make_pack(tmp_path, "demo")
    assert discover_packs(tmp_path)[0].description == "A demo benchmark."


def test_discover_empty_dir(tmp_path: Path) -> None:
    assert discover_packs(tmp_path / "missing") == []
