from multibrainllm.domain import AgentRole
from multibrainllm.prompts import AVAILABLE_TOOLS, build_agent_prompt


def test_processor_prompt_lists_supported_tools() -> None:
    prompt = build_agent_prompt(AgentRole.PROCESSOR, "es")

    for tool in AVAILABLE_TOOLS:
        assert tool in prompt


def test_validator_prompt_forbids_invented_tools() -> None:
    prompt = build_agent_prompt(AgentRole.VALIDATOR, "en")

    assert "Never invent tool names." in prompt


def test_processor_prompt_documents_search_files_query_requirement() -> None:
    prompt = build_agent_prompt(AgentRole.PROCESSOR, "en")

    assert "`query` is required and must be non-empty." in prompt
    assert "If you need to verify whether a file exists, prefer `list_dir` first." in prompt


def test_validator_prompt_forbids_repeating_invalid_tool_request() -> None:
    prompt = build_agent_prompt(AgentRole.VALIDATOR, "en")

    assert "Do not repeat the same invalid tool request." in prompt
    assert "The payload may include prior `tool_results`" in prompt
