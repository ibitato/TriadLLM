from multibrainllm.domain import UserSettings
from multibrainllm.providers import LangChainGateway


def test_extract_mistral_message_parts() -> None:
    gateway = LangChainGateway(profiles={}, settings=UserSettings())
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
