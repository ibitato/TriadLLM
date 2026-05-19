"""Tests for Firecrawl tool handlers in ToolBroker."""

from __future__ import annotations

import json
import os

import pytest

from triadllm.domain import FirecrawlDefaults, PermissionMode, ToolRequest, ToolRisk
from triadllm.firecrawl import FirecrawlClient
from triadllm.tools import ToolBroker


@pytest.fixture(autouse=True)
def clear_env_var():
    """Clear FIRECRAWL_API_KEY before each test."""
    if "FIRECRAWL_API_KEY" in os.environ:
        del os.environ["FIRECRAWL_API_KEY"]
    yield
    if "FIRECRAWL_API_KEY" in os.environ:
        del os.environ["FIRECRAWL_API_KEY"]


@pytest.fixture
def mock_firecrawl_client():
    """Create a mock Firecrawl client for testing."""
    return FirecrawlClient(api_key="test-key")


class TestToolBrokerFirecrawl:
    """Tests for ToolBroker with Firecrawl integration."""

    def test_firecrawl_tools_in_available_tools(self):
        """Firecrawl tools are in available tools list."""
        broker = ToolBroker()
        tools = broker.available_tools()
        assert "firecrawl_scrape" in tools
        assert "firecrawl_search" in tools
        assert "firecrawl_map" in tools
        assert "firecrawl_crawl" in tools

    def test_tool_broker_receives_client(self, mock_firecrawl_client):
        """ToolBroker can receive Firecrawl client."""
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        assert broker.firecrawl_client is mock_firecrawl_client

    def test_tool_broker_default_client_none(self):
        """ToolBroker has None client by default."""
        broker = ToolBroker()
        assert broker.firecrawl_client is None


