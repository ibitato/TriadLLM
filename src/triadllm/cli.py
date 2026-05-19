from __future__ import annotations

from pathlib import Path

from triadllm.app import TriadApp
from triadllm.config import ConfigManager
from triadllm.i18n import Translator
from triadllm.logging_utils import configure_logging
from triadllm.providers import ProviderGateway
from triadllm.runtime import TriadRuntime


def build_runtime(config_root: str | None = None) -> TriadRuntime:
    """Build the TriadLLM runtime with integrated Firecrawl MCP support.

    The runtime will automatically initialize the Firecrawl MCP client if:
    1. There's a 'firecrawl' entry in settings.mcp_servers
    2. FIRECRAWL_API_KEY environment variable is set
    """
    config_manager = ConfigManager(root=None if config_root is None else Path(config_root))
    settings = config_manager.load_settings()
    profiles = config_manager.load_profiles()
    if settings.default_profile is None:
        settings.default_profile = config_manager.load_profile_default()
        config_manager.save_settings(settings)
    translator = Translator(settings.language)
    logger = configure_logging(config_manager.paths.log_file, settings)
    gateway = ProviderGateway(profiles, settings)

    # TriadRuntime will create ToolBroker internally with Firecrawl MCP client
    # if FIRECRAWL_API_KEY is available in the environment
    return TriadRuntime(
        config_manager=config_manager,
        settings=settings,
        profiles=profiles,
        translator=translator,
        model_gateway=gateway,
        logger=logger,
    )


def main() -> None:
    runtime = build_runtime()
    app = TriadApp(
        runtime=runtime,
        translator=runtime.translator,
        config_manager=runtime.config_manager,
    )
    app.run()
