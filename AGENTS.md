# AGENTS.md

## Purpose

This file is a working guide for coding agents that modify, maintain, test, or document `MultiBrainLLM`.

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


## Non-Negotiable Project Rules

- Use `uv` for everything Python-related.
- Target Python `>=3.13,<3.14`.
- Preserve the three-agent flow unless the user explicitly asks for architectural change.
- Keep provider integration provider-agnostic at the runtime boundary.
- Do not couple the system to a single vendor’s native tool-calling format.
- Keep the tool execution path centralized in the broker.
- Do not bypass permission handling in runtime code.
- Keep `es` and `en` as first-class locales.
- Keep logging detailed enough to debug runs from log files alone.
- If code behavior changes, update documentation in the same change.


## Core Architecture

Main modules:

- `src/multibrainllm/app.py`
  TUI, slash commands, transcript rendering, permission modal, reasoning visibility.

- `src/multibrainllm/runtime.py`
  Turn orchestration, clarification resume flow, proposal-validation loop, event emission, session persistence.

- `src/multibrainllm/providers.py`
  Provider abstraction, official OpenAI/Mistral SDK usage, OpenAI-compatible local backends, repair/fallback logic.

- `src/multibrainllm/tools.py`
  Tool broker, permission gating, cross-platform local tool implementations.

- `src/multibrainllm/prompts.py`
  Agent prompts, tool usage guidance, behavioral constraints.

- `src/multibrainllm/domain.py`
  Typed contracts, schemas, enums, shared models.

- `src/multibrainllm/config.py`
  Settings and profiles loading, platform-specific paths.

- `src/multibrainllm/logging_utils.py`
  Structured JSON logging, redaction, rotation.


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

Behavioral intent:

- the `processor` proposes the primary answer
- the `validator` checks that answer against the user request and gathered evidence
- the `orchestrator` consolidates both into the user-facing reply

Do not drift this into "two parallel independent opinions" unless the user explicitly requests that architecture.


## Provider Integration Rules

Current provider backends:

- `openai`
- `mistral`
- `openai_compatible`

Guidelines:

- Prefer official SDKs for vendor-native endpoints.
- Use the OpenAI SDK for local OpenAI-compatible servers.
- Keep fallback behavior local to `providers.py`.
- If a provider returns reasoning but no valid JSON, prefer repair or deterministic fallback over crashing the turn.
- Log parse failures, retries, and fallback paths.
- Never assume a model alias exists just because it appears in docs; real account availability varies.

When adding a provider:

1. add or extend the backend enum in `domain.py`
2. add provider construction and invoke logic in `providers.py`
3. preserve the common runtime interface
4. add tests for parsing and failure handling
5. update `README.md`
6. update `src/multibrainllm/examples/profiles.yaml`


## Prompt Engineering Rules

Prompts are operational code. Treat them as such.

Requirements:

- be explicit about allowed actions
- enforce schema compliance
- reinforce the intended workflow: proposal, validation, consolidation
- tell the model which tools exist
- document expected arguments for each tool
- explain when to prefer one tool over another
- forbid invented tool names
- forbid repeating the same invalid tool request
- instruct the model to use prior `tool_results` before requesting more tools

When changing prompts:

- update tests in `tests/test_prompts.py`
- run a real provider test for at least one tool-using scenario if behavior changed materially
- keep prompts concise enough to avoid unnecessary token waste, but explicit enough to reduce loops


## Tooling Rules

Current tools:

- `shell_exec`
- `read_file`
- `write_file`
- `list_dir`
- `search_files`
- `get_env`
- `pwd`

Important constraints:

- only the broker executes tools
- permission mode must be respected
- `get_env` remains allowlisted
- tool names and argument contracts should be stable
- tool requests should be serializable and loggable

When adding or changing a tool:

1. implement it in `tools.py`
2. update `available_tools()`
3. update prompt guidance in `prompts.py`
4. update docs in `README.md`
5. add tests for success and failure modes
6. consider risk classification and permission implications

