# Installation

## Requirements

- **Python ≥ 3.10**
- **Git** (Arbor runs each experiment in an isolated git worktree)
- An API key for at least one LLM provider (Anthropic, OpenAI, or any
  OpenAI-compatible endpoint via LiteLLM)

## Install

```bash
git clone https://github.com/RUC-NLPIR/Arbor.git
cd Arbor
pip install -e .          # or: uv pip install -e .
```

That single command installs Arbor and the `arbor` command into your current Python
environment. We recommend a virtual environment so it stays isolated:

=== "venv + pip"

    ```bash
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -e .
    ```

=== "uv"

    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install -e .
    ```

!!! info "Why editable (`-e`)?"
    Arbor is research software under active development. An editable install lets you
    pull updates with `git pull` without reinstalling.

## Verify

```bash
arbor version
arbor doctor      # checks PATH, venv leakage, git, and API keys
```

`arbor doctor` is the fastest way to catch a broken setup — it reports which `arbor` your
shell resolves, which Python it runs on, whether `git` is available, and whether your
user config exists.

## Optional: a global `arbor` command with pipx

If you'd rather have `arbor` available in **every** directory without activating a venv,
install it with [pipx](https://pipx.pypa.io) — it manages the isolated environment for
you:

```bash
pipx install -e .                 # run from the cloned Arbor directory
pipx reinstall arbor     # upgrade later
```

## Troubleshooting

!!! failure "`arbor: command not found`"
    The package was installed into an environment that isn't active or on your `PATH`.
    Activate the right virtual environment, or use the pipx install above. Run
    `arbor doctor` for a diagnosis.

## Next steps

- [Quickstart](quickstart.md) — configure a provider and start your first run.
- [Configuration](configuration.md) — every option, with examples.
