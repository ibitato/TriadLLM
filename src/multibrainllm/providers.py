from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib.parse import urlparse

from mistralai import Mistral
from openai import AsyncOpenAI

from multibrainllm.domain import (
    ModelInvocationResult,
    ProviderBackend,
    ProviderProfile,
    SchemaT,
    UserSettings,
    AgentRole,
)


class ModelGateway(Protocol):
    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        ...


class ProviderGateway:
    def __init__(self, profiles: dict[str, ProviderProfile], settings: UserSettings) -> None:
        self.profiles = profiles
        self.settings = settings
        self._openai_clients: dict[str, AsyncOpenAI] = {}
        self._mistral_clients: dict[str, Mistral] = {}

    def profile_for_role(self, role: AgentRole) -> ProviderProfile:
        profile_id = self.settings.agent_profiles.get(role) or self.settings.default_profile
        if not profile_id:
            raise RuntimeError("No provider profile configured.")
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise RuntimeError(f"Provider profile '{profile_id}' is not defined.") from exc

    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        profile = self.profile_for_role(role)
        backend = self._backend_for_profile(profile)
        if backend == ProviderBackend.MISTRAL:
            return await self._ainvoke_mistral_chat(profile, schema, system_prompt, payload)
        if backend == ProviderBackend.OPENAI and profile.reasoning_summary:
            return await self._ainvoke_openai_responses(profile, schema, system_prompt, payload)
        return await self._ainvoke_openai_chat_json(profile, schema, system_prompt, payload)

    def _backend_for_profile(self, profile: ProviderProfile) -> ProviderBackend:
        if profile.provider is not None:
            return profile.provider

        host = urlparse(profile.base_url).hostname or ""
        if host.endswith("mistral.ai"):
            return ProviderBackend.MISTRAL
        if host.endswith("openai.com"):
            return ProviderBackend.OPENAI
        return ProviderBackend.OPENAI_COMPATIBLE

    def _resolve_api_key(self, profile: ProviderProfile, backend: ProviderBackend) -> str:
        if profile.api_key_env:
            env_value = os.getenv(profile.api_key_env)
            if env_value:
                return env_value
        if profile.api_key_literal:
            return profile.api_key_literal

        host = urlparse(profile.base_url).hostname or ""
        if backend == ProviderBackend.OPENAI_COMPATIBLE and host in {"127.0.0.1", "localhost"}:
            return "dummy"

        if profile.api_key_env:
            raise RuntimeError(f"Missing environment variable: {profile.api_key_env}")
        raise RuntimeError(f"No API key configured for profile '{profile.id}'")

    def _get_openai_client(self, profile: ProviderProfile) -> AsyncOpenAI:
        if profile.id in self._openai_clients:
            return self._openai_clients[profile.id]

        backend = self._backend_for_profile(profile)
        api_key = self._resolve_api_key(profile, backend)
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=profile.base_url,
            default_headers=profile.default_headers or None,
            timeout=profile.timeout,
        )
        self._openai_clients[profile.id] = client
        return client

    def _get_mistral_client(self, profile: ProviderProfile) -> Mistral:
        if profile.id in self._mistral_clients:
            return self._mistral_clients[profile.id]

        api_key = self._resolve_api_key(profile, ProviderBackend.MISTRAL)
        server_url = self._normalize_mistral_server_url(profile.base_url)
        client = Mistral(
            api_key=api_key,
            server_url=server_url,
            timeout_ms=int(profile.timeout * 1000),
        )
        self._mistral_clients[profile.id] = client
        return client

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
            "instructions": self._build_json_instructions(system_prompt, schema),
            "input": json.dumps(payload, ensure_ascii=False, indent=2),
            "temperature": profile.temperature,
        }
        if profile.max_tokens is not None:
            request["max_output_tokens"] = profile.max_tokens
        if profile.reasoning_effort or profile.reasoning_summary:
            request["reasoning"] = {
                "effort": profile.reasoning_effort or "medium",
                "summary": profile.reasoning_summary,
            }

        response = await client.responses.create(**request)
        parsed = self._parse_json_output(response.output_text, schema)
        reasoning_summary = self._extract_openai_reasoning_from_responses(response.model_dump(mode="json"))
        reasoning_tokens = None
        usage = response.usage
        if usage and usage.output_tokens_details:
            reasoning_tokens = usage.output_tokens_details.reasoning_tokens

        return ModelInvocationResult(
            parsed=parsed,
            model_name=response.model,
            reasoning_summary=reasoning_summary,
            reasoning_tokens=reasoning_tokens,
        )

    async def _ainvoke_openai_chat_json(
        self,
        profile: ProviderProfile,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        client = self._get_openai_client(profile)
        response = await client.chat.completions.create(
            model=profile.model,
            messages=[
                {"role": "system", "content": self._build_json_instructions(system_prompt, schema)},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            temperature=profile.temperature,
            max_tokens=profile.max_tokens,
        )
        data = response.model_dump(mode="json")
        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        parsed = self._parse_json_output(content, schema)
        reasoning_summary = self._extract_openai_chat_reasoning(message)

        return ModelInvocationResult(
            parsed=parsed,
            model_name=data.get("model"),
            reasoning_summary=reasoning_summary,
        )

    async def _ainvoke_mistral_chat(
        self,
        profile: ProviderProfile,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        client = self._get_mistral_client(profile)
        request: dict[str, Any] = {
            "model": profile.model,
            "messages": [
                {"role": "system", "content": self._build_json_instructions(system_prompt, schema)},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens,
        }
        if profile.model.startswith("magistral"):
            request["prompt_mode"] = "reasoning"

        response = await client.chat.complete_async(**request)
        data = response.model_dump(mode="json")
        message = data["choices"][0]["message"]
        final_text, thinking_chunks = self._extract_mistral_message_parts(message.get("content"))
        parsed = self._parse_json_output(final_text, schema)

        return ModelInvocationResult(
            parsed=parsed,
            model_name=data.get("model"),
            reasoning_summary=thinking_chunks,
        )

    def _build_json_instructions(self, system_prompt: str, schema: type[SchemaT]) -> str:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        return "\n\n".join(
            [
                system_prompt,
                "Return only valid JSON with no Markdown fences and no extra commentary.",
                f"JSON schema to follow:\n{schema_json}",
            ]
        )

    def _parse_json_output(self, output_text: str, schema: type[SchemaT]) -> SchemaT:
        normalized_output = self._normalize_json_text(output_text)
        try:
            return schema.model_validate_json(normalized_output)
        except Exception:
            candidate = self._normalize_json_text(self._extract_json_object(output_text))
            return schema.model_validate_json(candidate)

    def _extract_json_object(self, text: str) -> str:
        start = text.find("{")
        if start == -1:
            raise RuntimeError("Provider response did not include a JSON object")
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
        raise RuntimeError("Provider response JSON object was incomplete")

    def _normalize_json_text(self, text: str) -> str:
        chars: list[str] = []
        in_string = False
        escaped = False
        for char in text:
            if in_string:
                if escaped:
                    chars.append(char)
                    escaped = False
                    continue
                if char == "\\":
                    chars.append(char)
                    escaped = True
                    continue
                if char == '"':
                    chars.append(char)
                    in_string = False
                    continue
                if char == "\n":
                    chars.append("\\n")
                    continue
                if char == "\r":
                    chars.append("\\r")
                    continue
                if char == "\t":
                    chars.append("\\t")
                    continue
                chars.append(char)
                continue

            chars.append(char)
            if char == '"':
                in_string = True
        return "".join(chars)

    def _extract_openai_reasoning_from_responses(self, response: dict[str, Any]) -> list[str]:
        summaries: list[str] = []
        for item in response.get("output", []):
            if item.get("type") not in {"reasoning", "thinking"}:
                continue
            for summary in item.get("summary", []) or []:
                text = summary.get("text")
                if text:
                    summaries.append(str(text))
        return summaries

    def _extract_openai_chat_reasoning(self, message: dict[str, Any]) -> list[str]:
        summaries: list[str] = []
        for key in ("reasoning", "reasoning_content"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                summaries.append(value.strip())
        content = message.get("content")
        if isinstance(content, list):
            for chunk in content:
                if not isinstance(chunk, dict):
                    continue
                if chunk.get("type") in {"thinking", "reasoning"}:
                    text = chunk.get("text")
                    if text:
                        summaries.append(str(text))
        return summaries

    def _extract_mistral_message_parts(self, content: Any) -> tuple[str, list[str]]:
        if isinstance(content, str):
            return content, []
        if not isinstance(content, list):
            raise RuntimeError("Unsupported Mistral message content format")

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            chunk_type = chunk.get("type")
            if chunk_type == "text":
                text = chunk.get("text")
                if text:
                    text_parts.append(str(text))
            elif chunk_type == "thinking":
                for item in chunk.get("thinking", []):
                    if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                        thinking_parts.append(str(item["text"]))
        return "\n".join(text_parts).strip(), thinking_parts

    def _normalize_mistral_server_url(self, base_url: str) -> str:
        return base_url[:-3] if base_url.endswith("/v1") else base_url
