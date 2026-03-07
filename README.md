# MultiBrainLLM

`MultiBrainLLM` is a terminal chat application that runs each user turn through a three-stage LLM workflow:

- `processor`: produces the primary answer
- `validator`: validates that answer against the original user request and any gathered evidence
- `orchestrator`: presents the final consolidated response to the user

The interface is built with `Textual`, uses the official OpenAI and Mistral SDKs where available, and supports OpenAI-compatible local providers such as `GLM-4.7-Flash` on `localhost`.

This is not a system of two independent parallel opinions. The intended behavior is:

- generate an answer
- validate it against the original request
- consolidate the proposal and validation into one final reply

## Architecture

Each user turn runs through this pipeline:

1. `processor` receives the user message plus the full visible conversation history and proposes the primary answer.
2. `validator` receives the original user message, the same visible conversation, and the processor output. It verifies, challenges, corrects, or requests evidence.
3. `orchestrator` receives the processor proposal and the validator review, then presents the final consolidated answer shown in the TUI.

If `processor` or `validator` asks for more data, the runtime pauses, surfaces the clarification to the user, captures the answer, and resumes from the pending stage.

## Features

- Retro-styled TUI inspired by modern coding CLIs
- Scrollable transcript with fixed bottom composer
- Three-stage proposal, validation, and consolidation pipeline
- User clarification loop when processor or validator needs more data
- Full visible conversation history is passed back to every agent on each turn
- Local tools with `ask` and `yolo` permission modes
- Reasoning / thinking blocks rendered separately and toggleable with `/reasoning on|off`
- Slash commands for runtime control
- Structured logging with daily rotation
- Session persistence in JSONL
- Built-in i18n for Spanish and English, extensible to more locales
- Reproducible Python 3.13 environment via `uv`
- Official SDK integration for OpenAI and Mistral, plus OpenAI-compatible local backends
- Graceful fallback paths for providers that return reasoning but fail to emit valid structured JSON

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

The app persists:

- `settings.json`: language, permission mode, reasoning visibility, default profile and per-role assignments
- `profiles.yaml`: provider/model definitions
- `sessions/*.jsonl`: conversation event history
- `multibrain.log`: structured runtime log

## Provider Support

Supported provider backends:

- `openai`: official OpenAI SDK
- `mistral`: official Mistral SDK
- `openai_compatible`: OpenAI SDK pointed at a compatible endpoint, including local servers

Important notes:

- Provider availability depends on your account. A model alias present in docs may not be available in your tenant.
- The runtime supports assigning any supported provider family to any role.
- If a provider emits reasoning without a usable structured answer, the runtime applies repair or fallback logic instead of crashing the turn.
- Local OpenAI-compatible endpoints on `localhost` / `127.0.0.1` can use `api_key_literal: dummy`.

## Configuration

Example `profiles.yaml` structure:

```yaml
default_profile: openai_default

profiles:
  orchestrator_mistral_medium_latest:
    provider: mistral
    base_url: https://api.mistral.ai/v1
    model: mistral-medium-latest
    api_key_env: MISTRAL_API_KEY
    temperature: 0.7

  processor_gpt54_medium:
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-5.4
    api_key_env: OPENAI_API_KEY
    temperature: 1.0
    reasoning_effort: medium
    reasoning_summary: auto

  local_glm47_flash:
    provider: openai_compatible
    base_url: http://127.0.0.1:8080/v1
    model: zai-org/GLM-4.7-Flash
    api_key_literal: dummy
    temperature: 0.7
```

The repository example includes tested profile shapes for:

- OpenAI
- Mistral
- Magistral
- local OpenAI-compatible models

## Tools

Available local tools:

- `shell_exec`
- `read_file`
- `write_file`
- `list_dir`
- `search_files`
- `get_env`
- `pwd`

Execution rules:

- In `ask` mode, every tool request requires user approval.
- In `yolo` mode, tool requests run immediately.
- Environment access is allowlisted.
- Tool names are fixed; agents are instructed not to invent tool identifiers.

## Slash Commands

- `/help`
- `/status`
- `/config`
- `/permissions ask|yolo`
- `/lang es|en`
- `/models`
- `/model set <agent> <profile>`
- `/tools`
- `/reasoning on|off`
- `/toolresults on|off`
- `/new`
- `/clear`
- `/quit`

## Runtime Notes

- The visible transcript is the conversation context used for each new turn.
- The validator is a grounded review stage, not an independent second solver.
- The orchestrator is the final presentation layer: it does not replace validation, it packages the processor proposal and validator review for the user.
- `/new` starts a fresh conversation and rotates the session file.
- `/clear` clears the rendered transcript only; it does not reset the runtime state.
- Reasoning visibility affects display only; it does not change what is logged or sent to providers.
- Different model families may choose different valid actions for the same prompt: final answer, tool request, or clarification.

## Development

```bash
uv sync --dev
uv run pytest
```

Useful commands:

```bash
uv run pytest -q
uv run python -m compileall src tests
uv build
```

## License

This project is source-available under `PolyForm Noncommercial 1.0.0`. Commercial use is not allowed without separate permission.
