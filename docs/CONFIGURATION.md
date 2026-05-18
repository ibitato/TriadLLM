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
    "scrape_only_main_content": true,
    "search_limit": 3,
    "search_sources": ["web"],
    "search_fetch_content": true
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
- `mcp_servers`: array of MCP server configurations (Firecrawl uses REST API v2 directly)
- `firecrawl_defaults`: default parameter values for Firecrawl tools (v2 API)

### MCP Servers Configuration

The `mcp_servers` field configures external MCP (Model Context Protocol) integrations.

Each entry supports:

- `id`: server identifier (e.g., `"firecrawl"`)
- `timeout`: request timeout in seconds
- `api_key_env`: environment variable name containing the API key

For Firecrawl, the client uses the REST API v2 directly (not MCP protocol).
Set `FIRECRAWL_API_KEY` in your environment and include the server in `mcp_servers`
to enable Firecrawl tools.

### Firecrawl Defaults Configuration (v2 API)

The `firecrawl_defaults` field allows you to configure default parameter values for all Firecrawl tools.
This centralizes configuration instead of requiring parameters on each tool call.

**Note**: TriadLLM uses Firecrawl API v2 endpoints (`/v2/scrape`, `/v2/search`, `/v2/map`, `/v2/crawl`).

Available fields:

- `scrape_formats`: Default output formats for `firecrawl_scrape` (array of strings: `"markdown"`, `"html"`, `"rawHtml"`, `"links"`, `"pdf"`; default: `["markdown"]`)
- `scrape_only_main_content`: Only main content for `firecrawl_scrape` (boolean, default: true)
- `scrape_wait_for`: Wait time for JavaScript (ms)
- `scrape_include_tags`: HTML tags to include (array)
- `scrape_exclude_tags`: HTML tags to exclude (array)
- `scrape_remove_base64_images`: Remove base64 images (boolean, default: false)
- `search_limit`: Number of results for `firecrawl_search` (integer, default: 3)
- `search_sources`: Result types for search (array: `"web"`, `"news"`, `"images"`; default: `["web"]`)
- `search_categories`: Categories filter (array: `"github"`, `"research"`, `"pdf"`)
- `search_lang`: Language for search (string, default: `"en"`)
- `search_country`: Country ISO code for search
- `search_location`: Location string for search
- `search_tbs`: Time filter for search (e.g., `"qdr:m"` for past month)
- `search_include_domains`: Allowed domains for search (array)
- `search_exclude_domains`: Excluded domains for search (array)
- `search_ignore_invalid_urls`: Ignore invalid URLs (boolean, default: true)
- `search_fetch_content`: **CRITICAL** - Fetch page content in search results (boolean, default: true)
- `search_only_main_content`: Only main content for search results (boolean, default: true)
- `map_limit`: Maximum URLs for `firecrawl_map` (integer, default: 3)
- `map_include_subdomains`: Include subdomains when mapping (boolean, default: false)
- `crawl_limit`: Maximum pages for `firecrawl_crawl` (integer, default: 3)
- `crawl_allow_subdomains`: Allow subdomains when crawling (boolean, default: false)
- `crawl_allow_external_links`: Allow external links when crawling (boolean, default: false)

These defaults can always be overridden by explicitly passing the parameter in a tool request.
Tool arguments take precedence over configured defaults.

### Reducing Response Size

To prevent context overflow with large web page content, consider:
- Setting `scrape_only_main_content: true` (default) to exclude boilerplate
- Setting `search_fetch_content: true` (default) to include page content in search results
- Using `search_limit: 3` (default) for focused searches
- Using `search_sources: ["web"]` (default) instead of multiple sources
- All these settings significantly reduce the token count sent to models

**v2 API Note**: The search endpoint requires `pageOptions.fetchContent: true` to return page content.
This is enabled by default via the `search_fetch_content` setting.

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
