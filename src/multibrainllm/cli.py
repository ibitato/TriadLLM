from __future__ import annotations

from pathlib import Path

from multibrainllm.app import MultiBrainApp
from multibrainllm.config import ConfigManager
from multibrainllm.i18n import Translator
from multibrainllm.logging_utils import configure_logging
from multibrainllm.providers import LangChainGateway
from multibrainllm.runtime import MultiBrainRuntime
from multibrainllm.tools import ToolBroker


def build_runtime(config_root: str | None = None) -> MultiBrainRuntime:
    config_manager = ConfigManager(root=None if config_root is None else Path(config_root))
    settings = config_manager.load_settings()
    profiles = config_manager.load_profiles()
    if settings.default_profile is None:
        settings.default_profile = config_manager.load_profile_default()
        config_manager.save_settings(settings)
    translator = Translator(settings.language)
    logger = configure_logging(config_manager.paths.log_file, settings)
    gateway = LangChainGateway(profiles, settings)
    broker = ToolBroker()
    return MultiBrainRuntime(
        config_manager=config_manager,
        settings=settings,
        profiles=profiles,
        translator=translator,
        model_gateway=gateway,
        tool_broker=broker,
        logger=logger,
    )


def main() -> None:
    runtime = build_runtime()
    app = MultiBrainApp(
        runtime=runtime,
        translator=runtime.translator,
        config_manager=runtime.config_manager,
    )
    app.run()
