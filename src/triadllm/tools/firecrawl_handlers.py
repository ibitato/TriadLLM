from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from triadllm.domain import FirecrawlDefaults, ToolResult
from triadllm.tools.sanitizers import _sanitize_firecrawl_result

if TYPE_CHECKING:
    from triadllm.firecrawl import FirecrawlClient


class FirecrawlHandlersMixin:
    """Mixin providing Firecrawl tool handler methods for ToolBroker."""

    firecrawl_client: FirecrawlClient | None
    firecrawl_defaults: FirecrawlDefaults

    async def _tool_firecrawl_scrape(self, args: dict[str, object]) -> ToolResult:
        """Scrape a URL using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_scrape",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_scrape", success=False, error="url is required", exit_code=2)

        formats = args.get("formats", self.firecrawl_defaults.scrape_formats)
        if isinstance(formats, str):
            formats = [formats]
        elif not isinstance(formats, list):
            formats = self.firecrawl_defaults.scrape_formats

        only_main_content = args.get("onlyMainContent")
        if only_main_content is None:
            only_main_content = self.firecrawl_defaults.scrape_only_main_content

        wait_for = args.get("waitFor")
        if wait_for is not None:
            wait_for = float(wait_for)

        include_tags = args.get("includeTags")
        exclude_tags = args.get("excludeTags")
        remove_base64_images = args.get("removeBase64Images")
        if remove_base64_images is None:
            remove_base64_images = self.firecrawl_defaults.scrape_remove_base64_images

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            scrape_kwargs: dict[str, Any] = {"url": url}
            if formats:
                scrape_kwargs["formats"] = formats
            if only_main_content is not None:
                scrape_kwargs["only_main_content"] = only_main_content
            if wait_for is not None:
                scrape_kwargs["wait_for"] = wait_for
            if include_tags is not None:
                scrape_kwargs["include_tags"] = include_tags
            if exclude_tags is not None:
                scrape_kwargs["exclude_tags"] = exclude_tags
            if remove_base64_images is not None:
                scrape_kwargs["remove_base64_images"] = remove_base64_images
            if timeout is not None:
                scrape_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.scrape(**scrape_kwargs)
            sanitized_result = _sanitize_firecrawl_result(result)

            return ToolResult(
                tool="firecrawl_scrape",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"url": url},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_scrape",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"url": url},
            )

    async def _tool_firecrawl_search(self, args: dict[str, object]) -> ToolResult:
        """Search the web using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_search",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(tool="firecrawl_search", success=False, error="query is required", exit_code=2)

        limit = args.get("limit", self.firecrawl_defaults.search_limit)
        if limit is not None:
            limit = int(limit)

        # Build scrapeOptions (the correct v2 way to get content in search results)
        scrape_options = args.get("scrapeOptions")
        if scrape_options is None:
            scrape_options = {}
        elif isinstance(scrape_options, str):
            try:
                scrape_options = json.loads(scrape_options)
            except json.JSONDecodeError:
                scrape_options = {}

        if "onlyMainContent" not in scrape_options:
            scrape_options["onlyMainContent"] = self.firecrawl_defaults.search_only_main_content
        if "formats" not in scrape_options and self.firecrawl_defaults.scrape_formats:
            scrape_options["formats"] = self.firecrawl_defaults.scrape_formats

        # Collect all v2 search parameters
        sources = args.get("sources", self.firecrawl_defaults.search_sources)
        categories = args.get("categories", self.firecrawl_defaults.search_categories)
        country = args.get("country", self.firecrawl_defaults.search_country)
        location = args.get("location", self.firecrawl_defaults.search_location)
        tbs = args.get("tbs", self.firecrawl_defaults.search_tbs)
        include_domains = args.get("includeDomains", self.firecrawl_defaults.search_include_domains)
        exclude_domains = args.get("excludeDomains", self.firecrawl_defaults.search_exclude_domains)
        ignore_invalid_urls = args.get("ignoreInvalidUrls", self.firecrawl_defaults.search_ignore_invalid_urls)
        lang = args.get("lang", self.firecrawl_defaults.search_lang)

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            search_kwargs: dict[str, Any] = {"query": query}
            if limit is not None:
                search_kwargs["limit"] = limit
            if lang is not None:
                search_kwargs["lang"] = str(lang)
            if country is not None:
                search_kwargs["country"] = str(country)
            if location is not None:
                search_kwargs["location"] = str(location)
            if sources is not None:
                search_kwargs["sources"] = sources
            if categories is not None:
                search_kwargs["categories"] = categories
            if tbs is not None:
                search_kwargs["tbs"] = str(tbs)
            if include_domains is not None:
                search_kwargs["include_domains"] = include_domains
            if exclude_domains is not None:
                search_kwargs["exclude_domains"] = exclude_domains
            if ignore_invalid_urls is not None:
                search_kwargs["ignore_invalid_urls"] = ignore_invalid_urls
            if scrape_options:
                search_kwargs["scrape_options"] = scrape_options
            if timeout is not None:
                search_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.search(**search_kwargs)
            sanitized_result = _sanitize_firecrawl_result(result)

            return ToolResult(
                tool="firecrawl_search",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"query": query},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_search",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"query": query},
            )

    async def _tool_firecrawl_map(self, args: dict[str, object]) -> ToolResult:
        """Map a website using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_map",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_map", success=False, error="url is required", exit_code=2)

        search = args.get("search")
        if search is not None:
            search = str(search)

        limit = args.get("limit", self.firecrawl_defaults.map_limit)
        if limit is not None:
            limit = int(limit)

        include_subdomains = args.get("includeSubdomains")
        if include_subdomains is None:
            include_subdomains = self.firecrawl_defaults.map_include_subdomains

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            map_kwargs: dict[str, Any] = {"url": url}
            if search:
                map_kwargs["search"] = search
            if limit is not None:
                map_kwargs["limit"] = limit
            if include_subdomains is not None:
                map_kwargs["include_subdomains"] = include_subdomains
            if timeout is not None:
                map_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.map(**map_kwargs)
            sanitized_result = _sanitize_firecrawl_result(result)

            return ToolResult(
                tool="firecrawl_map",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"url": url},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_map",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"url": url},
            )

    async def _tool_firecrawl_crawl(self, args: dict[str, object]) -> ToolResult:
        """Crawl a website using Firecrawl REST API v2."""
        if self.firecrawl_client is None:
            return ToolResult(
                tool="firecrawl_crawl",
                success=False,
                error="Firecrawl is not configured. Set FIRECRAWL_API_KEY environment variable.",
                exit_code=1,
            )
        url = str(args.get("url", "")).strip()
        if not url:
            return ToolResult(tool="firecrawl_crawl", success=False, error="url is required", exit_code=2)

        limit = args.get("limit", self.firecrawl_defaults.crawl_limit)
        if limit is not None:
            limit = int(limit)

        # v2 API uses allowBackwardLinks (NOT allowSubdomains)
        allow_backward_links = args.get("allowBackwardLinks")
        if allow_backward_links is None:
            allow_backward_links = self.firecrawl_defaults.crawl_allow_backward_links

        allow_external_links = args.get("allowExternalLinks")
        if allow_external_links is None:
            allow_external_links = self.firecrawl_defaults.crawl_allow_external_links

        timeout = args.get("timeout")
        if timeout is not None:
            timeout = float(timeout)

        try:
            crawl_kwargs: dict[str, Any] = {"url": url}
            if limit is not None:
                crawl_kwargs["limit"] = limit
            if allow_backward_links is not None:
                crawl_kwargs["allow_backward_links"] = allow_backward_links
            if allow_external_links is not None:
                crawl_kwargs["allow_external_links"] = allow_external_links
            if timeout is not None:
                crawl_kwargs["timeout"] = timeout

            result = await self.firecrawl_client.crawl(**crawl_kwargs)
            sanitized_result = _sanitize_firecrawl_result(result)

            return ToolResult(
                tool="firecrawl_crawl",
                success=True,
                output=json.dumps(sanitized_result, ensure_ascii=False),
                metadata={"url": url},
            )
        except Exception as e:
            return ToolResult(
                tool="firecrawl_crawl",
                success=False,
                error=str(e),
                exit_code=1,
                metadata={"url": url},
            )
