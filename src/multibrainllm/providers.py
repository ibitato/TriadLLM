from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from pydantic import BaseModel

from multibrainllm.domain import AgentRole, ModelInvocationResult, ProviderProfile, SchemaT, UserSettings


class ModelGateway(Protocol):
    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        ...


class LangChainGateway:
    def __init__(self, profiles: dict[str, ProviderProfile], settings: UserSettings) -> None:
        self.profiles = profiles
        self.settings = settings
        self._clients: dict[str, ChatOpenAI] = {}
        self._openai_clients: dict[str, AsyncOpenAI] = {}

    def profile_for_role(self, role: AgentRole) -> ProviderProfile:
        profile_id = self.settings.agent_profiles.get(role) or self.settings.default_profile
        if not profile_id:
            raise RuntimeError("No provider profile configured.")
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise RuntimeError(f"Provider profile '{profile_id}' is not defined.") from exc

    def _get_client(self, profile: ProviderProfile) -> ChatOpenAI:
        if profile.id in self._clients:
            return self._clients[profile.id]

        api_key = os.getenv(profile.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing environment variable: {profile.api_key_env}")

        client = ChatOpenAI(
            api_key=api_key,
            base_url=profile.base_url,
            model=profile.model,
            temperature=profile.temperature,
            timeout=profile.timeout,
            max_tokens=profile.max_tokens,
            reasoning_effort=profile.reasoning_effort,
            default_headers=profile.default_headers or None,
        )
        self._clients[profile.id] = client
        return client

    def _get_openai_client(self, profile: ProviderProfile) -> AsyncOpenAI:
        if profile.id in self._openai_clients:
            return self._openai_clients[profile.id]

        api_key = os.getenv(profile.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing environment variable: {profile.api_key_env}")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=profile.base_url,
            default_headers=profile.default_headers or None,
        )
        self._openai_clients[profile.id] = client
        return client

    def _is_official_openai(self, profile: ProviderProfile) -> bool:
        host = urlparse(profile.base_url).hostname or ""
        return host.endswith("openai.com")

    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        profile = self.profile_for_role(role)
        if self._is_official_openai(profile) and profile.reasoning_summary:
            return await self._ainvoke_openai_responses(profile, schema, system_prompt, payload)
        return await self._ainvoke_langchain(profile, schema, system_prompt, payload)

    async def _ainvoke_langchain(
        self,
        profile: ProviderProfile,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        client = self._get_client(profile)
        runnable = client.with_structured_output(schema, include_raw=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        result = await runnable.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content),
            ]
        )
        if isinstance(result, dict):
            parsed = result["parsed"]
            raw = result.get("raw")
        else:
            parsed = result
            raw = None

        if not isinstance(parsed, schema):
            parsed = schema.model_validate(parsed)

        reasoning_summary = self._extract_reasoning_blocks(getattr(raw, "content", []))
        model_name = None
        if raw is not None:
            model_name = raw.response_metadata.get("model_name") or raw.response_metadata.get("model")

        return ModelInvocationResult(
            parsed=parsed,
            model_name=model_name,
            reasoning_summary=reasoning_summary,
        )

    async def _ainvoke_openai_responses(
        self,
        profile: ProviderProfile,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        client = self._get_openai_client(profile)
        request: dict[str, Any] = {
            "model": profile.model,
            "input": json.dumps(payload, ensure_ascii=False, indent=2),
            "temperature": profile.temperature,
        }
        request["instructions"] = self._build_openai_json_instructions(system_prompt, schema)
        if profile.max_tokens is not None:
            request["max_output_tokens"] = profile.max_tokens
        if profile.reasoning_effort or profile.reasoning_summary:
            request["reasoning"] = {
                "effort": profile.reasoning_effort or "medium",
                "summary": profile.reasoning_summary,
            }

        response = await client.responses.create(**request)
        parsed = self._parse_openai_output(response.output_text, schema)

        reasoning_summary = self._extract_openai_reasoning(response.output)
        reasoning_tokens = None
        if response.usage and response.usage.output_tokens_details:
            reasoning_tokens = response.usage.output_tokens_details.reasoning_tokens

        return ModelInvocationResult(
            parsed=parsed,
            model_name=response.model,
            reasoning_summary=reasoning_summary,
            reasoning_tokens=reasoning_tokens,
        )

    def _extract_reasoning_blocks(self, content: Any) -> list[str]:
        if not isinstance(content, list):
            return []
        summaries: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type not in {"reasoning", "thinking"}:
                continue
            for item in block.get("summary", []):
                text = item.get("text")
                if text:
                    summaries.append(str(text))
        return summaries

    def _extract_openai_reasoning(self, output: Any) -> list[str]:
        summaries: list[str] = []
        for item in output:
            if getattr(item, "type", None) not in {"reasoning", "thinking"}:
                continue
            for summary in getattr(item, "summary", []) or []:
                text = getattr(summary, "text", None)
                if text:
                    summaries.append(str(text))
        return summaries

    def _build_openai_json_instructions(self, system_prompt: str, schema: type[SchemaT]) -> str:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        return "\n\n".join(
            [
                system_prompt,
                "Return only valid JSON with no Markdown fences or extra commentary.",
                f"JSON schema to follow:\n{schema_json}",
            ]
        )

    def _parse_openai_output(self, output_text: str, schema: type[SchemaT]) -> SchemaT:
        try:
            return schema.model_validate_json(output_text)
        except Exception:
            candidate = self._extract_json_object(output_text)
            return schema.model_validate_json(candidate)

    def _extract_json_object(self, text: str) -> str:
        start = text.find("{")
        if start == -1:
            raise RuntimeError("OpenAI response did not include a JSON object")
        depth = 0
        in_string = False
        escaped = False
        for index, char in enumerate(text[start:], start=start):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        raise RuntimeError("OpenAI response JSON object was incomplete")
