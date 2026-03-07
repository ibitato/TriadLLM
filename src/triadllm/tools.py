from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Awaitable, Callable

from triadllm.domain import PermissionMode, ToolRequest, ToolResult, ToolRisk

ApprovalHandler = Callable[[ToolRequest], Awaitable[bool]]

ALLOWLIST_ENV = {"HOME", "PATH", "PWD", "SHELL", "TERM", "USER", "USERNAME", "USERPROFILE"}


class ToolBroker:
    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or Path.cwd()

    def available_tools(self) -> list[str]:
        return [
            "shell_exec",
            "read_file",
            "write_file",
            "list_dir",
            "search_files",
            "get_env",
            "pwd",
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
        return ToolResult(tool="get_env", success=True, output=os.getenv(key, ""))

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
