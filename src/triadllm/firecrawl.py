"""Firecrawl Client - Cliente REST para la API Firecrawl v2.

Este módulo provee un cliente HTTP directo a la API de Firecrawl v2,
eliminando la necesidad de instalar el binario firecrawl-mcp externo.
Solo requiere la API key en la variable de entorno FIRECRAWL_API_KEY.

Usa exclusivamete endpoints v2 (no deprecated).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FirecrawlError(Exception):
    """Error base para operaciones Firecrawl."""

    def __init__(self, message: str, status_code: int | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class FirecrawlClient:
    """Cliente para la API Firecrawl v2.

    Implementa las operaciones principales:
    - scrape: Extraer contenido de una URL
    - search: Búsqueda web
    - map: Mapear estructura de un sitio
    - crawl: Crawlear un sitio completo

    Usa la API REST de Firecrawl v2 directamente (https://api.firecrawl.dev/v2).
    """

    BASE_URL = "https://api.firecrawl.dev/v2"
    DEFAULT_TIMEOUT = 120.0  # 2 minutes
    MAX_RETRIES = 3

    def __init__(self, api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Inicializar cliente Firecrawl.

        Args:
            api_key: API key de Firecrawl. Si no se provee, se busca en FIRECRAWL_API_KEY.
            timeout: Timeout en segundos para peticiones HTTP.

        Raises:
            FirecrawlError: Si no se encuentra API key.
        """
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise FirecrawlError(
                "Firecrawl API key is required. Set FIRECRAWL_API_KEY environment variable.",
                status_code=401,
            )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> FirecrawlClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: object | None, exc_val: object | None, exc_tb: object | None) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Asegurar que el cliente HTTP está inicializado."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Cerrar el cliente HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def scrape(
        self,
        url: str,
        formats: list[str] | None = None,
        only_main_content: bool | None = None,
        wait_for: float | None = None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        remove_base64_images: bool | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ejecutar scrape de una URL."""
        payload: dict[str, Any] = {"url": url}
        if formats:
            payload["formats"] = formats
        if only_main_content is not None:
            payload["onlyMainContent"] = only_main_content
        if wait_for:
            payload["waitFor"] = wait_for
        if include_tags:
            payload["includeTags"] = include_tags
        if exclude_tags:
            payload["excludeTags"] = exclude_tags
        if remove_base64_images is not None:
            payload["removeBase64Images"] = remove_base64_images

        return await self._post("/scrape", payload, timeout=timeout)

    async def search(
        self,
        query: str,
        limit: int | None = None,
        lang: str | None = None,
        sources: list[str] | None = None,
        categories: list[str] | None = None,
        country: str | None = None,
        location: str | None = None,
        tbs: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        ignore_invalid_urls: bool | None = None,
        scrape_options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ejecutar búsqueda web."""
        payload: dict[str, Any] = {"query": query}
        if limit is not None:
            payload["limit"] = limit
        if lang is not None:
            payload["lang"] = lang
        if sources:
            payload["sources"] = sources
        if categories:
            payload["categories"] = categories
        if country:
            payload["country"] = country
        if location:
            payload["location"] = location
        if tbs:
            payload["tbs"] = tbs
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains
        if ignore_invalid_urls is not None:
            payload["ignoreInvalidURLs"] = ignore_invalid_urls
        if scrape_options:
            payload["scrapeOptions"] = scrape_options

        return await self._post("/search", payload, timeout=timeout)

    async def map(
        self,
        url: str,
        search: str | None = None,
        limit: int | None = None,
        include_subdomains: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Mapear la estructura de un sitio web."""
        payload: dict[str, Any] = {"url": url}
        if search:
            payload["search"] = search
        if limit is not None:
            payload["limit"] = limit
        if include_subdomains:
            payload["includeSubdomains"] = include_subdomains

        return await self._post("/map", payload, timeout=timeout)

    async def crawl(
        self,
        url: str,
        limit: int | None = None,
        allow_backward_links: bool = False,
        allow_external_links: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Crawlear un sitio web completo."""
        payload: dict[str, Any] = {
            "url": url,
            "allowBackwardLinks": allow_backward_links,
            "allowExternalLinks": allow_external_links,
        }
        if limit is not None:
            payload["limit"] = limit

        return await self._post("/crawl", payload, timeout=timeout)

    async def _post(self, endpoint: str, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        """Ejecutar petición POST con retry en 429."""
        client = await self._ensure_client()
        actual_timeout = timeout if timeout is not None else self.timeout
        url = f"{self.BASE_URL}{endpoint}"

        logger.debug(
            "firecrawl_api_request",
            extra={"endpoint": endpoint, "url": url, "payload_preview": json.dumps(payload)[:500]},
        )

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.post(url, json=payload, timeout=actual_timeout)

                logger.debug(
                    "firecrawl_api_response",
                    extra={
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "response_preview": (response.text[:500] if response.text else "empty"),
                    },
                )

                if response.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "firecrawl_rate_limited",
                        extra={"endpoint": endpoint, "attempt": attempt + 1, "wait_seconds": wait},
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 400:
                    error_body = self._safe_parse_json(response.text)
                    error_msg = error_body.get("error", error_body.get("message", response.text[:200]))
                    raise FirecrawlError(
                        f"Firecrawl API error: {error_msg}",
                        status_code=response.status_code,
                        details={"endpoint": endpoint, "response": error_body},
                    )

                return self._safe_parse_json(response.text)

            except httpx.TimeoutException as e:
                logger.error("firecrawl_api_timeout", extra={"endpoint": endpoint, "error": str(e)})
                raise FirecrawlError(
                    f"Firecrawl API request timed out: {e}",
                    status_code=408,
                    details={"endpoint": endpoint},
                ) from e
            except httpx.ConnectError as e:
                logger.error("firecrawl_api_connect_error", extra={"endpoint": endpoint, "error": str(e)})
                raise FirecrawlError(
                    f"Failed to connect to Firecrawl API: {e}",
                    status_code=502,
                    details={"endpoint": endpoint},
                ) from e
            except httpx.HTTPStatusError as e:
                logger.error("firecrawl_api_http_error", extra={"endpoint": endpoint, "error": str(e)})
                raise FirecrawlError(
                    f"Firecrawl API HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                    status_code=e.response.status_code,
                    details={"endpoint": endpoint},
                ) from e
            except FirecrawlError:
                raise
            except Exception as e:
                logger.error("firecrawl_api_error", extra={"endpoint": endpoint, "error": str(e)})
                raise FirecrawlError(
                    f"Firecrawl API error: {e}",
                    details={"endpoint": endpoint},
                ) from e

        # All retries exhausted (only reached for 429s)
        raise FirecrawlError(
            f"Firecrawl API rate limited after {self.MAX_RETRIES} retries",
            status_code=429,
            details={"endpoint": endpoint},
        )

    def _safe_parse_json(self, text: str) -> dict[str, Any]:
        """Parsear JSON de forma segura."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("firecrawl_invalid_json_response", extra={"text_preview": text[:500]})
            return {"raw": text}
