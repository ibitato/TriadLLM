from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from multibrainllm.config import ConfigManager
from multibrainllm.domain import (
    AgentActionKind,
    AgentResponse,
    AgentRole,
    ConsolidatedResponse,
    ModelInvocationResult,
    PermissionMode,
    SessionEvent,
    SessionEventKind,
    ToolRequest,
    UserSettings,
)
from multibrainllm.i18n import Translator
from multibrainllm.runtime import MultiBrainRuntime
from multibrainllm.tools import ToolBroker


class FakeGateway:
    def __init__(self, scripted: dict[AgentRole, list[ModelInvocationResult[BaseModel]]]) -> None:
        self.scripted = {role: list(responses) for role, responses in scripted.items()}
        self.seen_payloads: dict[AgentRole, list[dict[str, Any]]] = {role: [] for role in scripted}

    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[BaseModel],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[BaseModel]:
        self.seen_payloads.setdefault(role, []).append(payload)
        response = self.scripted[role].pop(0)
        assert isinstance(response.parsed, schema)
        return response


def build_runtime(tmp_path: Path, gateway: FakeGateway) -> MultiBrainRuntime:
    manager = ConfigManager(root=tmp_path)
    settings = UserSettings(language="es", permission_mode=PermissionMode.ASK)
    translator = Translator("es")
    logger = logging.getLogger(f"test-runtime-{tmp_path}")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return MultiBrainRuntime(
        config_manager=manager,
        settings=settings,
        profiles={},
        translator=translator,
        model_gateway=gateway,
        tool_broker=ToolBroker(workspace=tmp_path),
        logger=logger,
    )


@pytest.mark.anyio
async def test_runtime_handles_clarification_resume(tmp_path: Path) -> None:
    gateway = FakeGateway(
        {
            AgentRole.PROCESSOR: [
                ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.ASK_USER, question="¿Qué archivo?")),
                ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Analicé main.py")),
            ],
            AgentRole.VALIDATOR: [
                ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="La respuesta es consistente")),
            ],
            AgentRole.ORCHESTRATOR: [
                ModelInvocationResult(
                    parsed=ConsolidatedResponse(
                        processor_view="Agente 1 dijo que analizó main.py",
                        validator_view="Agente 2 confirmó consistencia",
                        synthesis="La ruta final es revisar main.py",
                    )
                ),
            ],
        }
    )
    runtime = build_runtime(tmp_path, gateway)

    first_events = await runtime.submit_user_message("revisa el proyecto")
    assert any(event.kind.value == "clarification" for event in first_events)

    second_events = await runtime.submit_user_message("main.py")
    assert any(event.kind.value == "final" for event in second_events)


@pytest.mark.anyio
async def test_runtime_handles_tool_denial(tmp_path: Path) -> None:
    gateway = FakeGateway(
        {
            AgentRole.PROCESSOR: [
                ModelInvocationResult(
                    parsed=AgentResponse(
                        kind=AgentActionKind.REQUEST_TOOL,
                        tool_request=ToolRequest(
                            tool="shell_exec",
                            arguments={"command": "echo hello"},
                            reason="Necesito validar el entorno",
                        ),
                    ),
                ),
                ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="No pude ejecutar, pero te explico el siguiente paso.")),
            ],
            AgentRole.VALIDATOR: [
                ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="La negativa está correctamente reflejada.")),
            ],
            AgentRole.ORCHESTRATOR: [
                ModelInvocationResult(
                    parsed=ConsolidatedResponse(
                        processor_view="Agent 1 documented the denied execution.",
                        validator_view="Agent 2 accepted the denial path.",
                        synthesis="The system handled the permission denial correctly.",
                    )
                ),
            ],
        }
    )
    runtime = build_runtime(tmp_path, gateway)

    events = await runtime.submit_user_message("ejecuta algo")

    assert any(event.title == "Tool Denegada" for event in events)
    assert any(event.kind.value == "final" for event in events)


@pytest.mark.anyio
async def test_runtime_emits_reasoning_events(tmp_path: Path) -> None:
    gateway = FakeGateway(
        {
            AgentRole.PROCESSOR: [
                ModelInvocationResult(
                    parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Respuesta"),
                    model_name="gpt-5.4-2026-03-05",
                    reasoning_summary=["He comparado varias opciones antes de responder."],
                    reasoning_tokens=42,
                )
            ],
            AgentRole.VALIDATOR: [
                ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="Validado")),
            ],
            AgentRole.ORCHESTRATOR: [
                ModelInvocationResult(
                    parsed=ConsolidatedResponse(
                        processor_view="Respuesta",
                        validator_view="Validado",
                        synthesis="Síntesis",
                    )
                )
            ],
        }
    )
    runtime = build_runtime(tmp_path, gateway)

    events = await runtime.submit_user_message("hola")

    assert any(event.kind.value == "reasoning" for event in events)


@pytest.mark.anyio
async def test_runtime_passes_full_visible_conversation(tmp_path: Path) -> None:
    gateway = FakeGateway(
        {
            AgentRole.PROCESSOR: [ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="proc"))],
            AgentRole.VALIDATOR: [ModelInvocationResult(parsed=AgentResponse(kind=AgentActionKind.FINAL, message="val"))],
            AgentRole.ORCHESTRATOR: [
                ModelInvocationResult(
                    parsed=ConsolidatedResponse(
                        processor_view="proc",
                        validator_view="val",
                        synthesis="syn",
                    )
                )
            ],
        }
    )
    runtime = build_runtime(tmp_path, gateway)
    for index in range(10):
        runtime.history.append(
            SessionEvent(
                kind=SessionEventKind.FINAL,
                title=f"Turn {index}",
                body=f"Body {index}",
            )
        )

    await runtime.submit_user_message("nuevo mensaje")

    processor_payload = gateway.seen_payloads[AgentRole.PROCESSOR][0]
    assert len(processor_payload["conversation"]) == 11
