"""Tests for Firecrawl MCP client."""

from __future__ import annotations

import json
import os

import httpx
import pytest

from triadllm.mcp import FirecrawlMCPClient, FirecrawlMCPError


@pytest.fixture
def mock_api_key():
    """Provide a mock API key for testing."""
    return "test-api-key-12345"


@pytest.fixture(autouse=True)
def clear_env_var():
    """Clear FIRECRAWL_API_KEY before each test."""
    if "FIRECRAWL_API_KEY" in os.environ:
        del os.environ["FIRECRAWL_API_KEY"]
    yield
    if "FIRECRAWL_API_KEY" in os.environ:
        del os.environ["FIRECRAWL_API_KEY"]


class TestFirecrawlMCPClientInit:
    """Tests for client initialization."""

    def test_init_with_api_key(self, mock_api_key):
        """Client initializes with provided API key."""
        client = FirecrawlMCPClient(api_key=mock_api_key, timeout=30.0)
        assert client.api_key == mock_api_key
        assert client.timeout == 30.0
        assert client._client is None

    def test_init_with_default_timeout(self, mock_api_key):
        """Client uses default timeout when not specified."""
        client = FirecrawlMCPClient(api_key=mock_api_key)
        assert client.timeout == FirecrawlMCPClient.DEFAULT_TIMEOUT

    def test_init_from_env_var(self, mock_api_key, monkeypatch):
        """Client reads API key from environment variable."""
        monkeypatch.setenv("FIRECRAWL_API_KEY", mock_api_key)
        client = FirecrawlMCPClient()
        assert client.api_key == mock_api_key

    def test_init_fails_without_api_key(self):
        """Client raises error when no API key is provided or in environment."""
        with pytest.raises(FirecrawlMCPError) as exc_info:
            FirecrawlMCPClient()
        assert "FIRECRAWL_API_KEY" in str(exc_info.value)
        assert exc_info.value.status_code == 401


class TestFirecrawlMCPClientScrape:
    """Tests for scrape method."""

    @pytest.mark.asyncio
    async def test_scrape_success(self, mock_api_key):
        """Scrape returns successful result."""
        mock_response = {"success": True, "data": {"url": "https://example.com", "content": "test"}}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.scrape("https://example.com")
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_scrape_with_formats(self, mock_api_key):
        """Scrape with formats parameter."""
        mock_response = {"success": True, "data": {"url": "https://example.com", "format": "markdown"}}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.scrape("https://example.com", formats=["markdown"])
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_scrape_api_error(self, mock_api_key):
        """Scrape handles API errors."""
        error_response = {"error": "Invalid URL"}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(400, json=error_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        with pytest.raises(FirecrawlMCPError) as exc_info:
            await client.scrape("invalid-url")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_scrape_auth_error(self, mock_api_key):
        """Scrape handles authentication errors."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": "Unauthorized"})
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        with pytest.raises(FirecrawlMCPError) as exc_info:
            await client.scrape("https://example.com")
        assert exc_info.value.status_code == 401


class TestFirecrawlMCPClientSearch:
    """Tests for search method."""

    @pytest.mark.asyncio
    async def test_search_success(self, mock_api_key):
        """Search returns successful result."""
        mock_response = {
            "success": True,
            "data": [{"title": "Test", "url": "https://test.com"}]
        }
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.search("test query")
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_search_with_limit(self, mock_api_key):
        """Search with limit parameter."""
        mock_response = {"success": True, "data": []}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.search("test query", limit=5)
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_search_missing_query(self, mock_api_key):
        """Search requires query parameter."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={})
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.search("")
        assert result == {}


class TestFirecrawlMCPClientMap:
    """Tests for map method."""

    @pytest.mark.asyncio
    async def test_map_success(self, mock_api_key):
        """Map returns successful result."""
        mock_response = {
            "success": True,
            "data": {"urls": ["https://example.com/page1", "https://example.com/page2"]}
        }
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.map("https://example.com")
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_map_with_search(self, mock_api_key):
        """Map with search parameter."""
        mock_response = {"success": True, "data": {"urls": []}}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.map("https://example.com", search="docs")
        assert result == mock_response


class TestFirecrawlMCPClientCrawl:
    """Tests for crawl method."""

    @pytest.mark.asyncio
    async def test_crawl_success(self, mock_api_key):
        """Crawl returns successful result."""
        mock_response = {
            "success": True,
            "data": {"pages": [{"url": "https://example.com"}]}
        }
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.crawl("https://example.com")
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_crawl_with_options(self, mock_api_key):
        """Crawl with all options."""
        mock_response = {"success": True, "data": {"pages": []}}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.crawl(
            "https://example.com",
            max_pages=10,
            include_subdomains=True,
            allow_external=False,
        )
        assert result == mock_response


class TestFirecrawlMCPClientContextManager:
    """Tests for context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_api_key):
        """Client works as async context manager."""
        mock_response = {"success": True}
        
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response)
        )
        async with FirecrawlMCPClient(api_key=mock_api_key) as client:
            client._client = httpx.AsyncClient(transport=mock_transport)
            result = await client.scrape("https://example.com")
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_close(self, mock_api_key):
        """Client can be closed manually."""
        client = FirecrawlMCPClient(api_key=mock_api_key)
        await client._ensure_client()
        assert client._client is not None
        await client.close()
        assert client._client is None


class TestFirecrawlMCPClientErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_timeout_error(self, mock_api_key):
        """Handles timeout errors."""
        # Mock transport that raises TimeoutException
        async def handler(request):
            raise httpx.TimeoutException("Request timed out")
        
        mock_transport = httpx.MockTransport(handler)
        client = FirecrawlMCPClient(api_key=mock_api_key, timeout=0.01)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        with pytest.raises(FirecrawlMCPError) as exc_info:
            await client.scrape("https://example.com")
        assert exc_info.value.status_code == 408

    @pytest.mark.asyncio
    async def test_connect_error(self, mock_api_key):
        """Handles connection errors."""
        # Mock transport that raises ConnectError
        async def handler(request):
            raise httpx.ConnectError("Connection failed")
        
        mock_transport = httpx.MockTransport(handler)
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        with pytest.raises(FirecrawlMCPError) as exc_info:
            await client.scrape("https://example.com")
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, mock_api_key):
        """Handles invalid JSON responses."""
        mock_transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="not json")
        )
        client = FirecrawlMCPClient(api_key=mock_api_key)
        client._client = httpx.AsyncClient(transport=mock_transport)
        
        result = await client.scrape("https://example.com")
        assert "raw" in result
        assert result["raw"] == "not json"
