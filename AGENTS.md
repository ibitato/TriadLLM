# AGENTS.md

## Purpose

This file is a working guide for coding agents that modify, maintain, test, or document `TriadLLM`.

The project is a Python `3.13` terminal application with a `Textual` TUI and a three-agent runtime built around a proposal-validation-consolidation workflow:

- `processor`: primary answer generation / execution planning
- `validator`: validation, correction, and evidence gathering against the original user request and processor output
- `orchestrator`: final user-facing consolidation

The codebase is designed around:

- `uv` for environment and dependency management
- official SDKs for provider integrations where possible
- a provider-agnostic structured JSON protocol for agent outputs
- a central tool broker with permission control
- persistent structured logging for post-run diagnosis


## Quality Gates

All quality gates must pass before any commit. Use `make check` to verify.

### Commands

```bash
make check      # Run all gates: format + lint + typecheck + tests
make fix        # Auto-fix format and lint issues
make format     # Check formatting only (ruff format --check)
make lint       # Check lint only (ruff check)
make typecheck  # Check types only (mypy)
make test       # Run tests only (pytest)
make clean      # Remove __pycache__ and tool caches
```

### Gate Details

| Gate | Tool | Config | What it checks |
|------|------|--------|----------------|
| Format | `ruff format` | `pyproject.toml [tool.ruff]` | Consistent code formatting |
| Lint | `ruff check` | `pyproject.toml [tool.ruff.lint]` | Import order, unused imports, code patterns |
| Types | `mypy` | `pyproject.toml [tool.mypy]` | Type correctness (strict on new modules) |
| Tests | `pytest` | `pyproject.toml [tool.pytest]` | All tests pass |

### Pre-commit Hooks

Pre-commit hooks are configured in `.pre-commit-config.yaml`. Install with:

```bash
uv run pre-commit install
```

Hooks run ruff format, ruff check, and mypy on every commit.

### Rules for New Code

- New modules must pass mypy without `ignore_errors` overrides.
- All new functions must have type annotations.
- All new features must have tests.
- Run `make check` before submitting any change.


## Non-Negotiable Project Rules

- Use `uv` for everything Python-related.
- Target Python `>=3.13,<3.14`.
- Preserve the three-agent flow unless the user explicitly asks for architectural change.
- Keep provider integration provider-agnostic at the runtime boundary.
- Do not couple the system to a single vendor's native tool-calling format.
- Keep the tool execution path centralized in the broker.
- Do not bypass permission handling in runtime code.
- Keep `es` and `en` as first-class locales.
- Keep logging detailed enough to debug runs from log files alone.
- If code behavior changes, update documentation in the same change.
- All quality gates must pass before any commit.


## Module Structure

```
src/triadllm/
├── __init__.py          # Package root
├── __main__.py          # python -m triadllm entry
├── cli.py               # build_runtime() and main() entry point
├── config.py            # Settings/profiles loading, platform paths
├── domain.py            # Typed contracts, schemas, enums, models
├── firecrawl.py         # Firecrawl REST API v2 client (async httpx)
├── i18n.py              # Translator, locale loading
├── logging_utils.py     # Structured JSON logging, redaction
├── prompts.py           # Agent prompts, tool guidance
├── providers.py         # Provider abstraction (OpenAI/Mistral/Compatible)
├── runtime.py           # Turn orchestration, event emission
├── app.py               # Re-export shim (backward compat → ui/)
├── tools/               # Tool broker package
│   ├── __init__.py      # Re-exports ToolBroker, ApprovalHandler
│   ├── broker.py        # ToolBroker: execute, normalize, local tools
│   ├── firecrawl_handlers.py  # Firecrawl tool handlers (mixin)
│   └── sanitizers.py    # Markdown→text, truncation, result sanitization
└── ui/                  # TUI package
    ├── __init__.py      # Re-exports TriadApp, screens, widgets
    ├── app.py           # TriadApp: main app, slash commands, rendering
    ├── screens.py       # SplashScreen, PermissionScreen, EditorScreen, ConfigEditorScreen
    └── widgets.py       # ComposerArea
```

### Import Conventions

- External code imports from top-level: `from triadllm.tools import ToolBroker`
- The `app.py` at package root is a backward-compat shim; real code lives in `ui/app.py`
- Tests import from the public API (`triadllm.tools`, `triadllm.app`, etc.)


## Core Architecture

### Entry Point

`triadllm:main` → `cli.py:main()` → builds runtime → launches `TriadApp`

### Runtime (`runtime.py`)

Turn orchestration, clarification resume flow, proposal-validation loop, event emission, session persistence.

### Providers (`providers.py`)

Provider abstraction, official OpenAI/Mistral SDK usage, OpenAI-compatible local backends, repair/fallback logic.

### Tools (`tools/`)

