import pytest

from multibrainllm.domain import ProviderBackend, ProviderProfile, UserSettings
from multibrainllm.providers import ProviderGateway
from multibrainllm.domain import AgentActionKind, AgentResponse, AgentRole, ModelInvocationResult


def test_extract_mistral_message_parts() -> None:
    gateway = ProviderGateway(profiles={}, settings=UserSettings())
    content = [
        {
            "type": "thinking",
            "thinking": [
                {"type": "text", "text": "step one"},
                {"type": "text", "text": "step two"},
            ],
        },
        {
            "type": "text",
            "text": '{"kind":"final","message":"ok"}',
        },
    ]

    text, thinking = gateway._extract_mistral_message_parts(content)

    assert text == '{"kind":"final","message":"ok"}'
    assert thinking == ["step one", "step two"]


def test_local_openai_compatible_profile_uses_dummy_key() -> None:
    profile = ProviderProfile(
        id="local",
        label="Local",
        provider=ProviderBackend.OPENAI_COMPATIBLE,
        base_url="http://127.0.0.1:8080/v1",
        model="zai-org/GLM-4.7-Flash",
        api_key_literal="dummy",
    )
    gateway = ProviderGateway(profiles={"local": profile}, settings=UserSettings(default_profile="local"))

    assert gateway._resolve_api_key(profile, ProviderBackend.OPENAI_COMPATIBLE) == "dummy"


def test_normalize_json_text_escapes_control_chars_inside_strings() -> None:
    gateway = ProviderGateway(profiles={}, settings=UserSettings())
    raw = '{"message":"line 1\nline 2","kind":"final"}'

    normalized = gateway._normalize_json_text(raw)

    assert normalized == '{"message":"line 1\\nline 2","kind":"final"}'


def test_fallback_agent_response_from_reasoning_infers_tool_request() -> None:
    gateway = ProviderGateway(profiles={}, settings=UserSettings())

    result = gateway._fallback_agent_response_from_reasoning(
        ["I should use list_dir to inspect the current workspace before validating the pipeline."],
        {"language": "en"},
    )

    assert result.kind == AgentActionKind.REQUEST_TOOL
    assert result.tool_request is not None
    assert result.tool_request.tool == "list_dir"


def test_fallback_agent_response_from_reasoning_infers_clarification() -> None:
    gateway = ProviderGateway(profiles={}, settings=UserSettings())

    result = gateway._fallback_agent_response_from_reasoning(
        ["No tengo contexto suficiente y no puedo verificar qué pipeline se refiere el usuario."],
        {"language": "es"},
    )

    assert result.kind == AgentActionKind.ASK_USER
    assert "pipeline" in (result.question or "").lower()


def test_fallback_consolidated_response_uses_existing_outputs() -> None:
    gateway = ProviderGateway(profiles={}, settings=UserSettings())

    result = gateway._fallback_consolidated_response(
        {
            "language": "es",
            "processor_output": "processor ok",
            "validator_output": "validator ok",
        }
    )

    assert result.processor_view == "processor ok"
    assert result.validator_view == "validator ok"
    assert "Síntesis automática" in result.synthesis


@pytest.mark.anyio
async def test_ainvoke_with_repair_retries_after_parse_failure() -> None:
    profile = ProviderProfile(
        id="local",
        label="Local",
        provider=ProviderBackend.OPENAI_COMPATIBLE,
        base_url="http://127.0.0.1:8080/v1",
        model="zai-org/GLM-4.7-Flash",
        api_key_literal="dummy",
    )
    gateway = ProviderGateway(profiles={"local": profile}, settings=UserSettings(default_profile="local"))
    attempts: list[bool] = []

    async def fake_once(  # noqa: ANN001, ANN202
        backend,
        current_profile,
        schema,
        system_prompt,
        payload,
        repair_mode=False,
    ):
        attempts.append(repair_mode)
        if not repair_mode:
            raise RuntimeError("Provider response did not include a JSON object")
        return ModelInvocationResult(
            parsed=AgentResponse(kind=AgentActionKind.FINAL, message="ok"),
            model_name=current_profile.model,
        )

    gateway._ainvoke_once = fake_once  # type: ignore[method-assign]

    result = await gateway.ainvoke(
        role=AgentRole.PROCESSOR,
        schema=AgentResponse,
        system_prompt="Return final JSON.",
        payload={"user_message": "hola"},
    )

    assert attempts == [False, True]
    assert result.parsed.message == "ok"
