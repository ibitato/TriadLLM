from multibrainllm.domain import AgentRole
from multibrainllm.prompts import AVAILABLE_TOOLS, build_agent_prompt


def test_processor_prompt_lists_supported_tools() -> None:
    prompt = build_agent_prompt(AgentRole.PROCESSOR, "es")

    for tool in AVAILABLE_TOOLS:
        assert tool in prompt


def test_validator_prompt_forbids_invented_tools() -> None:
    prompt = build_agent_prompt(AgentRole.VALIDATOR, "en")

    assert "Never invent tool names." in prompt
