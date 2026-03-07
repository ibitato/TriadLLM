# Contributing to TriadLLM

Thanks for considering a contribution.

TriadLLM is a source-available project focused on:

- proposal, validation, and synthesis workflows for LLMs
- a terminal-first operator experience
- provider-agnostic runtime behavior
- safe local tool execution with explicit permission handling

Before you open a pull request, read:

- [`README.md`](./README.md)
- [`AGENTS.md`](./AGENTS.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- [`docs/CONFIGURATION.md`](./docs/CONFIGURATION.md)

## Ground Rules

- Use `uv` for Python setup, dependency management, and commands.
- Target Python `3.13`.
- Keep repository-facing documentation in English.
- Keep the current three-stage runtime behavior unless the change is explicitly architectural.
- Do not couple the runtime to provider-specific native tool-calling formats.
- Do not bypass the central tool broker or permission model.
- Update docs when behavior changes.
- Keep changes narrow and reviewable.

## Development Setup

```bash
uv python install 3.13
uv sync --dev
```

Useful commands:

```bash
uv run pytest -q
uv run python -m compileall src tests docs
uv build
```

## Before Opening a Pull Request

Please make sure:

- tests pass locally
- the project still builds
- docs match the new behavior
- new user-facing strings are added to both locale files if needed
- secrets are not committed

## Change Types That Are Especially Welcome

- bug fixes
- documentation improvements
- onboarding improvements
- provider robustness improvements
- tool broker safety and observability improvements
- test coverage for mixed-provider behavior

## Changes That Need Extra Care

- changing the agent workflow semantics
- changing prompt contracts
- changing tool schemas
- changing config file formats
- changing persistence or migration behavior
- introducing vendor lock-in at the runtime boundary

## Pull Request Guidance

A good PR should explain:

- what changed
- why it changed
- any behavior or compatibility implications
- how it was verified

Keep PRs focused. If a change spans runtime, prompts, tools, and docs, explain the full chain clearly.

## Issues Before PRs

For larger changes, open an issue first so the direction can be aligned before implementation.

## Licensing Note

By contributing, you agree that your contribution may be distributed under the repository license in [`LICENSE`](./LICENSE).
