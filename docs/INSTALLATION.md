# Installation

This guide is for someone starting from a fresh clone of the `TriadLLM` repository.

## Requirements

- `uv`
- Python `3.13`
- at least one reachable provider endpoint
- API credentials exported in the shell for any remote provider you want to use

## Install `uv`

Follow the official instructions:

https://docs.astral.sh/uv/getting-started/installation/

## Clone the repository

```bash
git clone https://github.com/ibitato/TriadLLM.git
cd TriadLLM
```

## Install Python and dependencies

```bash
uv python install 3.13
uv sync
```

For development:

```bash
uv sync --dev
```

## Create the local config directories

Launch the app once:

```bash
uv run triad
```

That creates the runtime directories if they do not exist yet.

Default paths:

- Linux config: `~/.config/TriadLLM`
- Linux state/logs: `~/.local/state/TriadLLM`
- macOS config: `~/Library/Application Support/TriadLLM`
- Windows config: `%APPDATA%\\TriadLLM`

## Add provider profiles

Copy the repository example file into your user config directory:

```bash
mkdir -p ~/.config/TriadLLM
cp src/triadllm/examples/profiles.yaml ~/.config/TriadLLM/profiles.yaml
```

Then edit `profiles.yaml` so the profiles match the models you actually want to use.

## Export API keys

Examples:

```bash
export OPENAI_API_KEY=...
export MISTRAL_API_KEY=...
```

TriadLLM reads keys from the environment. It does not auto-load `.env`.

## Start the app

```bash
./run_triadllm.sh
```

This script automatically checks prerequisites, sets up the environment if needed, and launches the application.

Alternative entrypoints:

```bash
uv run triad
```

```bash
uv run triadllm
```

## Verify the setup

Inside the app:

- run `/status`
- run `/models`
- run `/tools`

If you want a clean English UI on a migrated install, run:

```text
/lang en
```

## Local OpenAI-Compatible Endpoints

TriadLLM also supports local servers that expose an OpenAI-compatible API.

Example profile:

```yaml
local_glm47_flash:
  label: Local GLM-4.7 Flash
  provider: openai_compatible
  base_url: http://127.0.0.1:8080/v1
  model: zai-org/GLM-4.7-Flash
  api_key_literal: dummy
  temperature: 0.7
  timeout: 60
```

The local compatibility layer uses the official OpenAI SDK pointed at your local endpoint.
