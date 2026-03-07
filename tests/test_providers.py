from multibrainllm.domain import ProviderBackend, ProviderProfile, UserSettings
from multibrainllm.providers import ProviderGateway


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
