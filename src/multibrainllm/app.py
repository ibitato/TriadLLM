from __future__ import annotations

import shlex

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from multibrainllm.config import ConfigManager
from multibrainllm.domain import AgentRole, PermissionMode, SessionEvent, SessionEventKind, ToolRequest
from multibrainllm.i18n import Translator
from multibrainllm.runtime import MultiBrainRuntime


class PermissionScreen(ModalScreen[bool]):
    CSS = """
    Screen {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #permission-dialog {
        width: 70;
        padding: 1 2;
        border: round #ff9f1c;
        background: #111111;
    }

    #permission-actions {
        height: auto;
        margin-top: 1;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, request: ToolRequest, translator: Translator) -> None:
        super().__init__()
        self.request = request
        self.translator = translator

    def compose(self) -> ComposeResult:
        summary = self.translator.t(
            "permission.summary",
            tool=self.request.tool,
            reason=self.request.reason,
            risk=self.request.risk.value,
            args=self.request.arguments,
        )
        with Container(id="permission-dialog"):
            yield Static(self.translator.t("permission.title"), classes="modal-title")
            yield Static(summary)
            with Horizontal(id="permission-actions"):
                yield Button(self.translator.t("permission.deny"), id="deny")
                yield Button(self.translator.t("permission.approve"), id="approve", variant="success")

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve")


class ChatBlock(Static):
    def __init__(self, title: str, body: str, kind: str) -> None:
        super().__init__(body, classes=f"chat-block {kind}")
        self.kind = kind
        self.border_title = title


class MultiBrainApp(App[None]):
    CSS = """
    Screen {
        background: #0a0f0d;
        color: #b6ff7a;
    }

    #root {
        height: 100%;
        layout: vertical;
        padding: 1;
    }

    #titlebar {
        height: 1;
        min-height: 1;
        margin: 0 1 1 1;
        content-align: left middle;
        color: #ff9f1c;
        text-style: bold;
    }

    #transcript {
        height: 1fr;
        min-height: 8;
        margin: 0 1;
        border: round #1f6f46;
        padding: 1;
        background: #050806;
    }

    #composer-row {
        height: 3;
        min-height: 3;
        margin: 1 1 0 1;
        width: 100%;
    }

    #composer {
        width: 1fr;
        min-width: 20;
        border: round #1f6f46;
        background: #111111;
        color: #f2ffd4;
    }

    #send {
        width: 10;
        margin-left: 1;
        background: #ff9f1c;
        color: #111111;
    }

    #statusbar {
        height: 1;
        min-height: 1;
        margin: 1 1 0 1;
        color: #ffcf70;
        content-align: left middle;
        text-overflow: ellipsis;
        width: 100%;
    }

    .chat-block {
        width: 100%;
        margin-bottom: 1;
        padding: 0 1;
        border: round #1f6f46;
        background: #101612;
    }

    .user {
        border: round #b6ff7a;
    }

    .system {
        border: round #ff9f1c;
    }

    .tool {
        border: round #ffc857;
    }

    .reasoning {
        border: round #7bdff2;
        color: #7bdff2;
        text-style: italic dim;
    }

    .clarification {
        border: round #f77f00;
    }

    .final {
        border: round #2ec4b6;
    }

    .is-hidden {
        display: none;
    }

    .status-value {
        text-style: bold;
    }
    """

    def __init__(
        self,
        runtime: MultiBrainRuntime,
        translator: Translator,
        config_manager: ConfigManager,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.translator = translator
        self.config_manager = config_manager
        self.busy = False

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            yield Static(id="titlebar")
            yield VerticalScroll(id="transcript")
            with Horizontal(id="composer-row"):
                yield Input(placeholder="", id="composer")
                yield Button("", id="send")
            yield Static(id="statusbar")

    async def on_mount(self) -> None:
        self.runtime.set_approval_handler(self._prompt_permission)
        self._refresh_chrome()
        self.query_one("#composer", Input).focus()
        await self._add_block(
            self.translator.t("event.system"),
            self.translator.t("app.welcome"),
            "system",
        )
        self._apply_reasoning_visibility()
        self._refresh_status()

    @on(Input.Submitted)
    async def handle_submit(self, event: Input.Submitted) -> None:
        await self._dispatch_input(event.value)

    @on(Button.Pressed, "#send")
    async def handle_send(self) -> None:
        composer = self.query_one("#composer", Input)
        await self._dispatch_input(composer.value)

    async def _dispatch_input(self, raw: str) -> None:
        text = raw.strip()
        if not text or self.busy:
            return

        composer = self.query_one("#composer", Input)
        composer.value = ""

        if text.startswith("/"):
            await self._handle_command(text)
            return

        self.busy = True
        self._refresh_status()
        try:
            events = await self.runtime.submit_user_message(text)
            for event in events:
                await self._render_event(event)
        finally:
            self.busy = False
            self._refresh_status()

    async def _handle_command(self, raw: str) -> None:
        parts = shlex.split(raw)
        command = parts[0].lower()
        args = parts[1:]

        if command == "/help":
            body = self.translator.t("slash.help")
        elif command == "/status":
            status = self.runtime.status()
            body = self.translator.t(
                "slash.status",
                language=status.language,
                permission=status.permission_mode.value,
                default_profile=status.default_profile or self.translator.t("status.none"),
                pending=status.pending_clarification,
                log_file=status.logs_path,
            )
        elif command == "/config":
            snapshot = self.config_manager.config_snapshot(self.runtime.settings, self.runtime.profiles)
            body = self.translator.t("slash.config", snapshot=snapshot)
        elif command == "/permissions":
            if not args or args[0] not in {"ask", "yolo"}:
                body = self.translator.t("slash.permissions.invalid")
            else:
                self.runtime.set_permission_mode(PermissionMode(args[0]))
                body = self.translator.t("slash.permissions.changed", mode=args[0])
        elif command == "/lang":
            if not args or args[0] not in {"es", "en"}:
                body = self.translator.t("slash.lang.invalid")
            else:
                self.runtime.set_language(args[0])
                self._refresh_chrome()
                body = self.translator.t("slash.lang.changed", language=args[0])
        elif command == "/models":
            status = self.runtime.status()
            body = "\n\n".join(
                [
                    self.translator.t(
                        "slash.models",
                        profiles=", ".join(status.available_profiles) or self.translator.t("status.none"),
                        orchestrator=self._describe_profile(status.active_profiles[AgentRole.ORCHESTRATOR]),
                        processor=self._describe_profile(status.active_profiles[AgentRole.PROCESSOR]),
                        validator=self._describe_profile(status.active_profiles[AgentRole.VALIDATOR]),
                    )
                ]
            )
        elif command == "/model":
            body = await self._handle_model_command(args)
        elif command == "/tools":
            body = self.translator.t("slash.tools", tools=", ".join(self.runtime.tool_broker.available_tools()))
        elif command == "/reasoning":
            if not args or args[0] not in {"on", "off"}:
                body = self.translator.t("slash.reasoning.invalid")
            else:
                visible = args[0] == "on"
                self.runtime.set_reasoning_visibility(visible)
                self._apply_reasoning_visibility()
                body = self.translator.t("slash.reasoning.changed", state=args[0])
        elif command == "/new":
            self.runtime.reset_conversation()
            self.query_one("#transcript", VerticalScroll).remove_children()
            await self._add_block(
                self.translator.t("event.system"),
                self.translator.t("app.welcome"),
                "system",
            )
            body = self.translator.t("slash.new")
        elif command == "/clear":
            self.query_one("#transcript", VerticalScroll).remove_children()
            body = self.translator.t("slash.clear")
        elif command == "/quit":
            self.exit()
            return
        else:
            body = self.translator.t("slash.unknown", command=command)

        await self._add_block(self.translator.t("event.system"), body, "system")
        self._refresh_status()

    async def _handle_model_command(self, args: list[str]) -> str:
        if len(args) != 3 or args[0] != "set":
            return self.translator.t("slash.model.invalid")
        role_raw = args[1].lower()
        profile_id = args[2]
        try:
            role = AgentRole(role_raw)
        except ValueError:
            return self.translator.t("slash.model.invalid")
        if profile_id not in self.runtime.profiles:
            return self.translator.t("slash.model.missing", profile=profile_id)
        self.runtime.set_agent_profile(role, profile_id)
        if self.runtime.settings.default_profile is None:
            self.runtime.set_default_profile(profile_id)
        return self.translator.t("slash.model.changed", role=role.value, profile=profile_id)

    async def _render_event(self, event: SessionEvent) -> None:
        kind_map = {
            SessionEventKind.USER: "user",
            SessionEventKind.SYSTEM: "system",
            SessionEventKind.TOOL: "tool",
            SessionEventKind.REASONING: "reasoning",
            SessionEventKind.CLARIFICATION: "clarification",
            SessionEventKind.FINAL: "final",
        }
        await self._add_block(event.title, event.body, kind_map[event.kind])

    async def _add_block(self, title: str, body: str, kind: str) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        block = ChatBlock(title, body, kind)
        await transcript.mount(block)
        if kind == "reasoning" and not self.runtime.settings.show_reasoning:
            block.add_class("is-hidden")
        transcript.scroll_end(animate=False)

    def _refresh_chrome(self) -> None:
        self.query_one("#titlebar", Static).update(self.translator.t("app.title"))
        self.query_one("#composer", Input).placeholder = self.translator.t("input.placeholder")
        self.query_one("#send", Button).label = self.translator.t("button.send")
        self.title = self.translator.t("app.title")
        self.sub_title = "Multi-agent terminal"
        self._apply_reasoning_visibility()
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self.runtime.status()
        state = self.translator.t("status.busy") if self.busy else self.translator.t("status.ready")
        default_profile = status.default_profile or self.translator.t("status.none")
        if len(default_profile) > 28:
            default_profile = f"{default_profile[:25]}..."
        self.query_one("#statusbar", Static).update(
            self.translator.t(
                "status.line",
                state=state,
                language=status.language,
                permission=status.permission_mode.value,
                profile=default_profile,
                reasoning=self.translator.t("status.on") if status.show_reasoning else self.translator.t("status.off"),
            )
        )

    async def _prompt_permission(self, request: ToolRequest) -> bool:
        return await self.push_screen_wait(PermissionScreen(request, self.translator))

    def _apply_reasoning_visibility(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        for child in transcript.children:
            if isinstance(child, ChatBlock) and child.kind == "reasoning":
                child.set_class(not self.runtime.settings.show_reasoning, "is-hidden")

    def _describe_profile(self, profile_id: str | None) -> str:
        if profile_id is None:
            return self.translator.t("status.none")
        profile = self.runtime.profiles.get(profile_id)
        if profile is None:
            return profile_id
        details = [
            f"id={profile.id}",
            f"provider={profile.provider.value if profile.provider else 'auto'}",
            f"model={profile.model}",
            f"temp={profile.temperature}",
        ]
        if profile.context_window is not None:
            details.append(f"context={profile.context_window}")
        if profile.max_output_tokens_limit is not None:
            details.append(f"max_output={profile.max_output_tokens_limit}")
        if profile.reasoning_effort is not None:
            details.append(f"effort={profile.reasoning_effort}")
        if profile.reasoning_summary is not None:
            details.append(f"summary={profile.reasoning_summary}")
        return ", ".join(details)
