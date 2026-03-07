from __future__ import annotations

import logging
from pathlib import Path

import pytest

from multibrainllm.app import MultiBrainApp
from multibrainllm.config import ConfigManager
from multibrainllm.domain import UserSettings
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