- `broker.py`: Central tool broker, permission gating, local tool implementations (shell_exec, read_file, write_file, list_dir, search_files, get_env, pwd).
- `firecrawl_handlers.py`: Firecrawl API v2 tool handlers (scrape, search, map, crawl) as a mixin class.
- `sanitizers.py`: Markdown-to-text conversion, token-based truncation, result sanitization for Firecrawl outputs.

### UI (`ui/`)

- `app.py`: TriadApp main class, slash command handling, transcript rendering.
- `screens.py`: Modal screens (splash, permission, editor, config editor).
- `widgets.py`: ComposerArea with Enter-to-send, Ctrl+J newline, Ctrl+E expand.

### Firecrawl Client (`firecrawl.py`)

Async HTTP client for Firecrawl API v2. Features:
- Direct REST calls (no external binary needed)
- Retry with exponential backoff on 429 (rate limit)
- Endpoints: `/v2/scrape`, `/v2/search`, `/v2/map`, `/v2/crawl`

### Domain (`domain.py`)

Typed contracts: AgentResponse, ConsolidatedResponse, ToolRequest, ToolResult, UserSettings, FirecrawlDefaults, etc.

### Prompts (`prompts.py`)

Agent prompts, tool usage guidance, behavioral constraints.


## How Agents Communicate With Models

The system uses a shared structured output contract instead of provider-specific tool calling.

Important consequence:

- models do not execute tools directly
- models return structured JSON
- runtime interprets the JSON
- broker executes tools
- results are fed back into the same agent

For `AgentResponse`, an agent may only:

- return `final`
- return `ask_user`
- return `request_tool`

Do not replace this with ad hoc string parsing or free-form tool intents.


## Provider Integration Rules

Current provider backends: `openai`, `mistral`, `openai_compatible`

When adding a provider:

1. add or extend the backend enum in `domain.py`
2. add provider construction and invoke logic in `providers.py`
3. preserve the common runtime interface
4. add tests for parsing and failure handling
5. update `README.md`
6. update `src/triadllm/examples/profiles.yaml`


## Tooling Rules

Current tools:

- `shell_exec`, `read_file`, `write_file`, `list_dir`, `search_files`, `get_env`, `pwd`
- `firecrawl_scrape`, `firecrawl_search`, `firecrawl_map`, `firecrawl_crawl`

When adding or changing a tool:

1. implement it in `tools/broker.py` (local) or `tools/firecrawl_handlers.py` (firecrawl)
2. update `available_tools()` in `tools/broker.py`
3. update prompt guidance in `prompts.py`
4. update docs in `README.md`
5. add tests for success and failure modes
6. consider risk classification and permission implications


## Runtime Rules

Do not break these properties:

- every agent receives the full visible conversation context for each iteration
- clarifications pause and resume cleanly
- tool requests are iterative, not terminal
- the validator always receives both the original user task and the processor answer
- the orchestrator always produces the final user-facing consolidated response
- the transcript and session log remain analyzable after the run


## Testing Rules

At minimum, after meaningful code changes run:

```bash
make check
```

For broader release-grade verification:

```bash
uv build
uv run python -m compileall src tests
```

Test requirements:

- All new features must have tests.
- Tests live in `tests/` with naming convention `test_<module>.py`.
- Prefer small deterministic tests. Use real-provider smoke checks only when needed.
- Target >80% coverage on core modules (tools, firecrawl, runtime).


## Logging Rules

Logs must be good enough for a separate terminal session to diagnose:

- what the user asked
- which role ran, which provider/model answered
- what tool was requested and returned
- whether repair/fallback logic was used
- how the turn finished

Keep JSON logs structured. Redact secrets. Include previews for large fields.


## TUI Rules

The TUI should remain minimal, professional, retro-terminal styled, readable on real terminals.

Keep: transcript scrolling, fixed composer, status bar, permission modal, reasoning visibility toggle, slash commands.


## i18n Rules

Supported locales: `es`, `en`. All system UI strings must come from locale catalogs.


## Documentation Rules

Whenever you change provider support, slash commands, tool availability, configuration shape, runtime behavior, or installation steps — update `README.md` and relevant docs.


## Recommended Commands

```bash
# Development
uv sync --dev
make check          # All quality gates
make fix            # Auto-fix format + lint
uv run pytest -q    # Tests only
uv build            # Build distribution

# Run the app
uv run triad

# Follow logs
tail -f ~/.local/state/TriadLLM/log/triadllm.log
```


## Anti-Patterns To Avoid

- Committing without running `make check`
- Hardcoding provider-specific logic into runtime orchestration
- Bypassing the tool broker
- Adding undocumented slash commands or tools
- Silently changing configuration schema
- Weakening logs to reduce output volume
- Adding UI text without locale updates
- Changing prompts without considering tool loops or clarification behavior
- Adding new modules without mypy type annotations
