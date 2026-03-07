# TriadLLM

`TriadLLM` is a terminal chat application for multi-stage LLM work. Each user turn follows a fixed workflow:

1. `processor` generates the primary answer
2. `validator` checks that answer against the original request and gathered evidence
3. `orchestrator` consolidates both into the final user-facing reply

The project uses:

- `Textual` for the TUI
- official OpenAI and Mistral SDKs where possible
- an OpenAI-compatible backend for local servers such as `GLM-4.7-Flash`
- a shared structured JSON protocol for agent actions
- a central tool broker with `ask` and `yolo` permission modes

The repository language is English, and fresh installs default to English in the app. Spanish is also supported at runtime with `/lang es`.

## What TriadLLM Is

TriadLLM is not a “two independent opinions” system. The intended workflow is:

- generate a primary answer
- validate it against the original request
- consolidate the answer and validation into a final response

That makes the second model a grounded review layer rather than a second parallel solver.

## Features

- scrollable transcript with fixed bottom composer
- three-stage proposal, validation, and consolidation flow
- full visible conversation history passed back to agents on each turn
- clarification loop when the processor or validator needs more data
- local tools with permission prompts
- toggleable reasoning display with `/reasoning on|off`
- toggleable tool-request/result display with `/toolresults on|off`
- slash commands for runtime control
- JSONL session persistence
- structured rotating logs
- English and Spanish locales
- Python `3.13` environment managed with `uv`

## Quick Start

### 1. Install `uv`

See the official installer:

https://docs.astral.sh/uv/getting-started/installation/

### 2. Clone and bootstrap

```bash
git clone https://github.com/ibitato/TriadLLM.git
cd TriadLLM
uv python install 3.13
uv sync
```

### 3. Prepare provider configuration

Run the app once to create the config directories:

```bash
uv run triad
```

Then copy the example profile file into your user config directory:

- Linux: `~/.config/TriadLLM/profiles.yaml`
- macOS: `~/Library/Application Support/TriadLLM/profiles.yaml`
- Windows: `%APPDATA%\\TriadLLM\\profiles.yaml`

Example on Linux:

```bash
mkdir -p ~/.config/TriadLLM
cp src/triadllm/examples/profiles.yaml ~/.config/TriadLLM/profiles.yaml
```

If you want to inspect the active paths later, use `/config` inside the app.

### 4. Export API keys

Examples:

```bash
export OPENAI_API_KEY=...
export MISTRAL_API_KEY=...
```

The app reads provider credentials from the environment. It does not load a `.env` file by itself.

### 5. Start the app

```bash
uv run triad
```

Alternative entrypoint:

```bash
uv run triadllm
```

## First-Run Checklist

After cloning the repo, a new user should verify:

- Python `3.13` is installed with `uv`
- `uv sync` completed successfully
- `profiles.yaml` exists in the user config directory
- the required API keys are exported in the shell
- `uv run triad` starts the TUI
- `/models` shows the configured profiles
- `/status` shows the expected language, permissions, and log path

## Configuration and Runtime Files

TriadLLM stores runtime state outside the repo:

- `settings.json`: language, permission mode, log settings, UI toggles, role assignments
- `profiles.yaml`: provider/model definitions
- `sessions/*.jsonl`: persisted session events
- `triadllm.log`: structured runtime log

On first launch, TriadLLM automatically reuses legacy local config from `MultiBrainLLM` if it finds existing settings, profiles, sessions, or logs.

Repository examples:

- sample profiles: [`src/triadllm/examples/profiles.yaml`](/home/dlopez/code/collabAgent/src/triadllm/examples/profiles.yaml)
- sample settings: [`src/triadllm/examples/settings.json`](/home/dlopez/code/collabAgent/src/triadllm/examples/settings.json)

## Tools and Permissions

Available local tools:

- `shell_exec`
- `read_file`
- `write_file`
- `list_dir`
- `search_files`
- `get_env`
- `pwd`

Execution modes:

- `ask`: every tool request requires approval
- `yolo`: tool requests run immediately

Use `/permissions ask` or `/permissions yolo` to switch modes at runtime.

## Slash Commands

- `/help`
- `/status`
- `/config`
- `/permissions ask|yolo`
- `/lang es|en`
- `/models`
- `/model set <orchestrator|processor|validator> <profile>`
- `/tools`
- `/reasoning on|off`
- `/toolresults on|off`
- `/new`
- `/clear`
- `/quit`

## Documentation

- installation guide: [`docs/INSTALLATION.md`](/home/dlopez/code/collabAgent/docs/INSTALLATION.md)
- configuration reference: [`docs/CONFIGURATION.md`](/home/dlopez/code/collabAgent/docs/CONFIGURATION.md)
- architecture guide: [`docs/ARCHITECTURE.md`](/home/dlopez/code/collabAgent/docs/ARCHITECTURE.md)
- FAQ: [`docs/FAQ.md`](/home/dlopez/code/collabAgent/docs/FAQ.md)
- coding-agent maintenance guide: [`AGENTS.md`](/home/dlopez/code/collabAgent/AGENTS.md)

## Development

```bash
uv sync --dev
uv run pytest -q
uv run python -m compileall src tests
uv build
```

## License

This project is source-available under `PolyForm Noncommercial 1.0.0`. Commercial use is not allowed without separate permission.
