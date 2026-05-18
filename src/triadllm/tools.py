from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from triadllm.domain import PermissionMode, ToolRequest, ToolResult, ToolRisk

if TYPE_CHECKING:
    from triadllm.mcp import FirecrawlMCPClient

ApprovalHandler = Callable[[ToolRequest], Awaitable[bool]]

ALLOWLIST_ENV = {"HOME", "PATH", "PWD", "SHELL", "TERM", "USER", "USERNAME", "USERPROFILE", "FIRECRAWL_API_KEY"}


class ToolBroker:
    def __init__(self, workspace: Path | None = None, firecrawl_client: "FirecrawlMCPClient | None" = None) -> None:
        self.workspace = workspace or Path.cwd()
        self.firecrawl_client = firecrawl_client

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
        """Scrape a URL using Firecrawl MCP."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_scrape",
                success=False,
                error="Firecrawl MCP is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_scrape", success=False, error="url is required", exit_code=2)

        formats = args.get("formats")
        if isinstance(formats, str):
            formats = [formats]
        elif not isinstance(formats, list):
            formats = None

        wait_for = args.get("waitFor") or args.get("wait_for")
        if wait_for is not None:
            wait_for = float(wait_for)

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            # Build kwargs for scrape
            scrape_kwargs: dict[str, object] = {}
            if formats:
                scrape_kwargs["formats"] = formats
            if wait_for:
                scrape_kwargs["wait_for"] = wait_for
            if timeout:
                scrape_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.scrape(url, **scrape_kwargs)
            return ToolResult(
                tool="firecrawl_scrape",
                success=True,
                output=json.dumps(result, ensure_ascii=False),
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
        """Search the web using Firecrawl MCP."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_search",
                success=False,
                error="Firecrawl MCP is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(tool="firecrawl_search", success=False, error="query is required", exit_code=2)

        limit = args.get("limit")
        if limit is not None:
            limit = int(limit)

        page_options = args.get("pageOptions") or args.get("page_options")
        if isinstance(page_options, str):
            try:
                page_options = json.loads(page_options)
            except json.JSONDecodeError:
                page_options = None

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            search_kwargs: dict[str, object] = {}
            if limit:
                search_kwargs["limit"] = limit
            if page_options:
                search_kwargs["page_options"] = page_options
            if timeout:
                search_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.search(query, **search_kwargs)
            return ToolResult(
                tool="firecrawl_search",
                success=True,
                output=json.dumps(result, ensure_ascii=False),
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
        """Map a website using Firecrawl MCP."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_map",
                success=False,
                error="Firecrawl MCP is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_map", success=False, error="url is required", exit_code=2)

        search = args.get("search")
        if search is not None:
            search = str(search)

        limit = args.get("limit")
        if limit is not None:
            limit = int(limit)

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            map_kwargs: dict[str, object] = {}
            if search:
                map_kwargs["search"] = search
            if limit:
                map_kwargs["limit"] = limit
            if timeout:
                map_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.map(url, **map_kwargs)
            return ToolResult(
                tool="firecrawl_map",
                success=True,
                output=json.dumps(result, ensure_ascii=False),
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
        """Crawl a website using Firecrawl MCP."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_crawl",
                success=False,
                error="Firecrawl MCP is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_crawl", success=False, error="url is required", exit_code=2)

        max_pages = args.get("maxPages") or args.get("max_pages")
        if max_pages is not None:
            max_pages = int(max_pages)

        include_subdomains = args.get("includeSubdomains") or args.get("include_subdomains")
        if include_subdomains is not None:
            include_subdomains = bool(include_subdomains)
        else:
            include_subdomains = False

        allow_external = args.get("allowExternal") or args.get("allow_external")
        if allow_external is not None:
            allow_external = bool(allow_external)
        else:
            allow_external = False

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            crawl_kwargs: dict[str, object] = {}
            if max_pages is not None:
                crawl_kwargs["max_pages"] = max_pages
            if include_subdomains is not None:
                crawl_kwargs["include_subdomains"] = include_subdomains
            if allow_external is not None:
                crawl_kwargs["allow_external"] = allow_external
            if timeout is not None:
                crawl_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.crawl(url, **crawl_kwargs)
            return ToolResult(
                tool="firecrawl_crawl",
                success=True,
                output=json.dumps(result, ensure_ascii=False),
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
