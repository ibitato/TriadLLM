"""Smoke test: Real Firecrawl API call for 'Qwen 3 LLM DGX Spark'.

This test uses the actual FIRECRAWL_API_KEY from the environment.
Run with: uv run pytest tests/test_smoke_firecrawl_real.py -v -s
"""

from __future__ import annotations

import json
import os

import pytest

from triadllm.domain import FirecrawlDefaults, PermissionMode, ToolRequest, ToolRisk
from triadllm.firecrawl import FirecrawlClient
from triadllm.tools import ToolBroker

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRECRAWL_API_KEY"),
    reason="FIRECRAWL_API_KEY not set",
)


class TestRealFirecrawlSearch:
    """Tests using the real Firecrawl API."""

    @pytest.mark.asyncio
    async def test_real_search_qwen_dgx_spark(self) -> None:
        """Real search: Qwen 3 LLM + DGX Spark — verifies API connectivity and response structure."""
        client = FirecrawlClient()

        try:
            result = await client.search(
                query="Qwen 3 LLM model DGX Spark NVIDIA",
                limit=3,
                lang="es",
                scrape_options={"formats": ["markdown"], "onlyMainContent": True},
            )
        finally:
            await client.close()

        # Verify response structure
        assert isinstance(result, dict)
        assert result.get("success") is True or "data" in result

        # Extract results - API may return list directly or nested in 'data'
        data = result.get("data", result.get("results", []))
        if isinstance(data, dict):
            # Some responses nest results differently
            data = data.get("results", data.get("data", [data]))
        if not isinstance(data, list):
            data = [data]

        print(f"\n{'=' * 60}")
        print("FIRECRAWL SEARCH RESULTS: 'Qwen 3 LLM model DGX Spark NVIDIA'")
        print(f"{'=' * 60}")
        print(f"Raw response keys: {list(result.keys())}")
        print(f"Results count: {len(data)}")
        for i, item in enumerate(data[:5], 1):
            if isinstance(item, dict):
                print(f"\n--- Result {i} ---")
                print(f"  Title: {item.get('title', 'N/A')}")
                print(f"  URL: {item.get('url', 'N/A')}")
                desc = item.get("description", item.get("content", item.get("markdown", "")))
                if desc:
                    print(f"  Content preview: {str(desc)[:200]}...")

        assert len(data) > 0 or result.get("success") is True, f"Unexpected response: {json.dumps(result)[:500]}"

    @pytest.mark.asyncio
    async def test_real_search_via_tool_broker(self) -> None:
        """Real search through ToolBroker — simulates exactly what the CLI does."""
        client = FirecrawlClient()
        defaults = FirecrawlDefaults(search_limit=3, search_lang="es")
        broker = ToolBroker(firecrawl_client=client, firecrawl_defaults=defaults)

        request = ToolRequest(
            tool="firecrawl_search",
            arguments={"query": "Qwen3 235B modelo LLM opinión DGX Spark NVIDIA rendimiento"},
            reason="Buscar información sobre Qwen 3 y DGX Spark",
            risk=ToolRisk.LOW,
        )

        result = await broker.execute(request, permission_mode=PermissionMode.YOLO)
        await client.close()

        assert result.success is True, f"Search failed: {result.error}"
        assert result.tool == "firecrawl_search"

        output = json.loads(result.output)
        data = output.get("data", [])
        if isinstance(data, dict):
            data = [data]

        print(f"\n{'=' * 60}")
        print("TOOL BROKER SEARCH (como lo haría la CLI)")
        print(f"{'=' * 60}")
        print(f"Success: {result.success}")
        print(f"Output keys: {list(output.keys()) if isinstance(output, dict) else type(output).__name__}")
        print(f"Data type: {type(data).__name__}, items: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, list):
            for i, item in enumerate(data[:5], 1):
                print(f"\n--- Result {i} ---")
                if isinstance(item, dict):
                    print(f"  Title: {item.get('title', 'N/A')}")
                    print(f"  URL: {item.get('url', 'N/A')}")
                    content = item.get("content", item.get("description", item.get("markdown", "")))
                    if content:
                        print(f"  Content preview: {str(content)[:300]}")
                else:
                    print(f"  Value: {str(item)[:200]}")

        # Basic assertion: search succeeded and returned something
        assert result.output, "Empty output from search"

    @pytest.mark.asyncio
    async def test_real_scrape_nvidia_dgx(self) -> None:
        """Real scrape of NVIDIA DGX Spark page — verifies scrape endpoint works."""
        client = FirecrawlClient()

        try:
            result = await client.scrape(
                url="https://www.nvidia.com/en-us/products/dgx/spark/",
                formats=["markdown"],
                only_main_content=True,
            )
        finally:
            await client.close()

        assert isinstance(result, dict)

        # Check we got content
        data = result.get("data", result)
        content = data.get("markdown", data.get("content", ""))

        print(f"\n{'=' * 60}")
        print("SCRAPE: nvidia.com/dgx/spark")
        print(f"{'=' * 60}")
        print(f"Content length: {len(content)} chars")
        if content:
            print(f"Preview: {content[:500]}")

        assert len(content) > 100, "Scrape returned too little content"
