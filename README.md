# MultiBrainLLM

`MultiBrainLLM` is a terminal chat application that routes each user turn through three LLM agents:

- `orchestrator`: user-facing agent, final synthesis, permission mediation
- `processor`: primary reasoning agent
- `validator`: review and contrast agent

The interface is built with `Textual`, the model layer uses `LangChain`, and provider profiles target OpenAI-compatible APIs.

## Features

- Retro-styled TUI inspired by modern coding CLIs
- Scrollable transcript with fixed bottom composer
- Three-agent pipeline with consolidated final response
- User clarification loop when processor or validator needs more data
- Local tools with `ask` and `yolo` permission modes
- Slash commands for runtime control
- Structured logging with daily rotation
- Built-in i18n for Spanish and English, extensible to more locales
- Reproducible Python 3.13 environment via `uv`

## Quick Start

```bash
uv python install 3.13
uv sync
uv run multibrain
```

By default the app looks for config under the platform-specific user config directory:

- Linux: `~/.config/MultiBrainLLM`
- macOS: `~/Library/Application Support/MultiBrainLLM`
- Windows: `%APPDATA%\MultiBrainLLM`

Copy the example provider config from [`src/multibrainllm/examples/profiles.yaml`](src/multibrainllm/examples/profiles.yaml) to your user config directory as `profiles.yaml`, then export the matching API key variable.

## Slash Commands

- `/help`
- `/status`
- `/config`
- `/permissions ask|yolo`
- `/lang es|en`
- `/models`
- `/model set <agent> <profile>`
- `/tools`
- `/clear`
- `/quit`

## Development

```bash
uv sync --dev
uv run pytest
```

## License

This project is source-available under `PolyForm Noncommercial 1.0.0`. Commercial use is not allowed without separate permission.
