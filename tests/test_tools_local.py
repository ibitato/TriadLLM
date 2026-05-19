"""Tests for local tool handlers in ToolBroker."""

from __future__ import annotations

from pathlib import Path

import pytest

from triadllm.domain import PermissionMode, ToolRequest, ToolRisk
from triadllm.tools import ToolBroker


@pytest.fixture
def broker(tmp_path: Path) -> ToolBroker:
    return ToolBroker(workspace=tmp_path)


class TestShellExec:
    @pytest.mark.asyncio
    async def test_shell_exec_timeout(self, broker: ToolBroker):
        request = ToolRequest(
            tool="shell_exec",
            arguments={"command": "sleep 10", "timeout": 0.1},
            reason="test",
            risk=ToolRisk.HIGH,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert not result.success
        assert result.exit_code == 124
        assert "timed out" in result.error.lower()


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_file_not_found(self, broker: ToolBroker):
        request = ToolRequest(
            tool="read_file",
            arguments={"path": "nonexistent_file.txt"},
            reason="test",
            risk=ToolRisk.LOW,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert not result.success
        assert result.exit_code == 2
        assert "not found" in result.error.lower()


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_write_file_creates_parents(self, broker: ToolBroker):
        request = ToolRequest(
            tool="write_file",
            arguments={"path": "deep/nested/dir/file.txt", "content": "hello"},
            reason="test",
            risk=ToolRisk.HIGH,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert result.success
        written = (broker.workspace / "deep" / "nested" / "dir" / "file.txt").read_text()
        assert written == "hello"


class TestListDir:
    @pytest.mark.asyncio
    async def test_list_dir_not_found(self, broker: ToolBroker):
        request = ToolRequest(
            tool="list_dir",
            arguments={"path": "nonexistent_dir"},
            reason="test",
            risk=ToolRisk.LOW,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert not result.success
        assert result.exit_code == 2


class TestSearchFiles:
    @pytest.mark.asyncio
    async def test_search_files_empty_query(self, broker: ToolBroker):
        request = ToolRequest(
            tool="search_files",
            arguments={"query": ""},
            reason="test",
            risk=ToolRisk.LOW,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert not result.success
        assert "query is required" in result.error


class TestGetEnv:
    @pytest.mark.asyncio
    async def test_get_env_blocked_key(self, broker: ToolBroker):
        request = ToolRequest(
            tool="get_env",
            arguments={"key": "SECRET_PASSWORD"},
            reason="test",
            risk=ToolRisk.MEDIUM,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert not result.success
        assert "not allowed" in result.error

    @pytest.mark.asyncio
    async def test_get_env_api_key_redacted(self, broker: ToolBroker, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "super-secret-key")
        request = ToolRequest(
            tool="get_env",
            arguments={"key": "FIRECRAWL_API_KEY"},
            reason="test",
            risk=ToolRisk.MEDIUM,
        )
        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        assert result.success
        # Should return "true" (key exists) not the actual value
        assert result.output == "true"
        assert "super-secret-key" not in result.output