class TestFirecrawlScrapeHandler:
    """Tests for firecrawl_scrape tool handler."""

    @pytest.mark.asyncio
    async def test_scrape_success(self, mock_firecrawl_client):
        """Scrape handler returns success with mock client."""

        async def mock_scrape(url, **kw):
            return {"url": url, "content": "test"}

        mock_firecrawl_client.scrape = mock_scrape

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is True
        assert result.tool == "firecrawl_scrape"
        output = json.loads(result.output)
        assert output["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_scrape_no_client(self):
        """Scrape handler fails without client."""
        broker = ToolBroker(firecrawl_client=None)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is False
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_scrape_missing_url(self, mock_firecrawl_client):
        """Scrape handler fails without URL."""
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is False
        assert "url is required" in result.error

    @pytest.mark.asyncio
    async def test_scrape_with_formats(self, mock_firecrawl_client):
        """Scrape handler passes formats parameter."""
        received_args = {}

        async def mock_scrape(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com", "formats": ["markdown"]},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "formats" in received_args
        assert received_args["formats"] == ["markdown"]


class TestFirecrawlSearchHandler:
    """Tests for firecrawl_search tool handler."""

    @pytest.mark.asyncio
    async def test_search_success(self, mock_firecrawl_client):
        """Search handler returns success."""

        async def mock_search(query, **kw):
            return {"query": query, "results": []}

        mock_firecrawl_client.search = mock_search

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test query"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is True
        output = json.loads(result.output)
        assert output["query"] == "test query"

    @pytest.mark.asyncio
    async def test_search_missing_query(self, mock_firecrawl_client):
        """Search handler fails without query."""
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is False
        assert "query is required" in result.error

    @pytest.mark.asyncio
    async def test_search_with_limit(self, mock_firecrawl_client):
        """Search handler passes limit parameter."""
        received_args = {}

        async def mock_search(query, **kwargs):
            received_args.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test", "limit": 5},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "limit" in received_args
        assert received_args["limit"] == 5


class TestFirecrawlMapHandler:
    """Tests for firecrawl_map tool handler."""

    @pytest.mark.asyncio
    async def test_map_success(self, mock_firecrawl_client):
        """Map handler returns success."""

        async def mock_map(url, **kw):
            return {"url": url, "urls": []}

        mock_firecrawl_client.map = mock_map

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_map",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is True
        output = json.loads(result.output)
        assert output["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_map_missing_url(self, mock_firecrawl_client):
        """Map handler fails without URL."""
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_map",
            arguments={},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is False
        assert "url is required" in result.error


class TestFirecrawlCrawlHandler:
    """Tests for firecrawl_crawl tool handler."""

    @pytest.mark.asyncio
    async def test_crawl_success(self, mock_firecrawl_client):
        """Crawl handler returns success."""

        async def mock_crawl(url, **kw):
            return {"url": url, "pages": []}

        mock_firecrawl_client.crawl = mock_crawl

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is True
        output = json.loads(result.output)
        assert output["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_crawl_missing_url(self, mock_firecrawl_client):
        """Crawl handler fails without URL."""
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is False
        assert "url is required" in result.error

    @pytest.mark.asyncio
    async def test_crawl_with_options(self, mock_firecrawl_client):
        """Crawl handler passes all options."""
        received_args = {}

        async def mock_crawl(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.crawl = mock_crawl

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={
                "url": "https://example.com",
                "limit": 10,
                "allowBackwardLinks": True,
                "allowExternalLinks": False,
            },
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert received_args.get("limit") == 10
        assert received_args.get("allow_backward_links") is True
        assert received_args.get("allow_external_links") is False


class TestFirecrawlPermissionMode:
    """Tests for permission handling with Firecrawl tools."""

    @pytest.mark.asyncio
    async def test_ask_mode_denies_tool(self, mock_firecrawl_client):
        """Tool is denied in ASK mode without approval."""
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        # Without approval handler, tool is denied in ASK mode
        result = await broker.execute(
            request,
            permission_mode=PermissionMode.ASK,
        )

        assert result.success is False
        assert "denied" in result.error.lower()

    @pytest.mark.asyncio
    async def test_yolo_mode_allows_tool(self, mock_firecrawl_client):
        """Tool is allowed in YOLO mode."""

        async def mock_scrape(url, **kw):
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.YOLO,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_ask_mode_with_approval(self, mock_firecrawl_client):
        """Tool is allowed in ASK mode with approval."""

        async def mock_scrape(url, **kw):
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape

        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        # Approval handler that always approves
        async def approve(_):
            return True

        result = await broker.execute(
            request,
            permission_mode=PermissionMode.ASK,
            approval_handler=approve,
        )

        assert result.success is True


class TestFirecrawlDefaults:
    """Tests for Firecrawl defaults configuration."""

    def test_tool_broker_receives_defaults(self):
        """ToolBroker can receive Firecrawl defaults."""
        defaults = FirecrawlDefaults(
            scrape_formats=["html"],
            search_limit=10,
            map_limit=10,
            crawl_limit=10,
        )
        broker = ToolBroker(firecrawl_defaults=defaults)
        assert broker.firecrawl_defaults is defaults

    def test_tool_broker_default_defaults(self):
        """ToolBroker creates default FirecrawlDefaults if none provided."""
        broker = ToolBroker()
        assert broker.firecrawl_defaults is not None
        assert isinstance(broker.firecrawl_defaults, FirecrawlDefaults)
        assert broker.firecrawl_defaults.scrape_formats == ["markdown"]
        assert broker.firecrawl_defaults.search_limit == 5
        assert broker.firecrawl_defaults.search_only_main_content is True
        assert broker.firecrawl_defaults.map_limit == 5
        assert broker.firecrawl_defaults.crawl_limit == 5

    @pytest.mark.asyncio
    async def test_scrape_uses_default_formats(self, mock_firecrawl_client):
        """Scrape handler uses configured default formats."""
        received_args = {}

        async def mock_scrape(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape

        defaults = FirecrawlDefaults(scrape_formats=["html", "rawHtml"])
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "formats" in received_args
        assert received_args["formats"] == ["html", "rawHtml"]

    @pytest.mark.asyncio
    async def test_scrape_arg_overrides_default(self, mock_firecrawl_client):
        """Scrape handler: explicit formats argument overrides defaults."""
        received_args = {}

        async def mock_scrape(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape

        defaults = FirecrawlDefaults(scrape_formats=["html"])
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com", "formats": ["markdown"]},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "formats" in received_args
        assert received_args["formats"] == ["markdown"]

    @pytest.mark.asyncio
    async def test_search_uses_default_limit(self, mock_firecrawl_client):
        """Search handler uses configured default limit."""
        received_args = {}

        async def mock_search(query, **kwargs):
            received_args.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search

        defaults = FirecrawlDefaults(search_limit=10)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "limit" in received_args
        assert received_args["limit"] == 10

    @pytest.mark.asyncio
    async def test_map_uses_default_limit(self, mock_firecrawl_client):
        """Map handler uses configured default limit."""
        received_args = {}

        async def mock_map(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.map = mock_map

        defaults = FirecrawlDefaults(map_limit=8)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_map",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "limit" in received_args
        assert received_args["limit"] == 8

    @pytest.mark.asyncio
    async def test_crawl_uses_default_limit(self, mock_firecrawl_client):
        """Crawl handler uses configured default limit."""
        received_args = {}

        async def mock_crawl(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.crawl = mock_crawl

        defaults = FirecrawlDefaults(crawl_limit=20)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "limit" in received_args
        assert received_args["limit"] == 20

    @pytest.mark.asyncio
    async def test_scrape_uses_default_only_main_content(self, mock_firecrawl_client):
        """Scrape handler uses configured default onlyMainContent."""
        received_args = {}

        async def mock_scrape(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape

        defaults = FirecrawlDefaults(scrape_only_main_content=True)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "only_main_content" in received_args
        assert received_args["only_main_content"] is True

    @pytest.mark.asyncio
    async def test_search_uses_default_lang(self, mock_firecrawl_client):
        """Search handler uses configured default lang."""
        received_args = {}

        async def mock_search(query, **kwargs):
            received_args.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search

        defaults = FirecrawlDefaults(search_lang="es")
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "lang" in received_args
        assert received_args["lang"] == "es"

    @pytest.mark.asyncio
    async def test_search_uses_default_country(self, mock_firecrawl_client):
        """Search handler uses configured default country."""
        received_args = {}

        async def mock_search(query, **kwargs):
            received_args.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search

        defaults = FirecrawlDefaults(search_country="us")
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "country" in received_args
        assert received_args["country"] == "us"

    @pytest.mark.asyncio
    async def test_search_arg_overrides_lang_country(self, mock_firecrawl_client):
        """Search handler: explicit lang/country override defaults."""
        received_args = {}

        async def mock_search(query, **kwargs):
            received_args.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search

        defaults = FirecrawlDefaults(search_lang="en", search_country="us")
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test", "lang": "es", "country": "es"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert received_args["lang"] == "es"
        assert received_args["country"] == "es"


class TestFirecrawlNewDefaults:
    """Tests for newly added Firecrawl default parameters."""

    @pytest.mark.asyncio
    async def test_map_uses_default_include_subdomains(self, mock_firecrawl_client):
        """Map handler uses configured default includeSubdomains."""
        received_args = {}

        async def mock_map(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.map = mock_map

        defaults = FirecrawlDefaults(map_include_subdomains=True)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_map",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "include_subdomains" in received_args
        assert received_args["include_subdomains"] is True

    @pytest.mark.asyncio
    async def test_map_passes_include_subdomains_to_client(self, mock_firecrawl_client):
        """Map handler passes includeSubdomains to client method."""
        received_args = {}

        async def mock_map(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.map = mock_map

        defaults = FirecrawlDefaults(map_include_subdomains=True)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_map",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "include_subdomains" in received_args
        assert received_args["include_subdomains"] is True

    @pytest.mark.asyncio
    async def test_map_arg_overrides_defaults(self, mock_firecrawl_client):
        """Map handler: explicit arguments override defaults."""
        received_args = {}

        async def mock_map(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.map = mock_map

        defaults = FirecrawlDefaults(
            map_include_subdomains=False,
        )
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_map",
            arguments={
                "url": "https://example.com",
                "includeSubdomains": True,
            },
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert received_args["include_subdomains"] is True

    @pytest.mark.asyncio
    async def test_crawl_uses_default_include_subdomains(self, mock_firecrawl_client):
        """Crawl handler uses configured default includeSubdomains."""
        received_args = {}

        async def mock_crawl(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.crawl = mock_crawl

        defaults = FirecrawlDefaults(crawl_allow_backward_links=True)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "allow_backward_links" in received_args
        assert received_args["allow_backward_links"] is True

    @pytest.mark.asyncio
    async def test_crawl_uses_default_allow_external_links(self, mock_firecrawl_client):
        """Crawl handler uses configured default allowExternalLinks."""
        received_args = {}

        async def mock_crawl(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.crawl = mock_crawl

        defaults = FirecrawlDefaults(crawl_allow_external_links=True)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "allow_external_links" in received_args
        assert received_args["allow_external_links"] is True

    @pytest.mark.asyncio
    async def test_crawl_arg_overrides_defaults(self, mock_firecrawl_client):
        """Crawl handler: explicit arguments override defaults."""
        received_args = {}

        async def mock_crawl(url, **kwargs):
            received_args.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.crawl = mock_crawl

        defaults = FirecrawlDefaults(
            crawl_allow_backward_links=False,
            crawl_allow_external_links=False,
        )
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_crawl",
            arguments={
                "url": "https://example.com",
                "allowBackwardLinks": True,
                "allowExternalLinks": True,
            },
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert received_args["allow_backward_links"] is True
        assert received_args["allow_external_links"] is True

    def test_firecrawl_defaults_all_fields(self):
        """FirecrawlDefaults has all expected fields with correct defaults."""
        defaults = FirecrawlDefaults()
        assert defaults.scrape_formats == ["markdown"]
        assert defaults.scrape_only_main_content is True
        assert defaults.scrape_wait_for is None
        assert defaults.scrape_include_tags is None
        assert defaults.scrape_exclude_tags is None
        assert defaults.scrape_remove_base64_images is True
        assert defaults.search_limit == 5
        assert defaults.search_sources == ["web"]
        assert defaults.search_categories is None
        assert defaults.search_lang == "en"
        assert defaults.search_country is None
        assert defaults.search_location is None
        assert defaults.search_tbs is None
        assert defaults.search_include_domains is None
        assert defaults.search_exclude_domains is None
        assert defaults.search_ignore_invalid_urls is True
        assert defaults.search_only_main_content is True
        assert defaults.map_limit == 5
        assert defaults.map_include_subdomains is False
        assert defaults.crawl_limit == 5
        assert defaults.crawl_allow_backward_links is False
        assert defaults.crawl_allow_external_links is False

    @pytest.mark.asyncio
    async def test_search_uses_default_only_main_content(self, mock_firecrawl_client):
        """Search handler uses configured default onlyMainContent in scrapeOptions."""
        received_args = {}

        async def mock_search(query, **kwargs):
            received_args.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search

        defaults = FirecrawlDefaults(search_only_main_content=True)
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client, firecrawl_defaults=defaults)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test"},
            reason="test",
            risk=ToolRisk.LOW,
        )

        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert "scrape_options" in received_args
        assert received_args["scrape_options"]["onlyMainContent"] is True


class TestOptimizedDefaultsWiring:
    """Verify optimized defaults flow correctly: domain → broker → handler → client."""

    def test_optimized_defaults_values(self):
        """Verify the optimized default values are set correctly."""
        defaults = FirecrawlDefaults()
        # Token-efficient: markdown only, no base64 images
        assert defaults.scrape_formats == ["markdown"]
        assert defaults.scrape_only_main_content is True
        assert defaults.scrape_remove_base64_images is True
        # Balanced search: 5 results, web source, main content only
        assert defaults.search_limit == 5
        assert defaults.search_sources == ["web"]
        assert defaults.search_only_main_content is True
        assert defaults.search_ignore_invalid_urls is True
        # Map/crawl: 5 pages, no external expansion
        assert defaults.map_limit == 5
        assert defaults.crawl_limit == 5
        assert defaults.crawl_allow_backward_links is False
        assert defaults.crawl_allow_external_links is False

    @pytest.mark.asyncio
    async def test_scrape_passes_remove_base64_default(self, mock_firecrawl_client):
        """Scrape handler applies remove_base64_images=True from defaults."""
        received = {}

        async def mock_scrape(url, **kwargs):
            received.update(kwargs)
            return {"url": url}

        mock_firecrawl_client.scrape = mock_scrape
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)  # uses default FirecrawlDefaults
        request = ToolRequest(
            tool="firecrawl_scrape",
            arguments={"url": "https://example.com"},
            reason="test",
            risk=ToolRisk.LOW,
        )
        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert received.get("remove_base64_images") is True

    @pytest.mark.asyncio
    async def test_search_passes_optimized_defaults(self, mock_firecrawl_client):
        """Search handler passes all optimized defaults to client."""
        received = {}

        async def mock_search(query, **kwargs):
            received.update(kwargs)
            received["query"] = query
            return {"query": query}

        mock_firecrawl_client.search = mock_search
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)  # uses default FirecrawlDefaults
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test query"},
            reason="test",
            risk=ToolRisk.LOW,
        )
        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        assert received["limit"] == 5
        assert received["lang"] == "en"
        assert received["sources"] == ["web"]
        assert received["ignore_invalid_urls"] is True
        # scrape_options should include onlyMainContent and formats
        scrape_opts = received.get("scrape_options", {})
        assert scrape_opts.get("onlyMainContent") is True
        assert scrape_opts.get("formats") == ["markdown"]

    @pytest.mark.asyncio
    async def test_search_explicit_args_override_defaults(self, mock_firecrawl_client):
        """Explicit arguments in the tool request override defaults."""
        received = {}

        async def mock_search(query, **kwargs):
            received.update(kwargs)
            return {"query": query}

        mock_firecrawl_client.search = mock_search
        broker = ToolBroker(firecrawl_client=mock_firecrawl_client)
        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "test", "limit": 2, "lang": "es"},
            reason="test",
            risk=ToolRisk.LOW,
        )
        await broker.execute(request, permission_mode=PermissionMode.YOLO)

        # Explicit values override defaults
        assert received["limit"] == 2
        assert received["lang"] == "es"
