# Configuration

TriadLLM uses two main user-managed files:

- `settings.json`
- `profiles.yaml`

The repository also includes examples:

- [`src/triadllm/examples/settings.json`](../src/triadllm/examples/settings.json)
- [`src/triadllm/examples/profiles.yaml`](../src/triadllm/examples/profiles.yaml)

## Config Locations

Typical paths:

- Linux: `~/.config/TriadLLM`
- macOS: `~/Library/Application Support/TriadLLM`
- Windows: `%APPDATA%\\TriadLLM`

## `settings.json`

This file controls app behavior and role assignments.

Example:

```json
{
  "language": "en",
  "permission_mode": "ask",
  "show_reasoning": true,
  "show_tool_results": true,
  "default_profile": "orchestrator_mistral_medium_latest",
  "agent_profiles": {
    "orchestrator": "orchestrator_mistral_medium_latest",
    "processor": "processor_magistral_medium_latest",
    "validator": "validator_gpt54_medium"
  },
  "log_level": "INFO",
  "log_retention_days": 7
}
```

Fields:

- `language`: `en` or `es`
- `permission_mode`: `ask` or `yolo`
- `show_reasoning`: whether reasoning blocks are visible in the transcript
- `show_tool_results`: whether tool request/result blocks are visible in the transcript
- `default_profile`: fallback profile id if a role-specific assignment is missing
- `agent_profiles`: per-role profile assignments
- `log_level`: `DEBUG`, `INFO`, `WARNING`, or `ERROR`
- `log_retention_days`: rotating log retention window

## `profiles.yaml`

This file defines available model/provider profiles.

Minimal shape:

```yaml
default_profile: openai_default

profiles:
  openai_default:
    label: OpenAI Default
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-4.1-mini
    api_key_env: OPENAI_API_KEY
    temperature: 0.2
```

Available profile fields:

- `label`: human-readable name shown in config and status output
- `provider`: `openai`, `mistral`, or `openai_compatible`
- `base_url`: endpoint root
- `model`: model id or alias
- `api_key_env`: environment variable name to read the key from
- `api_key_literal`: direct value for local endpoints such as `dummy`
- `temperature`: sampling temperature
- `timeout`: request timeout in seconds
- `max_tokens`: general provider request token limit
- `context_window`: reference metadata for the model context length
- `max_output_tokens_limit`: reference metadata for known output caps
- `reasoning_effort`: provider-specific reasoning effort, currently used for OpenAI reasoning-capable models
- `reasoning_summary`: provider-specific reasoning summary mode
- `default_headers`: optional extra headers

## Role Assignment Strategy

TriadLLM has three fixed roles:

- `orchestrator`
- `processor`
- `validator`

The runtime supports any supported provider family in any role.

If `agent_profiles` is empty, the runtime falls back to `default_profile` for all three roles.

Recommended mental model:

- `processor`: best generation model
- `validator`: best verification model
- `orchestrator`: stable synthesis and presentation model

## Environment Variables

Common examples:

- `OPENAI_API_KEY`
- `MISTRAL_API_KEY`

The value is not stored by TriadLLM. The shell environment must provide it before launch.

## Runtime Controls

These slash commands update runtime settings during a session:

- `/permissions ask|yolo`
- `/lang es|en`
- `/model set <role> <profile>`
- `/reasoning on|off`
- `/toolresults on|off`
- `/cancel`

Changes are persisted back to `settings.json`.

Keyboard controls for the composer:

- `Enter` sends the current draft
- `Ctrl+J` inserts a newline in the bottom composer
- `Ctrl+E` opens the expanded composer modal
- in the expanded composer, `Ctrl+S` sends and `Esc` cancels
- while a turn is busy, new non-command prompts are queued and processed in order
- the `Cancel` button and `/cancel` stop the active turn; queued turns continue afterward

## Migration From `MultiBrainLLM`

On first launch, `TriadLLM` automatically copies legacy files forward if the new files do not exist yet:

- `settings.json`
- `profiles.yaml`
- `sessions/`
- `multibrain.log` -> `triadllm.log`

That means an existing local setup should keep working after the rename.
