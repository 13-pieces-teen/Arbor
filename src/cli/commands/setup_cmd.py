"""`arbor setup` — interactive one-time configuration wizard.

A first-time user runs ``arbor`` (or ``arbor setup``) and answers a few prompts;
we write ``~/.arbor/config.yaml`` so subsequent runs need no flags. The wizard is
the interactive sibling of the flag-driven ``arbor config init`` and shares its
writer (:func:`write_user_llm_config`) so both produce the same file shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ..._app import GLOBAL_CONFIG_FILE
from .._constants import (
    DEFAULT_CLAUDE_MODEL,
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
    provider = _select_choice(
        "API type",
        options=[
            ("auto", "let Arbor detect it — probes Responses API, else chat completions"),
            ("openai-responses", "OpenAI / o-series via the Responses API (reasoning chain)"),
            ("openai-chat", "any OpenAI-compatible endpoint (DeepSeek / Qwen / GLM / …)"),
            ("openai-oauth", "ChatGPT Plus/Pro subscription via browser login (experimental)"),
            ("anthropic", "Claude via the native Anthropic API"),
        ],
        default="auto",
    )

    if provider == "openai-oauth":
        return _setup_openai_oauth()

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

    # 5. reasoning effort (reasoning models / Claude thinking budget)
    llm["reasoning_effort"] = _prompt_reasoning_effort()

    _console.print()
    write_user_llm_config(llm)

    _probe_credentials(provider, api_key or None)
    _console.print(
        f"\n[green]Done.[/] Saved to [bold]{GLOBAL_CONFIG_FILE}[/] "
        "([dim]view it anytime with[/] [bold]arbor config show[/])."
    )
    _console.print("Just run [bold]arbor[/] to start a session.\n")
    return True


def _setup_openai_oauth() -> bool:
    """Run the ChatGPT subscription login, then write the global config."""
    from ...core.oauth import openai as oauth
    from .._constants import DEFAULT_OPENAI_OAUTH_MODEL
    from ..style import console as _console

    _console.print()
    _console.print(
        "[yellow]Experimental:[/] using a ChatGPT subscription token with "
        "third-party tools may violate OpenAI's terms and risks your account."
    )
    try:
        tokens = oauth.login()
    except oauth.OAuthError as exc:
        _console.print(f"[red]login failed:[/] {exc}")
        return False

    plan = tokens.plan_type or "unknown"
    _console.print(f"[green]✓[/] signed in to ChatGPT — plan=[bold]{plan}[/]")

    model = typer.prompt("Model", default=DEFAULT_OPENAI_OAUTH_MODEL).strip() or DEFAULT_OPENAI_OAUTH_MODEL
    effort = _prompt_reasoning_effort(default="medium")
    _console.print()
    write_user_llm_config(
        {"provider": "openai-oauth", "model": model, "reasoning_effort": effort}
    )
    _console.print(
        f"\n[green]Done.[/] Saved to [bold]{GLOBAL_CONFIG_FILE}[/]. "
        "Just run [bold]arbor[/] to start a session.\n"
    )
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


def _prompt_reasoning_effort(default: str = "high") -> str:
    """Pick the reasoning effort (speed vs. depth) for the run loop."""
    return _select_choice(
        "Reasoning effort",
        options=[
            ("high", "most thorough planning — slowest (best quality)"),
            ("medium", "balanced depth and speed"),
            ("low", "light reasoning — fast, may weaken complex planning"),
            ("none", "no reasoning — fastest, lowest quality"),
        ],
        default=default,
    )


def _select_choice(
    label: str, *, options: list[tuple[str, str]], default: str
) -> str:
    """Pick one value with arrow keys (↑/↓ or k/j, Enter to confirm).

    ``options`` is a list of ``(value, description)`` pairs. Falls back to a
    typed prompt when stdin/stdout is not an interactive terminal (CI, pipes,
    test runners) or when prompt_toolkit cannot start.
    """
    values = [value for value, _ in options]
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _prompt_choice(label, choices=values, default=default)

    try:
        return _arrow_select(label, options=options, default=default)
    except Exception:
        # Terminal can't host a full prompt_toolkit app — degrade gracefully.
        return _prompt_choice(label, choices=values, default=default)


def _arrow_select(
    label: str, *, options: list[tuple[str, str]], default: str
) -> str:
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    values = [value for value, _ in options]
    width = max(len(value) for value in values)
    index = values.index(default) if default in values else 0
    state = {"index": index}

    def render() -> list[tuple[str, str]]:
        lines: list[tuple[str, str]] = []
        for i, (value, desc) in enumerate(options):
            selected = i == state["index"]
            pointer = "❯ " if selected else "  "
            style = "class:option.selected" if selected else "class:option"
            meta = "class:meta.selected" if selected else "class:meta"
            lines.append((style, f"{pointer}{value:<{width}}"))
            lines.append((meta, f"   {desc}\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _(event):  # noqa: ANN001
        state["index"] = (state["index"] - 1) % len(options)

    @kb.add("down")
    @kb.add("j")
    def _(event):  # noqa: ANN001
        state["index"] = (state["index"] + 1) % len(options)

    @kb.add("enter")
    def _(event):  # noqa: ANN001
        event.app.exit(result=values[state["index"]])

    @kb.add("c-c")
    @kb.add("escape")
    def _(event):  # noqa: ANN001
        event.app.exit(exception=KeyboardInterrupt)

    header = FormattedTextControl(
        lambda: [("class:label", f"{label}  "), ("class:hint", "(↑/↓ to move, Enter to select)")]
    )
    body = FormattedTextControl(render, focusable=True)
    layout = Layout(HSplit([
        Window(header, height=1),
        Window(body, height=len(options) * 2),
    ]))
    style = Style.from_dict({
        "label": "bold #00afaf",
        "hint": "#808080",
        "option": "#d0d0d0",
        "option.selected": "#d75fff bold",
        "meta": "#808080",
        "meta.selected": "#af87ff",
    })
    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
    try:
        result = app.run()
    except KeyboardInterrupt:
        raise typer.Abort() from None

    chosen = next(desc for value, desc in options if value == result)
    typer.echo(f"{label}: {result}  ({chosen})")
    return result


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
