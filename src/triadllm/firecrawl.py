"""Firecrawl Client - Cliente REST para la API Firecrawl v2.

Este módulo provee un cliente HTTP directo a la API de Firecrawl v2,
eliminando la necesidad de instalar el binario firecrawl-mcp externo.
Solo requiere la API key en la variable de entorno FIRECRAWL_API_KEY.

Usa exclusivamete endpoints v2 (no deprecated).
"""

from __future__ import annotations

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

    async def __aenter__(self) -> "FirecrawlClient":
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
        """Ejecutar scrape de una URL.

        Args:
            url: URL a scrappear.
            formats: Formatos de salida (markdown, html, rawHtml, links, pdf).
            only_main_content: Solo contenido principal (excluye header, footer, etc.).
            wait_for: Tiempo de espera para JavaScript (ms).
            include_tags: Tags HTML a incluir.
            exclude_tags: Tags HTML a excluir.
            remove_base64_images: Remover imágenes base64.
            timeout: Timeout específico para esta operación.

        Returns:
            Resultado del scrape en formato dict.

        Raises:
            FirecrawlError: Si la operación falla.
        """
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
        sources: list[str] | None = None,
        categories: list[str] | None = None,
        country: str | None = None,
        location: str | None = None,
        tbs: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        ignore_invalid_urls: bool | None = None,
        scrape_options: dict[str, Any] | None = None,
        page_options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Ejecutar búsqueda web.

        Args:
            query: Consulta de búsqueda.
            limit: Número máximo de resultados.
            sources: Tipos de resultados (web, news, images).
            categories: Categorías (github, research, pdf).
            country: Código ISO de país.
            location: Ubicación (ej: "San Francisco,California,United States").
            tbs: Filtro temporal (ej: "qdr:m" para último mes).
            include_domains: Dominios permitidos.
            exclude_domains: Dominios excluidos.
            ignore_invalid_urls: Ignorar URLs inválidos.
            scrape_options: Opciones de scraping (formats, onlyMainContent, etc.).
            page_options: Opciones de página (fetchContent, onlyMainContent, etc.).
            timeout: Timeout específico para esta operación.

        Returns:
            Resultados de búsqueda en formato dict.

        Raises:
            FirecrawlError: Si la operación falla.
        """
        payload: dict[str, Any] = {"query": query}
        if limit is not None:
            payload["limit"] = limit
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
        if page_options:
            payload["pageOptions"] = page_options

        return await self._post("/search", payload, timeout=timeout)

    async def map(
        self,
        url: str,
        search: str | None = None,
        limit: int | None = None,
        include_subdomains: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Mapear la estructura de un sitio web.

        Args:
            url: URL base para el mapeo.
            search: Término de búsqueda para filtrar URLs.
            limit: Número máximo de URLs a mapear.
            include_subdomains: Incluir subdominios.
            timeout: Timeout específico para esta operación.

        Returns:
            Mapa del sitio en formato dict.

        Raises:
            FirecrawlError: Si la operación falla.
        """
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
        allow_subdomains: bool = False,
        allow_external_links: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Crawlear un sitio web completo.

        Args:
            url: URL base para el crawl.
            limit: Número máximo de páginas a crawlear.
            allow_subdomains: Permitir subdominios.
            allow_external_links: Permitir enlaces externos.
            timeout: Timeout específico para esta operación.

        Returns:
            Resultados del crawl en formato dict.

        Raises:
            FirecrawlError: Si la operación falla.
        """
        payload: dict[str, Any] = {
            "url": url,
            "allowSubdomains": allow_subdomains,
            "allowExternalLinks": allow_external_links,
        }
        if limit is not None:
            payload["limit"] = limit

        return await self._post("/crawl", payload, timeout=timeout)

    async def _post(self, endpoint: str, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        """Ejecutar petición POST a la API de Firecrawl.

        Args:
            endpoint: Endpoint de la API (ej: /scrape).
            payload: Carga útil en formato dict.
            timeout: Timeout específico. Usa self.timeout si no se provee.

        Returns:
            Respuesta de la API en formato dict.

        Raises:
            FirecrawlError: Si la petición falla.
        """
        client = await self._ensure_client()
        actual_timeout = timeout if timeout is not None else self.timeout

        url = f"{self.BASE_URL}{endpoint}"

        logger.debug(
            "firecrawl_api_request",
            extra={
                "endpoint": endpoint,
                "url": url,
                "payload_preview": json.dumps(payload)[:500],
            },
        )

        try:
            response = await client.post(
                url,
                json=payload,
                timeout=actual_timeout,
            )

            logger.debug(
                "firecrawl_api_response",
                extra={
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "response_preview": (response.text[:500] if response.text else "empty"),
                },
            )

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
            # Re-raise FirecrawlError without modification
            raise
        except Exception as e:
            logger.error("firecrawl_api_error", extra={"endpoint": endpoint, "error": str(e)})
            raise FirecrawlError(
                f"Firecrawl API error: {e}",
                details={"endpoint": endpoint},
            ) from e

    def _safe_parse_json(self, text: str) -> dict[str, Any]:
        """Parsear JSON de forma segura."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("firecrawl_invalid_json_response", extra={"text_preview": text[:500]})
            return {"raw": text}
