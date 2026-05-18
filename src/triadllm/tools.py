from __future__ import annotations

import asyncio
import html
import json
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from triadllm.domain import FirecrawlDefaults, PermissionMode, ToolRequest, ToolResult, ToolRisk

if TYPE_CHECKING:
    from triadllm.firecrawl import FirecrawlClient

ApprovalHandler = Callable[[ToolRequest], Awaitable[bool]]

ALLOWLIST_ENV = {"HOME", "PATH", "PWD", "SHELL", "TERM", "USER", "USERNAME", "USERPROFILE", "FIRECRAWL_API_KEY"}

# Maximum tokens for Firecrawl results to prevent model timeouts
MAX_FIRECRAWL_OUTPUT_TOKENS = 8000


def _convert_markdown_to_text(content: str) -> str:
    """Convert markdown content to plain text, removing links, images, and formatting.
    
    This significantly reduces the token count of Firecrawl responses.
    """
    if not content or not isinstance(content, str):
        return content or ""
    
    # Remove HTML comments
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    
    # Remove markdown images: ![alt](url) or ![alt](url "title")
    content = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', content)
    
    # Remove markdown links: [text](url) or [text](url "title")
    # Keep the text, remove the link syntax
    content = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', content)
    
    # Remove HTML tags
    content = re.sub(r'<[^>]+>', '', content)
    
    # Remove markdown headers (keep the text)
    content = re.sub(r'^(#+)\s*', '', content, flags=re.MULTILINE)
    
    # Remove markdown bold/italic: **text**, *text*, `__text__`, `_text_`
    content = re.sub(r'(\*\*|\*|__|_)(.*?)\1', r'\2', content)
    
    # Remove markdown code blocks (keep the code)
    content = re.sub(r'`([^`]*)`', r'\1', content)
    
    # Remove markdown blockquotes: > text
    content = re.sub(r'^>\s*', '', content, flags=re.MULTILINE)
    
    # Remove markdown horizontal rules: ---, ***, ___
    content = re.sub(r'^[\-*_]{3,}\s*$', '', content, flags=re.MULTILINE)
    
    # Remove markdown list markers: - , * , + , or numbers.
    content = re.sub(r'^[\s]*[\-*+]\s+', '', content, flags=re.MULTILINE)
    content = re.sub(r'^[\s]*\d+\.\s+', '', content, flags=re.MULTILINE)
    
    # Collapse multiple newlines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Strip leading/trailing whitespace
    content = content.strip()
    
    return content


def _truncate_text_by_tokens(text: str, max_tokens: int = MAX_FIRECRAWL_OUTPUT_TOKENS) -> str:
    """Truncate text to approximately max_tokens tokens.
    
    Uses a simple estimate: 4 characters ≈ 1 token (rough estimate for English).
    """
    if not text or not isinstance(text, str):
        return text or ""
    
    # Rough estimate: 4 chars per token
    max_chars = max_tokens * 4
    
    if len(text) <= max_chars:
        return text
    
    # Truncate and add indicator
    truncated = text[:max_chars]
    # Find last sentence boundary
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    last_boundary = max(last_period, last_newline)
    
    if last_boundary > max_chars - 100:  # Don't cut too far back
        truncated = truncated[:last_boundary]
    
    return truncated + "\n\n[... Output truncated for size. Use more specific queries for full results.]"


def _sanitize_firecrawl_result(result: dict[str, object]) -> dict[str, object]:
    """Process Firecrawl result to reduce size and convert to plain text.
    
    Applies markdown→text conversion and truncation to all content fields.
    """
    if not isinstance(result, dict):
        return result
    
    sanitized = {}
    for key, value in result.items():
        if key == "data" and isinstance(value, list):
            # Process list of results
            sanitized[key] = []
            for item in value:
                if isinstance(item, dict):
                    processed_item = {}
                    for item_key, item_value in item.items():
                        if item_key in ("content", "text", "description") and isinstance(item_value, str):
                            # Convert markdown to text and truncate
                            text_content = _convert_markdown_to_text(item_value)
                            text_content = _truncate_text_by_tokens(text_content)
                            processed_item[item_key] = text_content
                        else:
                            processed_item[item_key] = item_value
                    sanitized[key].append(processed_item)
                else:
                    sanitized[key].append(item)
        elif key in ("content", "text", "description", "metadata") and isinstance(value, str):
            # Convert markdown to text and truncate
            text_content = _convert_markdown_to_text(value)
            text_content = _truncate_text_by_tokens(text_content)
            sanitized[key] = text_content
        else:
            sanitized[key] = value
    
    return sanitized


