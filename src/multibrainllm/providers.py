from __future__ import annotations

import json
import os
from typing import Any, Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from multibrainllm.domain import AgentRole, ProviderProfile, UserSettings

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ModelGateway(Protocol):
    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> SchemaT:
        ...


class LangChainGateway:
    def __init__(self, profiles: dict[str, ProviderProfile], settings: UserSettings) -> None:
        self.profiles = profiles
        self.settings = settings
        self._clients: dict[str, ChatOpenAI] = {}

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

    async def ainvoke(
        self,
        role: AgentRole,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> SchemaT:
        profile = self.profile_for_role(role)
        client = self._get_client(profile)
        runnable = client.with_structured_output(schema)
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        result = await runnable.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content),
            ]
        )
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)