Do not add a tool silently. If the model must know it exists, the prompt and docs must change too.


## Runtime Rules

The runtime is the system’s behavioral backbone.

Do not break these properties:

- every agent receives the full visible conversation context for each iteration
- clarifications pause and resume cleanly
- tool requests are iterative, not terminal
- the validator always receives both the original user task and the processor answer
- the orchestrator always produces the final user-facing consolidated response
- the transcript and session log remain analyzable after the run

When modifying `runtime.py`, pay attention to:

- turn lifecycle
- `pending` clarification state
- session file rotation
- event emission consistency
- maximum internal step limits
- logging signal quality


## Logging Rules

The logs must be good enough for a separate terminal session to diagnose:

- what the user asked
- which role ran
- which provider/model answered
- what kind of action the model chose
- what tool was requested
- what the tool returned
- whether repair/fallback logic was used
- how the turn finished

Logging requirements:

- keep JSON logs structured
- redact secrets
- include previews for large fields instead of dumping unlimited text
- do not remove existing high-signal events unless replaced with better ones
- prefer adding structured fields over burying detail in free text

If behavior changes and logs become less useful, treat that as a regression.


## TUI Rules

The TUI should remain:

- minimal
- professional
- retro-terminal styled
- readable on real terminals

Keep:

- transcript scrolling
- fixed composer
- status bar
- permission modal
- reasoning visibility toggle
- slash commands

Do not introduce visual noise or break the current operational feel just to add features.


## i18n Rules

Supported first-class locales:

- `es`
- `en`

Rules:

- all system UI strings must come from locale catalogs
- do not hardcode user-facing operational text in Python if it belongs in locales
- model output itself is not translated by the app layer
- if you add a new slash command or runtime message, update both locale files


## Testing Rules

At minimum, after meaningful code changes run:

```bash
uv run pytest -q
uv run python -m compileall src tests
```

For broader release-grade verification, also use:

```bash
uv build
```

Add tests when changing:

- prompts
- provider parsing or fallback behavior
- runtime turn logic
- app slash commands
- config loading
- i18n behavior

Prefer small deterministic tests first. Use real-provider smoke checks only when needed to validate integration behavior.


## Documentation Rules

Documentation is part of the product. Keep it aligned.

Whenever you change:

- provider support
- slash commands
- tool availability
- configuration shape
- runtime behavior
- installation steps

you must review and update:

- `README.md`
- `src/multibrainllm/examples/profiles.yaml`
- any user-facing wording affected by the change

Do not leave the README behind the implementation.


## Safe Change Strategy

When making non-trivial changes:

1. inspect the relevant modules first
2. identify invariants you must preserve
3. update schemas/contracts before wiring behavior
4. update prompts if model behavior depends on new capabilities
5. add or update tests
6. run verification commands
7. update docs
8. check logs if the change affects runtime decisions


## Anti-Patterns To Avoid

- hardcoding provider-specific logic into runtime orchestration
- bypassing the tool broker
- adding undocumented slash commands
- inventing new tool names without broker support
- silently changing configuration schema
- weakening logs to reduce output volume
- relying only on mocked tests for provider behavior
- using free-form text parsing where structured schemas already exist
- adding UI text without locale updates
- changing prompts without considering tool loops or clarification behavior


## Recommended Commands

Environment and test:

```bash
uv sync --dev
uv run pytest -q
uv run python -m compileall src tests
uv build
```

Run the app:

```bash
uv run multibrain
```

Follow logs:

```bash
tail -f ~/.local/state/MultiBrainLLM/log/multibrain.log
```


## Final Standard

A good change in this repository has these properties:

- it preserves the multi-agent contract
- it improves or maintains observability
- it does not reduce cross-provider compatibility
- it keeps tools controlled and explicit
- it ships with tests
- it leaves documentation aligned with reality