class ToolBroker:
    def __init__(
        self,
        workspace: Path | None = None,
        firecrawl_client: "FirecrawlClient | None" = None,
        firecrawl_defaults: FirecrawlDefaults | None = None,
    ) -> None:
        self.workspace = workspace or Path.cwd()
        self.firecrawl_client = firecrawl_client
        self.firecrawl_defaults = firecrawl_defaults or FirecrawlDefaults()

    def available_tools(self) -> list[str]:
        return [
            "shell_exec",
            "read_file",
            "write_file",
            "list_dir",
            "search_files",
            "get_env",
            "pwd",
            "firecrawl_scrape",
            "firecrawl_search",
            "firecrawl_map",
            "firecrawl_crawl",
        ]

    async def execute(
        self,
        request: ToolRequest,
        permission_mode: PermissionMode,
        approval_handler: ApprovalHandler | None = None,
    ) -> ToolResult:
        request = self._normalize_request(request)
        if permission_mode == PermissionMode.ASK:
            if approval_handler is None or not await approval_handler(request):
                return ToolResult(
                    tool=request.tool,
                    success=False,
                    error="Execution denied by user.",
                    exit_code=-1,
                    metadata={"denied": True},
                )

        handler = getattr(self, f"_tool_{request.tool}", None)
        if handler is None:
            return ToolResult(
                tool=request.tool,
                success=False,
                error=f"Unknown tool: {request.tool}",
                exit_code=127,
            )
        return await handler(request.arguments)

    def _normalize_request(self, request: ToolRequest) -> ToolRequest:
        risk = {
            "read_file": ToolRisk.LOW,
            "list_dir": ToolRisk.LOW,
            "search_files": ToolRisk.LOW,
            "pwd": ToolRisk.LOW,
            "get_env": ToolRisk.MEDIUM,
            "shell_exec": ToolRisk.HIGH,
            "write_file": ToolRisk.HIGH,
            "firecrawl_scrape": ToolRisk.LOW,
            "firecrawl_search": ToolRisk.LOW,
            "firecrawl_map": ToolRisk.LOW,
            "firecrawl_crawl": ToolRisk.LOW,
        }.get(request.tool, request.risk)
        return request.model_copy(update={"risk": risk})

    def _resolve_path(self, path_value: str | None) -> Path:
        if not path_value:
            return self.workspace
        candidate = Path(path_value).expanduser()
        if not candidate.is_absolute():
            candidate = self.workspace / candidate
        return candidate.resolve()

    async def _tool_pwd(self, _: dict[str, object]) -> ToolResult:
        return ToolResult(tool="pwd", success=True, output=str(self.workspace))

    async def _tool_list_dir(self, args: dict[str, object]) -> ToolResult:
        path = self._resolve_path(str(args.get("path", ".")))
        if not path.exists():
            return ToolResult(tool="list_dir", success=False, error=f"Path not found: {path}", exit_code=2)
        entries = sorted(item.name for item in path.iterdir())
        return ToolResult(tool="list_dir", success=True, output="\n".join(entries))

    async def _tool_read_file(self, args: dict[str, object]) -> ToolResult:
        path = self._resolve_path(str(args.get("path", "")))
        limit = int(args.get("limit", 12000))
        if not path.exists():
            return ToolResult(tool="read_file", success=False, error=f"File not found: {path}", exit_code=2)
        content = path.read_text(encoding="utf-8", errors="replace")
        return ToolResult(tool="read_file", success=True, output=content[:limit])

    async def _tool_write_file(self, args: dict[str, object]) -> ToolResult:
        path = self._resolve_path(str(args.get("path", "")))
        content = str(args.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(tool="write_file", success=True, output=f"Wrote {len(content)} bytes to {path}")

    async def _tool_search_files(self, args: dict[str, object]) -> ToolResult:
        query = str(args.get("query", "")).strip()
        root = self._resolve_path(str(args.get("path", ".")))
        if not query:
            return ToolResult(tool="search_files", success=False, error="query is required", exit_code=2)
        rg = shutil.which("rg")
        if rg:
            process = await asyncio.create_subprocess_exec(
                rg,
                "-n",
                query,
                str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode not in (0, 1):
                return ToolResult(
                    tool="search_files",
                    success=False,
                    error=stderr.decode("utf-8", errors="replace"),
                    exit_code=process.returncode or 1,
                )
            return ToolResult(
                tool="search_files",
                success=True,
                output=stdout.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
            )

        matches: list[str] = []
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                        if query in line:
                            matches.append(f"{path}:{index}:{line}")
                except OSError:
                    continue
        return ToolResult(tool="search_files", success=True, output="\n".join(matches))

    async def _tool_get_env(self, args: dict[str, object]) -> ToolResult:
        key = str(args.get("key", "")).upper()
        if key not in ALLOWLIST_ENV:
            return ToolResult(
                tool="get_env",
                success=False,
                error=f"Environment variable '{key}' is not allowed.",
                exit_code=2,
            )
        value = os.getenv(key, "")
        # For API key variables, only return whether they exist (True/False), not the actual value
        if "API_KEY" in key or "SECRET" in key or "TOKEN" in key:
            return ToolResult(tool="get_env", success=True, output=str(value != "").lower())
        return ToolResult(tool="get_env", success=True, output=value)

    async def _tool_shell_exec(self, args: dict[str, object]) -> ToolResult:
        command = str(args.get("command", "")).strip()
        cwd = self._resolve_path(str(args.get("cwd", ".")))
        timeout = float(args.get("timeout", 60))
        if not command:
            return ToolResult(tool="shell_exec", success=False, error="command is required", exit_code=2)

        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult(tool="shell_exec", success=False, error="Command timed out.", exit_code=124)

        return ToolResult(
            tool="shell_exec",
            success=process.returncode == 0,
            output=stdout.decode("utf-8", errors="replace"),
            error=stderr.decode("utf-8", errors="replace"),
            exit_code=process.returncode or 0,
            metadata={"command": command, "cwd": str(cwd)},
        )

    async def _tool_firecrawl_scrape(self, args: dict[str, object]) -> ToolResult:
        """Scrape a URL using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_scrape",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_scrape", success=False, error="url is required", exit_code=2)

        # Use configured defaults
        formats = args.get("formats", self.firecrawl_defaults.scrape_formats)
        if isinstance(formats, str):
            formats = [formats]
        elif not isinstance(formats, list):
            formats = self.firecrawl_defaults.scrape_formats

        only_main_content = args.get("onlyMainContent")
        if only_main_content is None:
            only_main_content = self.firecrawl_defaults.scrape_only_main_content

        wait_for = args.get("waitFor")
        if wait_for is not None:
            wait_for = float(wait_for)

        include_tags = args.get("includeTags")
        exclude_tags = args.get("excludeTags")
        remove_base64_images = args.get("removeBase64Images")

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            # Build kwargs for scrape - using v2 parameter names
            scrape_kwargs: dict[str, object] = {
                "url": url,
            }
            if formats:
                scrape_kwargs["formats"] = formats
            if only_main_content is not None:
                scrape_kwargs["only_main_content"] = only_main_content
            if wait_for is not None:
                scrape_kwargs["wait_for"] = wait_for
            if include_tags is not None:
                scrape_kwargs["include_tags"] = include_tags
            if exclude_tags is not None:
                scrape_kwargs["exclude_tags"] = exclude_tags
            if remove_base64_images is not None:
                scrape_kwargs["remove_base64_images"] = remove_base64_images
            if timeout is not None:
                scrape_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.scrape(**scrape_kwargs)
            
            # Sanitize result: convert markdown to text and truncate to prevent model timeouts
            sanitized_result = _sanitize_firecrawl_result(result)
            
            return ToolResult(
                tool="firecrawl_scrape",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"url": url},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_scrape",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"url": url},
            )

    async def _tool_firecrawl_search(self, args: dict[str, object]) -> ToolResult:
        """Search the web using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_search",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(tool="firecrawl_search", success=False, error="query is required", exit_code=2)

        # Use configured defaults
        limit = args.get("limit", self.firecrawl_defaults.search_limit)
        if limit is not None:
            limit = int(limit)

        # Build scrapeOptions
        scrape_options = args.get("scrapeOptions")
        if scrape_options is None:
            scrape_options = {}
        elif isinstance(scrape_options, str):
            try:
                scrape_options = json.loads(scrape_options)
            except json.JSONDecodeError:
                scrape_options = {}

        # Apply configured defaults for scrapeOptions
        if "onlyMainContent" not in scrape_options:
            scrape_options["onlyMainContent"] = self.firecrawl_defaults.search_only_main_content
        if "formats" not in scrape_options and self.firecrawl_defaults.scrape_formats:
            scrape_options["formats"] = self.firecrawl_defaults.scrape_formats

        # Build pageOptions - CRITICAL for v2: fetchContent must be true to get page content
        page_options = args.get("pageOptions")
        if page_options is None:
            page_options = {}
        elif isinstance(page_options, str):
            try:
                page_options = json.loads(page_options)
            except json.JSONDecodeError:
                page_options = {}

        # Apply configured defaults for pageOptions
        if "fetchContent" not in page_options:
            page_options["fetchContent"] = self.firecrawl_defaults.search_fetch_content
        if "onlyMainContent" not in page_options:
            page_options["onlyMainContent"] = self.firecrawl_defaults.search_only_main_content

        # Collect all v2 search parameters
        sources = args.get("sources", self.firecrawl_defaults.search_sources)
        categories = args.get("categories", self.firecrawl_defaults.search_categories)
        country = args.get("country", self.firecrawl_defaults.search_country)
        location = args.get("location", self.firecrawl_defaults.search_location)
        tbs = args.get("tbs", self.firecrawl_defaults.search_tbs)
        include_domains = args.get("includeDomains", self.firecrawl_defaults.search_include_domains)
        exclude_domains = args.get("excludeDomains", self.firecrawl_defaults.search_exclude_domains)
        ignore_invalid_urls = args.get("ignoreInvalidUrls", self.firecrawl_defaults.search_ignore_invalid_urls)
        lang = args.get("lang", self.firecrawl_defaults.search_lang)

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            # Build search kwargs using v2 parameter names (camelCase)
            search_kwargs: dict[str, object] = {
                "query": query,
            }
            if limit is not None:
                search_kwargs["limit"] = limit
            if lang is not None:
                search_kwargs["lang"] = str(lang)
            if country is not None:
                search_kwargs["country"] = str(country)
            if location is not None:
                search_kwargs["location"] = str(location)
            if sources is not None:
                search_kwargs["sources"] = sources
            if categories is not None:
                search_kwargs["categories"] = categories
            if tbs is not None:
                search_kwargs["tbs"] = str(tbs)
            if include_domains is not None:
                search_kwargs["includeDomains"] = include_domains
            if exclude_domains is not None:
                search_kwargs["excludeDomains"] = exclude_domains
            if ignore_invalid_urls is not None:
                search_kwargs["ignoreInvalidURLs"] = ignore_invalid_urls
            if scrape_options:
                search_kwargs["scrapeOptions"] = scrape_options
            if page_options:
                search_kwargs["pageOptions"] = page_options
            if timeout is not None:
                search_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.search(**search_kwargs)
            
            # Sanitize result: convert markdown to text and truncate to prevent model timeouts
            sanitized_result = _sanitize_firecrawl_result(result)
            
            return ToolResult(
                tool="firecrawl_search",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"query": query},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_search",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"query": query},
            )

    async def _tool_firecrawl_map(self, args: dict[str, object]) -> ToolResult:
        """Map a website using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_map",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_map", success=False, error="url is required", exit_code=2)

        search = args.get("search")
        if search is not None:
            search = str(search)

        # Use configured defaults
        limit = args.get("limit", self.firecrawl_defaults.map_limit)
        if limit is not None:
            limit = int(limit)

        # Use configured defaults for map options - v2 uses includeSubdomains
        include_subdomains = args.get("includeSubdomains")
        if include_subdomains is None:
            include_subdomains = self.firecrawl_defaults.map_include_subdomains

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            map_kwargs: dict[str, object] = {
                "url": url,
            }
            if search:
                map_kwargs["search"] = search
            if limit is not None:
                map_kwargs["limit"] = limit
            if include_subdomains is not None:
                map_kwargs["include_subdomains"] = include_subdomains
            if timeout is not None:
                map_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.map(**map_kwargs)
            
            # Sanitize result: convert markdown to text and truncate to prevent model timeouts
            sanitized_result = _sanitize_firecrawl_result(result)
            
            return ToolResult(
                tool="firecrawl_map",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"url": url},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_map",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"url": url},
            )

    async def _tool_firecrawl_crawl(self, args: dict[str, object]) -> ToolResult:
        """Crawl a website using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_crawl",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_crawl", success=False, error="url is required", exit_code=2)

        # Use configured defaults - v2 uses 'limit' not 'max_pages'
        limit = args.get("limit", self.firecrawl_defaults.crawl_limit)
        if limit is not None:
            limit = int(limit)

        # Use configured defaults for crawl options - v2 uses allowSubdomains, allowExternalLinks
        allow_subdomains = args.get("allowSubdomains")
        if allow_subdomains is None:
            allow_subdomains = self.firecrawl_defaults.crawl_allow_subdomains

        allow_external_links = args.get("allowExternalLinks")
        if allow_external_links is None:
            allow_external_links = self.firecrawl_defaults.crawl_allow_external_links

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            crawl_kwargs: dict[str, object] = {
                "url": url,
            }
            if limit is not None:
                crawl_kwargs["limit"] = limit
            if allow_subdomains is not None:
                crawl_kwargs["allow_subdomains"] = allow_subdomains
            if allow_external_links is not None:
                crawl_kwargs["allow_external_links"] = allow_external_links
            if timeout is not None:
                crawl_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.crawl(**crawl_kwargs)
            
            # Sanitize result: convert markdown to text and truncate to prevent model timeouts
            sanitized_result = _sanitize_firecrawl_result(result)
            
            return ToolResult(
                tool="firecrawl_crawl",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"url": url},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_crawl",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"url": url},
            )
