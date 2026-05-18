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
  "log_retention_days": 7,
  "mcp_servers": [
    {
      "id": "firecrawl",
      "timeout": 120.0,
      "api_key_env": "FIRECRAWL_API_KEY"
    }
  ],
  "firecrawl_defaults": {
    "scrape_formats": ["markdown"],
    "search_limit": 5,
    "map_limit": 5,
    "crawl_max_pages": 5
  }
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
- `mcp_servers`: array of MCP server configurations (currently only Firecrawl is supported)
- `firecrawl_defaults`: default parameter values for Firecrawl tools

### MCP Servers Configuration

The `mcp_servers` field configures external MCP (Model Context Protocol) integrations.

Each entry supports:

- `id`: server identifier (e.g., `"firecrawl"`)
- `timeout`: request timeout in seconds
- `api_key_env`: environment variable name containing the API key

When configured and the corresponding environment variable is set, the MCP client
is automatically initialized at startup. For Firecrawl, set `FIRECRAWL_API_KEY`
in your environment and include the server in `mcp_servers`.

### Firecrawl Defaults Configuration

The `firecrawl_defaults` field allows you to configure default parameter values for all Firecrawl tools.
This centralizes configuration instead of requiring parameters on each tool call.

Available fields:

- `scrape_formats`: Default output formats for `firecrawl_scrape` (array of strings, e.g., `["markdown"]`, `["html"]`, `["markdown", "rawHtml"]`)
- `scrape_only_main_content`: Default to only main content for `firecrawl_scrape` (boolean, default: true - reduces response size significantly)
- `search_limit`: Default number of results for `firecrawl_search` (integer, default: 3)
- `search_lang`: Default language for `firecrawl_search` (string, default: "en")
- `search_country`: Default country for `firecrawl_search` (string or null, default: null)
- `map_limit`: Default number of URLs for `firecrawl_map` (integer, default: 3)
- `map_include_subdomains`: Default to include subdomains when mapping (boolean, default: false - stays within base domain)
- `map_ignore_query_parameters`: Default to ignore query parameters when mapping (boolean, default: true - reduces duplicate URLs from tracking parameters)
- `crawl_max_pages`: Default maximum pages for `firecrawl_crawl` (integer, default: 3)
- `crawl_include_subdomains`: Default to include subdomains when crawling (boolean, default: false - safer, contained crawling)
- `crawl_allow_external`: Default to allow external links when crawling (boolean, default: false - prevents crawling off-site)

These defaults can always be overridden by explicitly passing the parameter in a tool request.
Tool arguments take precedence over configured defaults.

### Reducing Response Size

To prevent context overflow with large web page content, consider:
- Setting `scrape_only_main_content: true` (default) to exclude boilerplate
- Using `search_limit: 3` instead of 5 for focused searches
- Both settings significantly reduce the token count sent to models

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
