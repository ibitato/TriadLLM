"""Tests for FirecrawlClient class."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from triadllm.firecrawl import FirecrawlClient, FirecrawlError


@pytest.fixture(autouse=True)
def clear_env():
    old = os.environ.pop("FIRECRAWL_API_KEY", None)
    yield
    if old is not None:
        os.environ["FIRECRAWL_API_KEY"] = old
    else:
        os.environ.pop("FIRECRAWL_API_KEY", None)


class TestFirecrawlClient:
    def test_client_requires_api_key(self):
        with pytest.raises(FirecrawlError, match="API key is required"):
            FirecrawlClient(api_key=None)

    def test_client_sets_auth_header(self):
        client = FirecrawlClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    @pytest.mark.asyncio
    async def test_scrape_sends_correct_payload(self):
        client = FirecrawlClient(api_key="test-key")
        mock_response = httpx.Response(
            200,
            json={"success": True, "data": {"markdown": "hello"}},
        )
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            result = await client.scrape(url="https://example.com", formats=["markdown"])

            mock_http.post.assert_called_once()
            call_kwargs = mock_http.post.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["url"] == "https://example.com"
            assert payload["formats"] == ["markdown"]
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_error_response_raises_firecrawl_error(self):
        client = FirecrawlClient(api_key="test-key")
        mock_response = httpx.Response(
            403,
            json={"error": "Forbidden"},
        )
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            with pytest.raises(FirecrawlError) as exc_info:
                await client.scrape(url="https://example.com")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_timeout_raises_firecrawl_error(self):
        client = FirecrawlClient(api_key="test-key")
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_ensure.return_value = mock_http

            with pytest.raises(FirecrawlError) as exc_info:
                await client.scrape(url="https://example.com")
            assert exc_info.value.status_code == 408

    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        client = FirecrawlClient(api_key="test-key")
        rate_limited = httpx.Response(429, json={"error": "rate limited"})
        success = httpx.Response(200, json={"success": True})

        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=[rate_limited, rate_limited, success])
            mock_ensure.return_value = mock_http

            with patch("triadllm.firecrawl.asyncio.sleep", new_callable=AsyncMock):
                result = await client.scrape(url="https://example.com")

            assert result["success"] is True
            assert mock_http.post.call_count == 3
