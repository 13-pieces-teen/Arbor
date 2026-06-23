"""`arbor benchmark` — verify and list Task Packs in the zoo.

Two subcommands:

* ``arbor benchmark verify <pack-dir>`` — run the gate that decides whether a pack
  is allowed into the zoo. Exits non-zero if any check fails.
* ``arbor benchmark list [zoo-dir]`` — print a plain index of packs (not a ranked
  leaderboard).
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...zoo import VerifyResult, discover_packs, find_eval_entrypoint, verify_pack

benchmark_app = typer.Typer(
    name="benchmark",
    help="Verify and list Task Packs in the arbor-zoo benchmark format.",
    no_args_is_help=True,
)


def _render(r: VerifyResult) -> None:
    if r.status == "pass":
        typer.secho(f"  [ok]   {r.name}: {r.message}", fg=typer.colors.GREEN)
    elif r.status == "warn":
        typer.secho(f"  [warn] {r.name}: {r.message}", fg=typer.colors.YELLOW)
        if r.hint:
            typer.echo(f"         hint: {r.hint}")
    else:
        typer.secho(f"  [fail] {r.name}: {r.message}", fg=typer.colors.RED, err=True)
        if r.hint:
            typer.secho(f"         hint: {r.hint}", fg=typer.colors.RED, err=True)


@benchmark_app.command("verify")
def verify_command(
    pack_dir: Path = typer.Argument(
        ...,
        help="Path to the benchmark directory (with README.md + eval.sh/eval.py).",
    ),
    no_eval: bool = typer.Option(
        False, "--no-eval",
        help="Skip the eval-running checks (structural validation only).",
    ),
    timeout: int = typer.Option(
        600, "--timeout",
        help="Per-eval timeout in seconds.",
    ),
) -> None:
    """Verify a Task Pack against the zoo format. Exits 1 if any check fails."""
    target = pack_dir.resolve()
    if not target.is_dir():
        typer.secho(f"error: not a directory: {target}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    if not (target / "README.md").exists() or find_eval_entrypoint(target) is None:
        typer.secho(
            f"error: {target} is not a benchmark (needs README.md + eval.sh/eval.py)",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=2)

    typer.echo(f"verifying {target.name} …")
    results = verify_pack(target, run_eval=not no_eval, timeout=timeout)
    for r in results:
        _render(r)

    fails = [r for r in results if r.status == "fail"]
    warns = [r for r in results if r.status == "warn"]
    if fails:
        typer.secho(
            f"\n{len(fails)} check(s) failed — pack does NOT enter the zoo.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    typer.secho(
        f"\nall checks passed ({len(warns)} advisory warning(s) — human review still required).",
        fg=typer.colors.GREEN,
    )


@benchmark_app.command("list")
def list_command(
    zoo_dir: Path = typer.Argument(
        Path("arbor-zoo"),
        help="The zoo directory to index (default: ./arbor-zoo).",
    ),
) -> None:
    """List the packs in a zoo directory (a plain index, not a leaderboard)."""
    target = zoo_dir.resolve()
    packs = discover_packs(target)
    if not packs:
        typer.echo(f"(no packs found in {target})")
        raise typer.Exit(code=0)
    typer.echo(f"# packs in {target}\n")
    width = max(len(p.name) for p in packs)
    for p in packs:
        typer.echo(f"  {p.name.ljust(width)}  {p.description}")
