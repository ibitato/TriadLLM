from __future__ import annotations

import logging
from pathlib import Path

import pytest
from textual.widgets import Button

from multibrainllm.app import MultiBrainApp, PermissionScreen
from multibrainllm.config import ConfigManager
from multibrainllm.domain import ToolRequest, UserSettings
from multibrainllm.i18n import Translator
from multibrainllm.runtime import MultiBrainRuntime
from multibrainllm.tools import ToolBroker


class IdleGateway:
    async def ainvoke(self, role, schema, system_prompt, payload):  # noqa: ANN001, ANN201
        raise RuntimeError("not used in this test")


@pytest.mark.anyio
async def test_app_handles_status_command(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = MultiBrainRuntime(
        config_manager=manager,
        settings=UserSettings(language="en"),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = MultiBrainApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.press("s", "t", "a", "t", "u", "s", "enter")
        transcript = app.query_one("#transcript")
        assert len(transcript.children) >= 2


@pytest.mark.anyio
async def test_app_toggles_reasoning_visibility(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-reasoning")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = MultiBrainRuntime(
        config_manager=manager,
        settings=UserSettings(language="en", show_reasoning=True),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = MultiBrainApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await app._add_block("Reasoning", "thinking", "reasoning")
        await pilot.press("/", "r", "e", "a", "s", "o", "n", "i", "n", "g", "space", "o", "f", "f", "enter")
        transcript = app.query_one("#transcript")
        reasoning_blocks = [child for child in transcript.children if "reasoning" in child.classes]
        assert reasoning_blocks
        assert "is-hidden" in reasoning_blocks[0].classes


@pytest.mark.anyio
async def test_app_starts_new_conversation(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-new")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = MultiBrainRuntime(
        config_manager=manager,
        settings=UserSettings(language="en", show_reasoning=True),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = MultiBrainApp(runtime=runtime, translator=translator, config_manager=manager)

    async with app.run_test() as pilot:
        await app._add_block("User", "hello", "user")
        await pilot.press("/", "n", "e", "w", "enter")
        transcript = app.query_one("#transcript")
        assert len(transcript.children) >= 2
        assert runtime.history == []


@pytest.mark.anyio
async def test_prompt_permission_uses_screen_callback_result(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    translator = Translator("en")
    logger = logging.getLogger("test-app-permission")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    runtime = MultiBrainRuntime(
        config_manager=manager,
        settings=UserSettings(language="en"),
        profiles={},
        translator=translator,
        model_gateway=IdleGateway(),
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )
    app = MultiBrainApp(runtime=runtime, translator=translator, config_manager=manager)

    def fake_push_screen(screen, callback=None, wait_for_dismiss=False, mode=None):  # noqa: ANN001, ANN202
        assert callback is not None
        assert wait_for_dismiss is False
        callback(True)
        return None

    app.push_screen = fake_push_screen  # type: ignore[method-assign]

    approved = await app._prompt_permission(
        ToolRequest(tool="list_dir", arguments={"path": "."}, reason="test")
    )

    assert approved is True


@pytest.mark.anyio
async def test_permission_screen_has_keyboard_shortcuts(tmp_path: Path) -> None:
    app = MultiBrainApp(
        runtime=MultiBrainRuntime(
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
