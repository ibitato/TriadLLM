# Architecture

TriadLLM is built around a fixed three-stage workflow.

## Core Flow

For each user turn:

1. the `processor` receives the user message and the full visible conversation history
2. the `validator` receives the same user message, the visible conversation history, and the processor output
3. the `orchestrator` receives the processor output and validator review and returns the final consolidated response

This is intentionally not a “two independent parallel answers” design.

The intended behavior is:

- proposal
- validation
- synthesis

## Clarifications

Either the `processor` or the `validator` can ask the user for more information.

When that happens:

1. the runtime stores a pending clarification state
2. the question is shown in the transcript
3. the next user message is treated as the clarification answer
4. the runtime resumes the exact pending stage

## Tools

The models do not execute tools directly.

Instead:

1. a model returns a structured `request_tool` response
2. the runtime routes it to the central broker
3. the broker applies permission rules
4. the tool result is fed back to the same agent as structured evidence

Current tools:

- `shell_exec`
- `read_file`
- `write_file`
- `list_dir`
- `search_files`
- `get_env`
- `pwd`

## Providers

Supported provider backends:

- `openai`
- `mistral`
- `openai_compatible`

Design goals:

- use official SDKs for vendor-native endpoints
- keep the runtime interface provider-agnostic
- fall back gracefully when a provider emits reasoning but fails to emit valid structured JSON

## Main Modules

- `src/triadllm/app.py`: Textual app, transcript, slash commands, permission modal
- `src/triadllm/runtime.py`: turn lifecycle, clarifications, role orchestration
- `src/triadllm/providers.py`: provider implementations and parsing logic
- `src/triadllm/tools.py`: tool broker and local tool execution
- `src/triadllm/prompts.py`: system prompts and tool guidance
- `src/triadllm/domain.py`: typed schemas and shared contracts
- `src/triadllm/config.py`: config paths, loading, and migration from legacy names
- `src/triadllm/logging_utils.py`: structured rotating logs

## Conversation Context

Each turn reuses the full visible conversation history, not just the last user message.

Visible history currently includes:

- user messages
- clarification questions
- final consolidated responses

Reasoning blocks and tool-result blocks are rendered for observability, but they are not treated as the visible user-facing conversation history for future turns.

## Final Output Model

The orchestrator always produces three sections:

- primary answer
- validation
- final synthesis

That output shape is the user-facing contract of the app.
