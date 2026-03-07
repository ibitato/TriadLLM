from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol
from urllib.parse import urlparse

from mistralai import Mistral
from openai import AsyncOpenAI

from multibrainllm.domain import (
    AgentActionKind,
    AgentResponse,
    ConsolidatedResponse,
    ToolRequest,
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
        self.logger = logging.getLogger("multibrainllm.providers")

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
        self.logger.debug(
            "provider_invoke_start",
            extra={
                "role": role.value,
                "profile_id": profile.id,
                "backend": backend.value,
                "model": profile.model,
                "schema": schema.__name__,
                "payload_summary": self._summarize_payload(payload),
            },
        )
        return await self._ainvoke_with_repair(
            backend=backend,
            profile=profile,
            schema=schema,
            system_prompt=system_prompt,
            payload=payload,
        )

    async def _ainvoke_with_repair(
        self,
        backend: ProviderBackend,
        profile: ProviderProfile,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult[SchemaT]:
        try:
            return await self._ainvoke_once(backend, profile, schema, system_prompt, payload)
        except Exception as exc:
            self.logger.warning(
                "provider_invoke_parse_failure",
                extra={
                    "profile_id": profile.id,
                    "backend": backend.value,
                    "model": profile.model,
                    "schema": schema.__name__,
                    "error": str(exc),
                    "payload_summary": self._summarize_payload(payload),
                },
            )
            repair_prompt = self._build_repair_prompt(system_prompt, schema)
            repaired_payload = {
                "original_payload": payload,
                "error": str(exc),
                "instruction": "Retry the task and return only valid JSON that matches the schema.",
            }
            return await self._ainvoke_once(
                backend,
                profile,
                schema,
                repair_prompt,
                repaired_payload,
                repair_mode=True,
            )

    async def _ainvoke_once(
        self,
        backend: ProviderBackend,
        profile: ProviderProfile,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
        repair_mode: bool = False,
    ) -> ModelInvocationResult[SchemaT]:
        self.logger.debug(
            "provider_invoke_attempt",
            extra={
                "profile_id": profile.id,
                "backend": backend.value,
                "model": profile.model,
                "schema": schema.__name__,
                "repair_mode": repair_mode,
            },
        )
        if backend == ProviderBackend.MISTRAL:
            return await self._ainvoke_mistral_chat(profile, schema, system_prompt, payload, repair_mode=repair_mode)
        if backend == ProviderBackend.OPENAI and profile.reasoning_summary and not repair_mode:
            return await self._ainvoke_openai_responses(profile, schema, system_prompt, payload)
        return await self._ainvoke_openai_chat_json(profile, schema, system_prompt, payload, repair_mode=repair_mode)

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
        self.logger.debug(
            "provider_invoke_success",
            extra={
                "profile_id": profile.id,
                "backend": ProviderBackend.OPENAI.value,
                "model": response.model,
                "schema": schema.__name__,
                "reasoning_tokens": reasoning_tokens,
                "parsed_summary": self._summarize_payload(parsed.model_dump(mode="json")),
            },
        )

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
        repair_mode: bool = False,
    ) -> ModelInvocationResult[SchemaT]:
        client = self._get_openai_client(profile)
        backend = self._backend_for_profile(profile)
        request: dict[str, Any] = {
            "model": profile.model,
            "messages": [
                {"role": "system", "content": self._build_json_instructions(system_prompt, schema)},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            "temperature": 0.0 if repair_mode else profile.temperature,
            "max_tokens": profile.max_tokens,
        }
        if backend == ProviderBackend.OPENAI_COMPATIBLE:
            request["response_format"] = {"type": "json_object"}
        if backend == ProviderBackend.OPENAI and repair_mode:
            request["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(
            **request,
        )
        data = response.model_dump(mode="json")
        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        reasoning_summary = self._extract_openai_chat_reasoning(message)
        if not content.strip() and schema is AgentResponse:
            parsed = self._fallback_agent_response_from_reasoning(reasoning_summary, payload)
        elif not content.strip() and schema is ConsolidatedResponse:
            parsed = self._fallback_consolidated_response(payload)
        else:
            parsed = self._parse_json_output(content, schema)
        self.logger.debug(
            "provider_invoke_success",
            extra={
                "profile_id": profile.id,
                "backend": backend.value,
                "model": data.get("model"),
                "schema": schema.__name__,
                "repair_mode": repair_mode,
                "reasoning_chunks": len(reasoning_summary),
                "raw_content_preview": content[:800],
                "parsed_summary": self._summarize_payload(parsed.model_dump(mode="json")),
            },
        )

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
        repair_mode: bool = False,
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
        if profile.model.startswith("magistral") and not repair_mode:
            request["prompt_mode"] = "reasoning"

        response = await client.chat.complete_async(**request)
        data = response.model_dump(mode="json")
        message = data["choices"][0]["message"]
        final_text, thinking_chunks = self._extract_mistral_message_parts(message.get("content"))
        parsed = self._parse_json_output(final_text, schema)
        self.logger.debug(
            "provider_invoke_success",
            extra={
                "profile_id": profile.id,
                "backend": ProviderBackend.MISTRAL.value,
                "model": data.get("model"),
                "schema": schema.__name__,
                "repair_mode": repair_mode,
                "thinking_chunks": len(thinking_chunks),
                "raw_content_preview": final_text[:800],
                "parsed_summary": self._summarize_payload(parsed.model_dump(mode="json")),
            },
        )

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
                "Return only valid JSON with double-quoted keys and string values where required. Do not output Markdown, prose, or code fences.",
                f"JSON schema to follow:\n{schema_json}",
            ]
        )

    def _build_repair_prompt(self, system_prompt: str, schema: type[SchemaT]) -> str:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        return "\n\n".join(
            [
                system_prompt,
                "Your previous answer could not be parsed.",
                "Retry from scratch and return exactly one valid JSON object matching the schema.",
                "Do not output internal reasoning, thinking, or analysis.",
                "Skip directly to the final JSON object.",
                "Do not include explanations, Markdown, code fences, or any text before or after the JSON object.",
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

    def _fallback_agent_response_from_reasoning(
        self,
        reasoning_summary: list[str],
        payload: dict[str, Any],
    ) -> AgentResponse:
        reasoning_text = "\n".join(reasoning_summary)
        lowered = reasoning_text.lower()
        language = str(payload.get("language", "en")).lower()
        clarification_question = (
            "Necesito más contexto verificable para continuar. ¿Puedes indicar qué pipeline o evidencia debo revisar?"
            if language == "es"
            else "I need more verifiable context to continue. Which pipeline or evidence should I review?"
        )

        for tool_name in ("list_dir", "search_files", "read_file", "pwd", "get_env", "shell_exec", "write_file"):
            if tool_name in reasoning_text or tool_name in lowered:
                reason = (
                    f"Recovered from reasoning-only provider output; inferred tool request for {tool_name}."
                )
                return AgentResponse(
                    kind=AgentActionKind.REQUEST_TOOL,
                    tool_request=ToolRequest(tool=tool_name, arguments={}, reason=reason),
                )

        uncertainty_markers = (
            "need more context",
            "insufficient context",
            "i don't know",
            "i do not know",
            "no tengo contexto",
            "necesito más contexto",
            "falta contexto",
            "cannot verify",
            "no puedo verificar",
            "which pipeline",
            "qué pipeline",
        )
        if any(marker in lowered for marker in uncertainty_markers):
            return AgentResponse(kind=AgentActionKind.ASK_USER, question=clarification_question)

        message = (
            "No pude verificar la respuesta con certeza; necesito más contexto o evidencia."
            if language == "es"
            else "I could not verify the answer with certainty; I need more context or evidence."
        )
        return AgentResponse(kind=AgentActionKind.FINAL, message=message)

    def _fallback_consolidated_response(self, payload: dict[str, Any]) -> ConsolidatedResponse:
        language = str(payload.get("language", "en")).lower()
        processor_output = str(payload.get("processor_output", "")).strip()
        validator_output = str(payload.get("validator_output", "")).strip()

        if language == "es":
            synthesis = "Síntesis automática: se muestra la respuesta del Processor y la del Validator porque el proveedor no devolvió JSON estructurado en el paso final."
        else:
            synthesis = "Automatic synthesis: showing the Processor and Validator outputs because the provider did not return structured JSON in the final step."

        return ConsolidatedResponse(
            processor_view=processor_output or ("Sin salida del Processor." if language == "es" else "No Processor output."),
            validator_view=validator_output or ("Sin salida del Validator." if language == "es" else "No Validator output."),
            synthesis=synthesis,
        )

    def _summarize_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            summarized: dict[str, Any] = {}
            for key, value in payload.items():
                if key == "conversation" and isinstance(value, list):
                    summarized[key] = {
                        "count": len(value),
                        "last_kind": value[-1].get("kind") if value else None,
                    }
                    continue
                if key == "tool_results" and isinstance(value, list):
                    summarized[key] = {
                        "count": len(value),
                        "last_tool": value[-1].get("tool") if value else None,
                    }
                    continue
                if isinstance(value, str):
                    summarized[key] = value[:300]
                    continue
                summarized[key] = self._summarize_payload(value)
            return summarized
        if isinstance(payload, list):
            return [self._summarize_payload(item) for item in payload[:5]]
        return payload
