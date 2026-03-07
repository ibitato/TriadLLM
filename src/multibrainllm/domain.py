from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

import json

from pydantic import BaseModel, Field, field_validator, model_validator


LanguageCode = Literal["en", "es"]


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    PROCESSOR = "processor"
    VALIDATOR = "validator"


class PermissionMode(str, Enum):
    ASK = "ask"
    YOLO = "yolo"


class ProviderBackend(str, Enum):
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    MISTRAL = "mistral"


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentActionKind(str, Enum):
    FINAL = "final"
    REQUEST_TOOL = "request_tool"
    ASK_USER = "ask_user"


class SessionEventKind(str, Enum):
    USER = "user"
    SYSTEM = "system"
    TOOL = "tool"
    REASONING = "reasoning"
    CLARIFICATION = "clarification"
    FINAL = "final"


class ProviderProfile(BaseModel):
    id: str
    label: str
    base_url: str
    model: str
    provider: ProviderBackend | None = None
    api_key_env: str | None = None
    api_key_literal: str | None = None
    temperature: float = 0.2
    timeout: float = 60.0
    max_tokens: int | None = None
    context_window: int | None = None
    max_output_tokens_limit: int | None = None
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    default_headers: dict[str, str] = Field(default_factory=dict)


class UserSettings(BaseModel):
    language: LanguageCode = "es"
    permission_mode: PermissionMode = PermissionMode.ASK
    show_reasoning: bool = True
    show_tool_results: bool = True
    default_profile: str | None = None
    agent_profiles: dict[AgentRole, str] = Field(default_factory=dict)
    log_level: str = "INFO"
    log_retention_days: int = 7


class ToolRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str
    risk: ToolRisk = ToolRisk.MEDIUM


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    kind: AgentActionKind
    message: str = ""
    question: str | None = None
    tool_request: ToolRequest | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "AgentResponse":
        if self.kind == AgentActionKind.ASK_USER and not self.question:
            raise ValueError("question is required when kind=ask_user")
        if self.kind == AgentActionKind.REQUEST_TOOL and not self.tool_request:
            raise ValueError("tool_request is required when kind=request_tool")
        return self


class ConsolidatedResponse(BaseModel):
    processor_view: str
    validator_view: str
    synthesis: str

    @field_validator("processor_view", "validator_view", "synthesis", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return _coerce_text(value)


class PendingClarification(BaseModel):
    role: AgentRole
    question: str
    base_payload: dict[str, Any]
    tool_results: list[ToolResult] = Field(default_factory=list)
    clarification_answers: list[str] = Field(default_factory=list)


class SessionEvent(BaseModel):
    kind: SessionEventKind
    title: str
    body: str
    role: AgentRole | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
    )


class AppPaths(BaseModel):
    config_dir: str
    data_dir: str
    log_dir: str
    settings_path: str
    profiles_path: str
    sessions_dir: str
    log_file: str


class RuntimeStatus(BaseModel):
    language: LanguageCode
    permission_mode: PermissionMode
    show_reasoning: bool
    show_tool_results: bool
    default_profile: str | None
    active_profiles: dict[AgentRole, str | None]
    available_profiles: list[str]
    pending_clarification: bool
    logs_path: str
    config_path: str


SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(slots=True)
class ModelInvocationResult(Generic[SchemaT]):
    parsed: SchemaT
    model_name: str | None = None
    reasoning_summary: list[str] = field(default_factory=list)
    reasoning_tokens: int | None = None


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [_coerce_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        for key in (
            "text",
            "message",
            "content",
            "synthesis",
            "final_answer",
            "respuesta_final",
            "answer",
        ):
            if key in value:
                text = _coerce_text(value[key])
                if text:
                    return text
        for item in value.values():
            text = _coerce_text(item)
            if text:
                return text
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()
