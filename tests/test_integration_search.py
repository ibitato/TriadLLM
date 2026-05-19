"""Integration test: Full CLI flow for 'Busca sobre el modelo llm Qwen 3.6 y dame tu opinion para una DGX Spark'.

This test suite simulates the complete proposal-validation-consolidation pipeline
with Firecrawl search tool usage, verifying:
1. The processor requests firecrawl_search with the right query
2. Search results are sanitized and returned to the processor
3. The processor produces a final answer using search results
4. The validator receives both user message and processor answer
5. The orchestrator consolidates into the final response
6. All events are emitted correctly and session is persisted
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from triadllm.config import ConfigManager
from triadllm.domain import (
    AgentActionKind,
    AgentResponse,
    AgentRole,
    ConsolidatedResponse,
    FirecrawlDefaults,
    ModelInvocationResult,
    PermissionMode,
    SessionEventKind,
    ToolRequest,
    ToolRisk,
    UserSettings,
)
from triadllm.i18n import Translator
from triadllm.runtime import TriadRuntime
from triadllm.tools import ToolBroker

USER_PROMPT = "Busca sobre el modelo llm Qwen 3.6 y dame tu opinion para una DGX Spark"

# Simulated Firecrawl search results (what the API would return)
MOCK_SEARCH_RESULTS = {
    "success": True,
    "data": [
        {
            "title": "Qwen3 - 235B-A22B: A Large MoE Model",
            "url": "https://huggingface.co/Qwen/Qwen3-235B-A22B",
            "description": "Qwen3 is the latest generation of large language models from Alibaba. "
            "The flagship model Qwen3-235B uses Mixture of Experts with 235B total params, "
            "22B active. Supports 119 languages, 32K context, thinking mode.",
            "content": "Qwen3 represents a major leap in open-weight LLMs. The 235B-A22B model "
            "uses MoE architecture with only 22B active parameters per token, making it "
            "efficient for inference. It supports both thinking and non-thinking modes. "
            "Available in sizes: 0.6B, 1.7B, 4B, 8B, 14B, 30B-A3B, 32B, 235B-A22B.",
        },
        {
            "title": "NVIDIA DGX Spark - Personal AI Supercomputer",
            "url": "https://www.nvidia.com/en-us/products/dgx/spark/",
            "description": "DGX Spark is NVIDIA's desktop AI supercomputer with Grace Blackwell "
            "architecture. 128GB unified memory, 1 petaflop AI performance.",
            "content": "The NVIDIA DGX Spark brings Grace Blackwell to the desktop. "
            "Features: 128GB unified CPU+GPU memory, up to 1 PFLOPS AI performance, "
            "NVLink-C2C interconnect. Designed for running large AI models locally. "
            "Can run models up to ~200B parameters with quantization.",
        },
        {
            "title": "Running Large LLMs on DGX Spark - Community Guide",
            "url": "https://forums.developer.nvidia.com/t/dgx-spark-llm-guide/",
            "description": "Community guide on running various LLMs on DGX Spark hardware.",
            "content": "With 128GB unified memory, DGX Spark can run: Llama 3.1 70B (FP16), "
            "Qwen2.5 72B (FP16), Mixtral 8x22B (quantized). For larger models like "
            "Qwen3-235B, you'd need 4-bit quantization (GPTQ/AWQ) which brings memory "
            "requirements to ~60GB, fitting within DGX Spark's 128GB.",
        },
    ],
}

PROCESSOR_SEARCH_ANSWER = (
    "Basándome en la búsqueda realizada:\n\n"
    "**Qwen 3 (no existe '3.6' específicamente)**\n"
    "Qwen3 es la última generación de LLMs de Alibaba Cloud. El modelo flagship es "
    "Qwen3-235B-A22B que usa arquitectura Mixture of Experts (MoE) con 235B parámetros "
    "totales pero solo 22B activos por token. Soporta 119 idiomas y contexto de 32K tokens.\n\n"
    "**Para DGX Spark:**\n"
    "La DGX Spark tiene 128GB de memoria unificada y ~1 PFLOP de rendimiento AI. "
    "Qwen3-235B requeriría cuantización a 4-bit (GPTQ/AWQ) para caber en los 128GB, "
    "lo cual es factible (~60GB). Los modelos más pequeños como Qwen3-32B correrían "
    "cómodamente en FP16.\n\n"
    "**Mi opinión:** Es una combinación viable. DGX Spark puede ejecutar Qwen3-235B "
    "cuantizado o Qwen3-32B en precisión completa. Para uso profesional local, es una "
    "opción sólida."
)

VALIDATOR_ANSWER = (
    "La respuesta del procesador es correcta en lo esencial:\n"
    "- Correcto: No existe 'Qwen 3.6', la versión actual es Qwen3 con variantes por tamaño.\n"
    "- Correcto: DGX Spark tiene 128GB y puede ejecutar modelos grandes con cuantización.\n"
    "- Correcto: Qwen3-235B necesitaría 4-bit quant para caber.\n"
    "- Nota: El rendimiento con cuantización 4-bit será inferior al FP16, "
    "pero aún usable para inferencia."
)

FINAL_SYNTHESIS = (
    "Qwen3 (no '3.6') es viable en DGX Spark. El modelo 235B-A22B cabe cuantizado a 4-bit "
    "(~60GB de los 128GB disponibles). Para máximo rendimiento, Qwen3-32B en FP16 es la "
    "mejor opción en esta plataforma. La combinación es sólida para desarrollo AI local."
)


class ScriptedGateway:
    """Gateway that returns scripted responses and records payloads."""

    def __init__(self, scripted: dict[AgentRole, list[ModelInvocationResult[BaseModel]]]) -> None:
        self.scripted = {role: list(responses) for role, responses in scripted.items()}
        self.seen_payloads: dict[AgentRole, list[dict[str, Any]]] = {role: [] for role in AgentRole}

    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[BaseModel],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[BaseModel]:
        self.seen_payloads[role].append(payload)
        response = self.scripted[role].pop(0)
        assert isinstance(response.parsed, schema)
        return response


def _build_runtime(tmp_path: Path, gateway: ScriptedGateway, firecrawl_mock: AsyncMock) -> TriadRuntime:
    manager = ConfigManager(root=tmp_path)
    settings = UserSettings(
        language="es",
        permission_mode=PermissionMode.YOLO,
        firecrawl_defaults=FirecrawlDefaults(search_limit=3, search_lang="es"),
    )
    translator = Translator("es")
    logger = logging.getLogger(f"test-integration-{tmp_path}")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    broker = ToolBroker(
        workspace=tmp_path,
        firecrawl_client=firecrawl_mock,
        firecrawl_defaults=settings.firecrawl_defaults,
    )
    return TriadRuntime(
        config_manager=manager,
        settings=settings,
        profiles={},
        translator=translator,
        model_gateway=gateway,
        tool_broker=broker,
        logger=logger,
        firecrawl_client=firecrawl_mock,
    )


@pytest.fixture
def firecrawl_mock() -> AsyncMock:
    """Mock FirecrawlClient that returns realistic search results."""
    mock = AsyncMock()
    mock.search = AsyncMock(return_value=MOCK_SEARCH_RESULTS)
    mock.scrape = AsyncMock(return_value={"success": True, "data": {"content": "page content"}})
    return mock


class TestFullTurnWithSearch:
    """Test the complete turn lifecycle: user → processor (search) → validator → orchestrator."""

    @pytest.mark.anyio
    async def test_full_search_turn(self, tmp_path: Path, firecrawl_mock: AsyncMock) -> None:
        """Simulate: user asks about Qwen 3.6 + DGX Spark, processor searches, full pipeline runs."""
        gateway = ScriptedGateway(
            {
                AgentRole.PROCESSOR: [
                    # Step 1: Processor requests firecrawl_search
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.REQUEST_TOOL,
                            tool_request=ToolRequest(
                                tool="firecrawl_search",
                                arguments={"query": "Qwen 3 LLM model specs DGX Spark compatibility"},
                                reason="Necesito buscar información actualizada sobre Qwen 3 y DGX Spark",
                                risk=ToolRisk.LOW,
                            ),
                        )
                    ),
                    # Step 2: Processor produces final answer with search results
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.FINAL,
                            message=PROCESSOR_SEARCH_ANSWER,
                        ),
                        model_name="qwen3-32b",
                        reasoning_summary=["Busqué info sobre Qwen3 y DGX Spark, combiné los datos."],
                        reasoning_tokens=150,
                    ),
                ],
                AgentRole.VALIDATOR: [
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.FINAL,
                            message=VALIDATOR_ANSWER,
                        ),
                        model_name="qwen3-32b",
                    ),
                ],
                AgentRole.ORCHESTRATOR: [
                    ModelInvocationResult(
                        parsed=ConsolidatedResponse(
                            processor_view=PROCESSOR_SEARCH_ANSWER,
                            validator_view=VALIDATOR_ANSWER,
                            synthesis=FINAL_SYNTHESIS,
                        ),
                        model_name="qwen3-32b",
                    ),
                ],
            }
        )

        runtime = _build_runtime(tmp_path, gateway, firecrawl_mock)
        events = await runtime.submit_user_message(USER_PROMPT)

        # --- Verify event sequence ---
        event_kinds = [e.kind for e in events]

        # Must have: USER, TOOL (request), TOOL (result), REASONING, FINAL
        assert SessionEventKind.USER in event_kinds
        assert SessionEventKind.TOOL in event_kinds
        assert SessionEventKind.FINAL in event_kinds

        # --- Verify Firecrawl was called correctly ---
        firecrawl_mock.search.assert_called_once()
        call_kwargs = firecrawl_mock.search.call_args[1]
        assert "query" in call_kwargs
        assert call_kwargs["limit"] == 3
        assert call_kwargs["lang"] == "es"
        # scrape_options should be passed (v2 correct way)
        assert "scrape_options" in call_kwargs

        # --- Verify processor received search results ---
        processor_payloads = gateway.seen_payloads[AgentRole.PROCESSOR]
        assert len(processor_payloads) == 2  # first call + second call with tool_results
        second_payload = processor_payloads[1]
        assert len(second_payload["tool_results"]) == 1
        tool_result = second_payload["tool_results"][0]
        assert tool_result["tool"] == "firecrawl_search"
        assert tool_result["success"] is True
        # Output should contain sanitized search results
        output_data = json.loads(tool_result["output"])
        assert "data" in output_data

        # --- Verify validator received both user message and processor answer ---
        validator_payloads = gateway.seen_payloads[AgentRole.VALIDATOR]
        assert len(validator_payloads) == 1
        val_payload = validator_payloads[0]
        assert val_payload["user_message"] == USER_PROMPT
        assert val_payload["processor_answer"] == PROCESSOR_SEARCH_ANSWER

        # --- Verify final event contains synthesis ---
        final_events = [e for e in events if e.kind == SessionEventKind.FINAL]
        assert len(final_events) == 1
        assert FINAL_SYNTHESIS in final_events[0].body

        # --- Verify session persistence ---
        session_files = list(Path(runtime.config_manager.paths.sessions_dir).glob("*.jsonl"))
        assert len(session_files) == 1
        lines = session_files[0].read_text().strip().split("\n")
        assert len(lines) == len(events)

    @pytest.mark.anyio
    async def test_search_without_firecrawl_configured(self, tmp_path: Path) -> None:
        """When Firecrawl is not configured, processor gets error and adapts."""
        gateway = ScriptedGateway(
            {
                AgentRole.PROCESSOR: [
                    # Processor tries to search
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.REQUEST_TOOL,
                            tool_request=ToolRequest(
                                tool="firecrawl_search",
                                arguments={"query": "Qwen 3 LLM"},
                                reason="Buscar info",
                                risk=ToolRisk.LOW,
                            ),
                        )
                    ),
                    # Gets error, produces answer from knowledge
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.FINAL,
                            message="No pude buscar en la web, pero basándome en mi conocimiento...",
                        )
                    ),
                ],
                AgentRole.VALIDATOR: [
                    ModelInvocationResult(
                        parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Respuesta limitada pero aceptable.")
                    ),
                ],
                AgentRole.ORCHESTRATOR: [
                    ModelInvocationResult(
                        parsed=ConsolidatedResponse(
                            processor_view="Respuesta sin búsqueda web",
                            validator_view="Aceptable con limitaciones",
                            synthesis="Sin acceso a búsqueda, la respuesta es parcial.",
                        )
                    ),
                ],
            }
        )

        # No firecrawl client
        manager = ConfigManager(root=tmp_path)
        settings = UserSettings(language="es", permission_mode=PermissionMode.YOLO)
        translator = Translator("es")
        logger = logging.getLogger(f"test-no-firecrawl-{tmp_path}")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        broker = ToolBroker(workspace=tmp_path, firecrawl_client=None)
        runtime = TriadRuntime(
            config_manager=manager,
            settings=settings,
            profiles={},
            translator=translator,
            model_gateway=gateway,
            tool_broker=broker,
            logger=logger,
        )

        events = await runtime.submit_user_message(USER_PROMPT)

        # Tool should fail with "not configured" error
        tool_events = [e for e in events if e.kind == SessionEventKind.TOOL]
        assert any(
            "not configured" in e.body.lower() or "firecrawl" in e.body.lower() or "denied" in e.body.lower()
            for e in tool_events
        )

        # But the turn should still complete
        assert any(e.kind == SessionEventKind.FINAL for e in events)

    @pytest.mark.anyio
    async def test_processor_asks_clarification(self, tmp_path: Path, firecrawl_mock: AsyncMock) -> None:
        """Processor asks for clarification before searching."""
        gateway = ScriptedGateway(
            {
                AgentRole.PROCESSOR: [
                    # Processor asks: which Qwen version?
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.ASK_USER,
                            question="¿Te refieres a Qwen3-235B (MoE) o Qwen3-32B (denso)? No existe 'Qwen 3.6'.",
                        )
                    ),
                    # After clarification, searches and answers
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.REQUEST_TOOL,
                            tool_request=ToolRequest(
                                tool="firecrawl_search",
                                arguments={"query": "Qwen3 235B DGX Spark inference"},
                                reason="Buscar compatibilidad",
                                risk=ToolRisk.LOW,
                            ),
                        )
                    ),
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.FINAL, message="Qwen3-235B en DGX Spark: viable con 4-bit quant."
                        )
                    ),
                ],
                AgentRole.VALIDATOR: [
                    ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Correcto.")),
                ],
                AgentRole.ORCHESTRATOR: [
                    ModelInvocationResult(
                        parsed=ConsolidatedResponse(
                            processor_view="Viable con cuantización",
                            validator_view="Correcto",
                            synthesis="Qwen3-235B funciona en DGX Spark con 4-bit quant.",
                        )
                    ),
                ],
            }
        )

        runtime = _build_runtime(tmp_path, gateway, firecrawl_mock)

        # First turn: processor asks clarification
        events1 = await runtime.submit_user_message(USER_PROMPT)
        assert any(e.kind == SessionEventKind.CLARIFICATION for e in events1)
        assert runtime.pending is not None

        # Second turn: user answers, pipeline completes
        events2 = await runtime.submit_user_message("El Qwen3-235B, el grande")
        assert any(e.kind == SessionEventKind.FINAL for e in events2)
        assert runtime.pending is None

    @pytest.mark.anyio
    async def test_permission_mode_ask_blocks_search(self, tmp_path: Path, firecrawl_mock: AsyncMock) -> None:
        """In ASK mode without approval handler, tool is denied."""
        gateway = ScriptedGateway(
            {
                AgentRole.PROCESSOR: [
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.REQUEST_TOOL,
                            tool_request=ToolRequest(
                                tool="firecrawl_search",
                                arguments={"query": "Qwen 3"},
                                reason="Buscar",
                                risk=ToolRisk.LOW,
                            ),
                        )
                    ),
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.FINAL, message="Búsqueda denegada, respondo con lo que sé."
                        )
                    ),
                ],
                AgentRole.VALIDATOR: [
                    ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="OK")),
                ],
                AgentRole.ORCHESTRATOR: [
                    ModelInvocationResult(
                        parsed=ConsolidatedResponse(
                            processor_view="Sin búsqueda",
                            validator_view="OK",
                            synthesis="Respuesta sin herramientas.",
                        )
                    ),
                ],
            }
        )

        manager = ConfigManager(root=tmp_path)
        settings = UserSettings(language="es", permission_mode=PermissionMode.ASK)
        translator = Translator("es")
        logger = logging.getLogger(f"test-ask-mode-{tmp_path}")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        broker = ToolBroker(
            workspace=tmp_path,
            firecrawl_client=firecrawl_mock,
            firecrawl_defaults=settings.firecrawl_defaults,
        )
        runtime = TriadRuntime(
            config_manager=manager,
            settings=settings,
            profiles={},
            translator=translator,
            model_gateway=gateway,
            tool_broker=broker,
            logger=logger,
        )
        # No approval handler set → tool denied

        events = await runtime.submit_user_message(USER_PROMPT)

        # Search should NOT have been called
        firecrawl_mock.search.assert_not_called()
        # But turn completes
        assert any(e.kind == SessionEventKind.FINAL for e in events)

    @pytest.mark.anyio
    async def test_search_results_are_sanitized(self, tmp_path: Path) -> None:
        """Verify that markdown content in search results is converted to plain text."""
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {
                        "title": "Test",
                        "url": "https://example.com",
                        "content": "# Header\n\n[Link text](https://url.com)\n\n![image](img.png)\n\n**bold** text",
                    }
                ],
            }
        )

        gateway = ScriptedGateway(
            {
                AgentRole.PROCESSOR: [
                    ModelInvocationResult(
                        parsed=AgentResponse(
                            kind=AgentActionKind.REQUEST_TOOL,
                            tool_request=ToolRequest(
                                tool="firecrawl_search",
                                arguments={"query": "test"},
                                reason="test",
                                risk=ToolRisk.LOW,
                            ),
                        )
                    ),
                    ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="done")),
                ],
                AgentRole.VALIDATOR: [
                    ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="ok")),
                ],
                AgentRole.ORCHESTRATOR: [
                    ModelInvocationResult(
                        parsed=ConsolidatedResponse(processor_view="done", validator_view="ok", synthesis="syn")
                    ),
                ],
            }
        )

        runtime = _build_runtime(tmp_path, gateway, mock_client)
        await runtime.submit_user_message("test query")

        # Check what the processor received as tool results
        second_payload = gateway.seen_payloads[AgentRole.PROCESSOR][1]
        tool_output = json.loads(second_payload["tool_results"][0]["output"])
        content = tool_output["data"][0]["content"]

        # Markdown should be stripped
        assert "](https://url.com)" not in content  # link syntax removed
        assert "![image]" not in content  # image syntax removed
        assert "Link text" in content  # link text preserved
        assert "bold" in content  # text preserved
