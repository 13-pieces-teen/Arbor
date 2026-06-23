"""``arbor.zoo`` — the benchmark format and its verifier.

A benchmark is a self-contained directory under ``arbor-zoo/``: a README whose YAML
front-matter is a tiny machine contract and whose body is prose, a PROVENANCE card, a
runnable baseline (one or more code files), and a protected eval entrypoint. This
package provides pack discovery + the contract (:mod:`~arbor.zoo.pack`) and the
``arbor benchmark verify`` gate (:mod:`~arbor.zoo.verify`). See ``docs/zoo.md``.
"""

from __future__ import annotations

from .pack import (
    EVAL_ENTRYPOINTS,
    Contract,
    PackSummary,
    discover_packs,
    find_eval_entrypoint,
    is_pack_dir,
    load_contract,
    read_front_matter,
)
from .verify import VerifyResult, verify_pack

__all__ = [
    "EVAL_ENTRYPOINTS",
    "Contract",
    "PackSummary",
    "VerifyResult",
    "discover_packs",
    "find_eval_entrypoint",
    "is_pack_dir",
    "load_contract",
    "read_front_matter",
    "verify_pack",
]
