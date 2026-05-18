"""Firecrawl MCP Client - Autocontenido para TriadLLM.

Este módulo provee un cliente HTTP directo a la API de Firecrawl,
eliminando la necesidad de instalar el binario firecrawl-mcp externo.
Solo requiere la API key en la variable de entorno FIRECRAWL_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FirecrawlMCPError(Exception):
    """Error base para operaciones Firecrawl MCP."""

    def __init__(self, message: str, status_code: int | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class FirecrawlMCPClient:
    """Cliente autocontenido para la API de Firecrawl.

    Implementa las operaciones principales del MCP de Firecrawl:
    - scrape: Extraer contenido de una URL
    - search: Búsqueda web
    - map: Mapear estructura de un sitio
    - crawl: Crawlear un sitio completo

    No requiere el binario firecrawl-mcp. Usa la API REST de Firecrawl directamente.
    """

    BASE_URL = "https://api.firecrawl.dev/v0"
    DEFAULT_TIMEOUT = 60.0

    def __init__(self, api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Inicializar cliente Firecrawl MCP.

        Args:
            api_key: API key de Firecrawl. Si no se provee, se busca en FIRECRAWL_API_KEY.
            timeout: Timeout en segundos para peticiones HTTP.

        Raises:
            FirecrawlMCPError: Si no se encuentra API key.
        """
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise FirecrawlMCPError(
                "Firecrawl API key is required. Set FIRECRAWL_API_KEY environment variable.",
                status_code=401,
            )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "FirecrawlMCPClient":
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
        wait_for: float | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Ejecutar scrape de una URL.

        Args:
            url: URL a scrappear.
            formats: Formatos de salida (markdown, html, etc.).
            wait_for: Tiempo de espera para JavaScript (ms).
            timeout: Timeout específico para esta operación.
            **kwargs: Argumentos adicionales pasados a la API.

        Returns:
            Resultado del scrape en formato dict.

        Raises:
            FirecrawlMCPError: Si la operación falla.
        """
        payload: dict[str, Any] = {"url": url}
        if formats:
            payload["formats"] = formats
        if wait_for:
            payload["waitFor"] = wait_for
        # Merge additional kwargs
        payload.update(kwargs)

        return await self._post("/scrape", payload, timeout=timeout)

    async def search(
        self,
        query: str,
        limit: int | None = None,
        page_options: dict[str, Any] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Ejecutar búsqueda web.

        Args:
            query: Consulta de búsqueda.
            limit: Número máximo de resultados.
            page_options: Opciones de paginación.
            timeout: Timeout específico para esta operación.
            **kwargs: Argumentos adicionales.

        Returns:
            Resultados de búsqueda en formato dict.

        Raises:
            FirecrawlMCPError: Si la operación falla.
        """
        payload: dict[str, Any] = {"query": query}
        if limit:
            payload["limit"] = limit
        if page_options:
            payload["pageOptions"] = page_options
        payload.update(kwargs)

        return await self._post("/search", payload, timeout=timeout)

    async def map(
        self,
        url: str,
        search: str | None = None,
        limit: int | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Mapear la estructura de un sitio web.

        Args:
            url: URL base para el mapeo.
            search: Término de búsqueda para filtrar URLs.
            limit: Número máximo de URLs a mapear.
            timeout: Timeout específico para esta operación.
            **kwargs: Argumentos adicionales.

        Returns:
            Mapa del sitio en formato dict.

        Raises:
            FirecrawlMCPError: Si la operación falla.
        """
        payload: dict[str, Any] = {"url": url}
        if search:
            payload["search"] = search
        if limit:
            payload["limit"] = limit
        payload.update(kwargs)

        return await self._post("/map", payload, timeout=timeout)

    async def crawl(
        self,
        url: str,
        max_pages: int | None = None,
        include_subdomains: bool = False,
        allow_external: bool = False,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Crawlear un sitio web completo.

        Args:
            url: URL base para el crawl.
            max_pages: Número máximo de páginas a crawlear.
            include_subdomains: Incluir subdominios.
            allow_external: Permitir enlaces externos.
            timeout: Timeout específico para esta operación.
            **kwargs: Argumentos adicionales.

        Returns:
            Resultados del crawl en formato dict.

        Raises:
            FirecrawlMCPError: Si la operación falla.
        """
        payload: dict[str, Any] = {
            "url": url,
            "includeSubdomains": include_subdomains,
            "allowExternal": allow_external,
        }
        if max_pages:
            payload["limit"] = max_pages
        payload.update(kwargs)

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
            FirecrawlMCPError: Si la petición falla.
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
                raise FirecrawlMCPError(
                    f"Firecrawl API error: {error_msg}",
                    status_code=response.status_code,
                    details={"endpoint": endpoint, "response": error_body},
                )

            return self._safe_parse_json(response.text)

        except httpx.TimeoutException as e:
            logger.error("firecrawl_api_timeout", extra={"endpoint": endpoint, "error": str(e)})
            raise FirecrawlMCPError(
                f"Firecrawl API request timed out: {e}",
                status_code=408,
                details={"endpoint": endpoint},
            ) from e
        except httpx.ConnectError as e:
            logger.error("firecrawl_api_connect_error", extra={"endpoint": endpoint, "error": str(e)})
            raise FirecrawlMCPError(
                f"Failed to connect to Firecrawl API: {e}",
                status_code=502,
                details={"endpoint": endpoint},
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error("firecrawl_api_http_error", extra={"endpoint": endpoint, "error": str(e)})
            raise FirecrawlMCPError(
                f"Firecrawl API HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                status_code=e.response.status_code,
                details={"endpoint": endpoint},
            ) from e
        except FirecrawlMCPError:
            # Re-raise FirecrawlMCPError without modification
            raise
        except Exception as e:
            logger.error("firecrawl_api_error", extra={"endpoint": endpoint, "error": str(e)})
            raise FirecrawlMCPError(
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
