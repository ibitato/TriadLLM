from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest
from pydantic import BaseModel
from textual.widgets import Button

from triadllm.app import TriadApp, PermissionScreen
from triadllm.config import ConfigManager
from triadllm.domain import (
    AgentActionKind,
    AgentResponse,
    AgentRole,
    ConsolidatedResponse,
    ModelInvocationResult,
    PermissionMode,
    ToolRequest,
    UserSettings,
)
from triadllm.i18n import Translator
from triadllm.runtime import TriadRuntime
from triadllm.tools import ToolBroker


class IdleGateway:
    async def ainvoke(self, role, schema, system_prompt, payload):  # noqa: ANN001, ANN201
        raise RuntimeError("not used in this test")


class ScriptedGateway:
    def __init__(self, scripted: dict[AgentRole, list[ModelInvocationResult[BaseModel]]]) -> None:
        self.scripted = {role: list(responses) for role, responses in scripted.items()}

    async def ainvoke(self, role, schema, system_prompt, payload):  # noqa: ANN001, ANN201
        response = self.scripted[role].pop(0)
        assert isinstance(response.parsed, schema)
        return response


@pytest.mark.anyio
async def test_app_handles_status_command(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en"),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.press("s", "t", "a", "t", "u", "s", "enter")
        transcript = app.query_one("#transcript")
        assert len(transcript.children) >= 2


@pytest.mark.anyio
async def test_app_shows_no_profiles_hint_on_fresh_install(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-no-profiles")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en"),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test():
        transcript = app.query_one("#transcript")
        joined = "\n".join(str(child.render()) for child in transcript.children)
        assert "No provider profiles are configured yet." in joined


@pytest.mark.anyio
async def test_app_toggles_reasoning_visibility(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-reasoning")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en", show_reasoning=True),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await app._add_block("Reasoning", "thinking", "reasoning")
        await pilot.press("/", "r", "e", "a", "s", "o", "n", "i", "n", "g", "space", "o", "f", "f", "enter")
        transcript = app.query_one("#transcript")
        reasoning_blocks = [child for child in transcript.children if "reasoning" in child.classes]
        assert reasoning_blocks
        assert "is-hidden" in reasoning_blocks[0].classes


@pytest.mark.anyio
async def test_app_toggles_tool_result_visibility(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-tools")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en", show_tool_results=True),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await app._add_block("Tool", "output", "tool")
        await pilot.press("/", "t", "o", "o", "l", "r", "e", "s", "u", "l", "t", "s", "space", "o", "f", "f", "enter")
        transcript = app.query_one("#transcript")
        tool_blocks = [child for child in transcript.children if "tool" in child.classes]
        assert tool_blocks
        assert "is-hidden" in tool_blocks[0].classes


@pytest.mark.anyio
async def test_app_starts_new_conversation(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-new")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en", show_reasoning=True),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await app._add_block("User", "hello", "user")
        await pilot.press("/", "n", "e", "w", "enter")
        transcript = app.query_one("#transcript")
        assert len(transcript.children) >= 2
        assert runtime.history == []


@pytest.mark.anyio
async def test_permission_screen_has_keyboard_shortcuts(tmp_path: Path) -> None:
    app = TriadApp(
        runtime=TriadRuntime(
            config_manager=ConfigManager(root=tmp_path),
            settings=UserSettings(language="en"),
            profiles={},
            translator=Translator("en"),
            model_gateway=IdleGateway(),
            tool_broker=ToolBroker(workspace=tmp_path),
            logger=logging.getLogger("test-app-permission-focus"),
        ),
        translator=Translator("en"),
        config_manager=ConfigManager(root=tmp_path),
    )

    async with app.run_test():
        screen = PermissionScreen(
            ToolRequest(tool="list_dir", arguments={"path": "."}, reason="test"),
            Translator("en"),
        )
        app.push_screen(screen)
        await screen._mounted_event.wait()
        approve_button = screen.query_one("#approve", Button)
        assert approve_button is not None
        assert ("enter", "approve", "Approve") in screen.BINDINGS
        assert ("escape", "deny", "Deny") in screen.BINDINGS


@pytest.mark.anyio
async def test_prompt_permission_resolves_on_enter(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-permission-enter")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en"),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        worker = app.run_worker(
            app._prompt_permission(ToolRequest(tool="list_dir", arguments={"path": "."}, reason="test")),
            thread=False,
            exit_on_error=False,
        )
        await pilot.pause()
        assert isinstance(app.screen, PermissionScreen)
        await pilot.press("enter")
        assert await asyncio.wait_for(worker.wait(), timeout=2) is True


@pytest.mark.anyio
async def test_prompt_permission_resolves_on_escape(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-permission-escape")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en"),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        worker = app.run_worker(
            app._prompt_permission(ToolRequest(tool="list_dir", arguments={"path": "."}, reason="test")),
            thread=False,
            exit_on_error=False,
        )
        await pilot.pause()
        assert isinstance(app.screen, PermissionScreen)
        await pilot.press("escape")
        assert await asyncio.wait_for(worker.wait(), timeout=2) is False


@pytest.mark.anyio
async def test_full_tool_flow_resolves_permission_modal_from_worker(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-full-tool-flow")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = TriadRuntime(
        config_manager=manager,
        settings=UserSettings(language="en", permission_mode=PermissionMode.ASK),
        profiles={},
        translator=translator,
        model_gateway=ScriptedGateway(
            {
                AgentRole.PROCESSOR: [
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.REQUEST_TOOL,
                            tool_request=ToolRequest(
                                tool="list_dir",
                                arguments={"path": "."},
                                reason="Verify the workspace contents.",
                            ),
                        )
                    ),
                    ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Processor done")),
                ],
                AgentRole.VALIDATOR: [
                    ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Validator done")),
                ],
                AgentRole.ORCHESTRATOR: [
                    ModelInvocationResult(
                        parsed=ConsolidatedResponse(
                            processor_view="Processor done",
                            validator_view="Validator done",
                            synthesis="Final answer",
                        )
                    )
                ],
            }
        ),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = TriadApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await app._dispatch_input("check workspace")
        await pilot.pause()
        assert isinstance(app.screen, PermissionScreen)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        transcript = app.query_one("#transcript")
        joined = "\n".join(str(child.render()) for child in transcript.children)
        assert "Final answer" in joined
