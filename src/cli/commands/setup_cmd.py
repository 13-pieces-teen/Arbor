"""`arbor setup` — interactive one-time configuration wizard.

A first-time user runs ``arbor`` (or ``arbor setup``) and answers a few prompts;
we write ``~/.arbor/config.yaml`` so subsequent runs need no flags. The wizard is
the interactive sibling of the flag-driven ``arbor config init`` and shares its
writer (:func:`write_user_llm_config`) so both produce the same file shape.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ..._app import GLOBAL_CONFIG_FILE
from .._constants import (
    DEFAULT_CLAUDE_MODEL,
    PROVIDER_CHOICES,
    default_model_for_provider,
)
from .config_cmd import write_user_llm_config


def run_setup_wizard(*, force: bool = False) -> bool:
    """Interactively collect LLM settings and write the global config.

    Returns True if a config was written, False if the user aborted (e.g. an
    existing config and they declined to overwrite). Reuses
    :func:`write_user_llm_config` so the file matches ``arbor config init``.
    """
    from ..style import console as _console

    if GLOBAL_CONFIG_FILE.exists() and not force:
        _console.print(f"\n[yellow]A config already exists at[/] {GLOBAL_CONFIG_FILE}")
        if not typer.confirm("Overwrite it?", default=False):
            _console.print("[dim]Keeping the existing config. Run `arbor config show` to view it.[/]")
            return False

    _console.print()
    _console.print("[bold cyan]arbor setup[/] — let's configure your model (one time).")
    _console.print("[dim]Press Enter to accept each default. Stored in "
                   f"{GLOBAL_CONFIG_FILE}.[/]\n")

    # 1. API type / provider
    _console.print(
        "[dim]API type:\n"
        "  [bold]auto[/bold]             let Arbor detect it — probes the endpoint's Responses\n"
        "                   API and uses it when available, else chat completions\n"
        "  [bold]openai-responses[/bold] OpenAI / o-series via the Responses API (reasoning chain)\n"
        "  [bold]openai-chat[/bold]      any OpenAI-compatible endpoint (DeepSeek / Qwen / GLM / …)\n"
        "  [bold]anthropic[/bold]        Claude via the native Anthropic API[/]"
    )
    provider = _prompt_choice(
        "API type",
        choices=list(PROVIDER_CHOICES),
        default="auto",
    )

    # 2. base_url (local proxy / vLLM / official API)
    base_url = typer.prompt(
        "Base URL (local proxy / vLLM, blank for the official API)",
        default="",
        show_default=False,
    ).strip()

    # 3. model
    suggested_model = default_model_for_provider(provider) or DEFAULT_CLAUDE_MODEL
    model = typer.prompt("Model", default=suggested_model).strip() or suggested_model

    # 4. api_key (hidden; blank keeps env-var auth)
    api_key = typer.prompt(
        "API key (blank to read from the environment; local proxies often accept dummy)",
        default="",
        hide_input=True,
        show_default=False,
    ).strip()

    llm: dict[str, str] = {"provider": provider, "model": model}
    if base_url:
        llm["base_url"] = base_url
    if api_key:
        llm["api_key"] = api_key

    _console.print()
    write_user_llm_config(llm)

    _probe_credentials(provider, api_key or None)
    _console.print(
        f"\n[green]Done.[/] Saved to [bold]{GLOBAL_CONFIG_FILE}[/] "
        "([dim]view it anytime with[/] [bold]arbor config show[/])."
    )
    _console.print("Just run [bold]arbor[/] to start a session.\n")
    return True


def _probe_credentials(provider: str, api_key: str | None) -> None:
    """Best-effort: confirm a key is resolvable (env or entered). Never raises."""
    from ..preflight import PreflightChecker
    from ..style import console as _console

    try:
        result = PreflightChecker(
            cwd=Path.cwd(), provider=provider, explicit_api_key=api_key,
        ).check_llm_credentials(render=False)
    except Exception:
        return
    if result.status == "fail":
        _console.print(f"[yellow]![/] {result.message}")
        if result.hint:
            _console.print(f"  [dim]{result.hint}[/]")
    else:
        _console.print("[green]✓[/] credentials look resolvable")


def _prompt_choice(label: str, *, choices: list[str], default: str) -> str:
    """Prompt until the answer is one of ``choices`` (case-insensitive)."""
    options = "/".join(choices)
    while True:
        ans = typer.prompt(f"{label} ({options})", default=default).strip().lower()
        if ans in choices:
            return ans
        typer.secho(f"  please choose one of: {options}", fg=typer.colors.YELLOW)


def setup_command(
    force: bool = typer.Option(
        False, "--force",
        help="Re-run setup even if a config already exists (overwrites it).",
    ),
) -> None:
    """Interactively configure arbor (writes ~/.arbor/config.yaml)."""
    wrote = run_setup_wizard(force=force)
    raise typer.Exit(code=0 if wrote else 1)
