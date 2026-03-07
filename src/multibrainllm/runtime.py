from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from multibrainllm.config import ConfigManager
from multibrainllm.domain import (
    AgentActionKind,
    AgentResponse,
    AgentRole,
    ConsolidatedResponse,
    PendingClarification,
    PermissionMode,
    RuntimeStatus,
    SessionEvent,
    SessionEventKind,
    ToolResult,
    UserSettings,
)
from multibrainllm.i18n import Translator
from multibrainllm.prompts import build_agent_prompt
from multibrainllm.providers import ModelGateway
from multibrainllm.tools import ApprovalHandler, ToolBroker


class MultiBrainRuntime:
    def __init__(
        self,
        config_manager: ConfigManager,
        settings: UserSettings,
        profiles: dict[str, Any],
        translator: Translator,
        model_gateway: ModelGateway,
        tool_broker: ToolBroker,
        logger: logging.Logger,
    ) -> None:
        self.config_manager = config_manager
        self.settings = settings
        self.profiles = profiles
        self.translator = translator
        self.model_gateway = model_gateway
        self.tool_broker = tool_broker
        self.logger = logger
        self.history: list[SessionEvent] = []
        self.pending: PendingClarification | None = None
        self.approval_handler: ApprovalHandler | None = None
        self.session_file = self._new_session_file()
        self.turn_counter = 0
        self.logger.info(
            "runtime_initialized",
            extra={
                "language": self.settings.language,
                "permission_mode": self.settings.permission_mode.value,
                "default_profile": self.settings.default_profile,
                "agent_profiles": {role.value: profile for role, profile in self.settings.agent_profiles.items()},
                "session_file": str(self.session_file),
            },
        )

    def set_approval_handler(self, handler: ApprovalHandler) -> None:
        self.approval_handler = handler

    def set_language(self, language: str) -> None:
        self.translator.set_language(language)  # type: ignore[arg-type]
        self.settings.language = language  # type: ignore[assignment]
        self.config_manager.save_settings(self.settings)
        self.logger.info("settings_updated", extra={"field": "language", "value": language})

    def set_permission_mode(self, mode: PermissionMode) -> None:
        self.settings.permission_mode = mode
        self.config_manager.save_settings(self.settings)
        self.logger.info("settings_updated", extra={"field": "permission_mode", "value": mode.value})

    def set_reasoning_visibility(self, visible: bool) -> None:
        self.settings.show_reasoning = visible
        self.config_manager.save_settings(self.settings)
        self.logger.info("settings_updated", extra={"field": "show_reasoning", "value": visible})

    def set_default_profile(self, profile_id: str | None) -> None:
        self.settings.default_profile = profile_id
        self.config_manager.save_settings(self.settings)
        self.logger.info("settings_updated", extra={"field": "default_profile", "value": profile_id})

    def set_agent_profile(self, role: AgentRole, profile_id: str) -> None:
        self.settings.agent_profiles[role] = profile_id
        self.config_manager.save_settings(self.settings)
        self.logger.info(
            "settings_updated",
            extra={"field": "agent_profile", "role": role.value, "value": profile_id},
        )

    def reset_conversation(self) -> None:
        self.history = []
        self.pending = None
        self.session_file = self._new_session_file()
        self.logger.info("conversation_reset", extra={"session_file": str(self.session_file)})

    def status(self) -> RuntimeStatus:
        active_profiles = {
            role: self.settings.agent_profiles.get(role) or self.settings.default_profile
            for role in AgentRole
        }
        return RuntimeStatus(
            language=self.settings.language,
            permission_mode=self.settings.permission_mode,
            show_reasoning=self.settings.show_reasoning,
            default_profile=self.settings.default_profile,
            active_profiles=active_profiles,
            available_profiles=sorted(self.profiles.keys()),
            pending_clarification=self.pending is not None,
            logs_path=self.config_manager.paths.log_file,
            config_path=self.config_manager.paths.profiles_path,
        )

    async def submit_user_message(self, message: str) -> list[SessionEvent]:
        events: list[SessionEvent] = []
        self.turn_counter += 1
        turn_id = self.turn_counter
        self.logger.info(
            "turn_started",
            extra={
                "turn_id": turn_id,
                "has_pending": self.pending is not None,
                "message_preview": message[:500],
                "history_events": len(self.history),
                "session_file": str(self.session_file),
            },
        )
        self._emit(
            events,
            SessionEventKind.USER,
            self.translator.t("event.user"),
            message,
        )

        try:
            if self.pending is not None:
                await self._resume_pending(message, events)
            else:
                await self._run_full_turn(message, events)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("runtime_error", extra={"user_message": message})
            self._emit(
                events,
                SessionEventKind.SYSTEM,
                self.translator.t("event.error"),
                self.translator.t("system.error", error=str(exc)),
            )
        self.logger.info(
            "turn_finished",
            extra={
                "turn_id": turn_id,
                "events_emitted": len(events),
                "pending_after_turn": self.pending is not None,
            },
        )
        return events

    async def _run_full_turn(self, message: str, events: list[SessionEvent]) -> None:
        history = self._conversation_context()
        self.logger.debug(
            "full_turn_start",
            extra={
                "message_preview": message[:500],
                "conversation_events": len(history),
            },
        )
        processor_payload = {
            "user_message": message,
            "conversation": history,
            "language": self.settings.language,
        }
        processor_response = await self._drive_agent(
            role=AgentRole.PROCESSOR,
            base_payload=processor_payload,
            events=events,
        )
        if processor_response is None:
            return

        validator_payload = {
            "user_message": message,
            "processor_answer": processor_response.message,
            "conversation": history,
            "language": self.settings.language,
        }
        validator_response = await self._drive_agent(
            role=AgentRole.VALIDATOR,
            base_payload=validator_payload,
            events=events,
        )
        if validator_response is None:
            return

        await self._finalize_turn(
            message=message,
            processor_output=processor_response.message,
            validator_output=validator_response.message,
            events=events,
        )

    async def _resume_pending(self, answer: str, events: list[SessionEvent]) -> None:
        pending = self.pending
        if pending is None:
            return
        self.pending = None
        self.logger.info(
            "clarification_resumed",
            extra={
                "role": pending.role.value,
                "question": pending.question,
                "answer_preview": answer[:500],
                "prior_tool_results": len(pending.tool_results),
            },
        )

        clarifications = pending.clarification_answers + [answer]
        response = await self._drive_agent(
            role=pending.role,
            base_payload=pending.base_payload,
            events=events,
            prior_tool_results=pending.tool_results,
            clarification_answers=clarifications,
        )
        if response is None:
            return

        if pending.role == AgentRole.PROCESSOR:
            validator_payload = {
                "user_message": pending.base_payload["user_message"],
                "processor_answer": response.message,
                "conversation": self._conversation_context(),
                "language": self.settings.language,
            }
            validator_response = await self._drive_agent(
                role=AgentRole.VALIDATOR,
                base_payload=validator_payload,
                events=events,
            )
            if validator_response is None:
                return
            await self._finalize_turn(
                message=pending.base_payload["user_message"],
                processor_output=response.message,
                validator_output=validator_response.message,
                events=events,
            )
            return

        await self._finalize_turn(
            message=pending.base_payload["user_message"],
            processor_output=pending.base_payload["processor_answer"],
            validator_output=response.message,
            events=events,
        )

    async def _drive_agent(
        self,
        role: AgentRole,
        base_payload: dict[str, Any],
        events: list[SessionEvent],
        prior_tool_results: list[ToolResult] | None = None,
        clarification_answers: list[str] | None = None,
    ) -> AgentResponse | None:
        tool_results = list(prior_tool_results or [])
        clarifications = list(clarification_answers or [])

        for step_index in range(1, 6):
            payload = {
                **base_payload,
                "tool_results": [result.model_dump(mode="json") for result in tool_results],
                "clarification_answers": clarifications,
            }
            self.logger.debug(
                "agent_step_start",
                extra={
                    "role": role.value,
                    "step_index": step_index,
                    "tool_results_count": len(tool_results),
                    "clarifications_count": len(clarifications),
                    "payload_summary": self._summarize_payload(payload),
                },
            )
            invocation = await self.model_gateway.ainvoke(
                role=role,
                schema=AgentResponse,
                system_prompt=build_agent_prompt(role, self.settings.language),
                payload=payload,
            )
            response = invocation.parsed
            self.logger.info(
                "agent_response",
                extra={
                    "role": role.value,
                    "kind": response.kind.value,
                    "step_index": step_index,
                    "model_name": invocation.model_name,
                    "response": response.model_dump(mode="json"),
                },
            )
            if invocation.reasoning_summary or invocation.reasoning_tokens:
                self._emit_reasoning(events, role, invocation.reasoning_summary, invocation.reasoning_tokens, invocation.model_name)

            if response.kind == AgentActionKind.FINAL:
                return response

            if response.kind == AgentActionKind.ASK_USER:
                self.pending = PendingClarification(
                    role=role,
                    question=response.question or response.message,
                    base_payload=base_payload,
                    tool_results=tool_results,
                    clarification_answers=clarifications,
                )
                self.logger.info(
                    "clarification_requested",
                    extra={
                        "role": role.value,
                        "question": response.question or response.message,
                        "step_index": step_index,
                    },
                )
                title_key = "event.processor_question" if role == AgentRole.PROCESSOR else "event.validator_question"
                self._emit(
                    events,
                    SessionEventKind.CLARIFICATION,
                    self.translator.t(title_key),
                    response.question or response.message,
                    role=role,
                )
                return None

            if response.tool_request is None:
                raise RuntimeError(f"{role.value} requested a tool without payload")

            self._emit(
                events,
                SessionEventKind.TOOL,
                self.translator.t("event.tool_request"),
                self._tool_request_message(role.value, response.tool_request.tool, response.tool_request.reason),
                role=role,
                metadata=response.tool_request.model_dump(mode="json"),
            )
            self.logger.info(
                "tool_request",
                extra={
                    "role": role.value,
                    "step_index": step_index,
                    "request": response.tool_request.model_dump(mode="json"),
                },
            )
            result = await self.tool_broker.execute(
                response.tool_request,
                permission_mode=self.settings.permission_mode,
                approval_handler=self.approval_handler,
            )
            tool_results.append(result)
            self.logger.info(
                "tool_execution",
                extra={
                    "role": role.value,
                    "tool": response.tool_request.tool,
                    "step_index": step_index,
                    "success": result.success,
                    "output_preview": result.output[:800],
                    "error_preview": result.error[:800],
                    "metadata": result.metadata,
                },
            )
            title = (
                self.translator.t("event.tool_denied")
                if result.metadata.get("denied")
                else self.translator.t("event.tool_result")
            )
            body = result.output or result.error or self.translator.t("event.tool_no_output")
            self._emit(events, SessionEventKind.TOOL, title, body.strip(), role=role)

        raise RuntimeError(f"{role.value} exceeded the maximum number of internal steps")

    async def _finalize_turn(
        self,
        message: str,
        processor_output: str,
        validator_output: str,
        events: list[SessionEvent],
    ) -> None:
        self.logger.debug(
            "finalize_turn_start",
            extra={
                "message_preview": message[:500],
                "processor_output_preview": processor_output[:500],
                "validator_output_preview": validator_output[:500],
            },
        )
        final_invocation = await self.model_gateway.ainvoke(
            role=AgentRole.ORCHESTRATOR,
            schema=ConsolidatedResponse,
            system_prompt=build_agent_prompt(AgentRole.ORCHESTRATOR, self.settings.language),
            payload={
                "user_message": message,
                "processor_output": processor_output,
                "validator_output": validator_output,
                "conversation": self._conversation_context(),
                "language": self.settings.language,
            },
        )
        final = final_invocation.parsed
        self.logger.info(
            "orchestrator_finalized",
            extra={
                "model_name": final_invocation.model_name,
                "final_summary": self._summarize_payload(final.model_dump(mode="json")),
            },
        )
        if final_invocation.reasoning_summary or final_invocation.reasoning_tokens:
            self._emit_reasoning(
                events,
                AgentRole.ORCHESTRATOR,
                final_invocation.reasoning_summary,
                final_invocation.reasoning_tokens,
                final_invocation.model_name,
            )
        body = "\n\n".join(
            [
                f"{self.translator.t('final.processor_label')}\n{final.processor_view}",
                f"{self.translator.t('final.validator_label')}\n{final.validator_view}",
                f"{self.translator.t('final.synthesis_label')}\n{final.synthesis}",
            ]
        )
        self._emit(events, SessionEventKind.FINAL, self.translator.t("event.final"), body, role=AgentRole.ORCHESTRATOR)

    def _tool_request_message(self, role_name: str, tool: str, reason: str) -> str:
        return self.translator.t(
            "event.tool_request_body",
            role=role_name,
            tool=tool,
            reason=reason,
        )

    def _conversation_context(self) -> list[dict[str, Any]]:
        visible_kinds = {
            SessionEventKind.USER,
            SessionEventKind.CLARIFICATION,
            SessionEventKind.FINAL,
        }
        return [
            event.model_dump(mode="json")
            for event in self.history
            if event.kind in visible_kinds
        ]

    def _emit(
        self,
        collector: list[SessionEvent],
        kind: SessionEventKind,
        title: str,
        body: str,
        role: AgentRole | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = SessionEvent(kind=kind, title=title, body=body, role=role, metadata=metadata or {})
        collector.append(event)
        self.history.append(event)
        self.logger.debug(
            "event_emitted",
            extra={
                "kind": kind.value,
                "role": role.value if role else None,
                "title": title,
                "body_preview": body[:800],
                "metadata": metadata or {},
            },
        )
        self._persist_event(event)

    def _persist_event(self, event: SessionEvent) -> None:
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with self.session_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def _emit_reasoning(
        self,
        collector: list[SessionEvent],
        role: AgentRole,
        reasoning_summary: list[str],
        reasoning_tokens: int | None,
        model_name: str | None,
    ) -> None:
        title = self.translator.t(
            "event.reasoning_title",
            role=role.value,
            model=model_name or self.translator.t("status.none"),
            tokens=reasoning_tokens if reasoning_tokens is not None else "?",
        )
        body = "\n\n".join(reasoning_summary) if reasoning_summary else self.translator.t("event.reasoning_unavailable")
        self._emit(
            collector,
            SessionEventKind.REASONING,
            title,
            body,
            role=role,
            metadata={
                "reasoning_tokens": reasoning_tokens,
                "model_name": model_name,
            },
        )

    def _new_session_file(self) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return Path(self.config_manager.paths.sessions_dir) / f"session-{timestamp}.jsonl"

    def _summarize_payload(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            summarized: dict[str, Any] = {}
            for key, value in payload.items():
                if isinstance(value, str):
                    summarized[key] = value[:300]
                elif isinstance(value, list):
                    summarized[key] = {
                        "count": len(value),
                        "preview": value[:2],
                    }
                else:
                    summarized[key] = value
            return summarized
        return payload
