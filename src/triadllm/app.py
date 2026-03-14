from __future__ import annotations

import shlex
from collections import deque

from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import CenterMiddle, Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.worker import Worker
from textual.widgets import Button, Static, TextArea, Markdown

from triadllm.config import ConfigManager
from triadllm.domain import AgentRole, PermissionMode, SessionEvent, SessionEventKind, ToolRequest
from triadllm.i18n import Translator
from triadllm.runtime import TriadRuntime

SPLASH_ART = r"""
████████╗██████╗ ██╗ █████╗ ██████╗ ██╗     ██╗     ███╗   ███╗
╚══██╔══╝██╔══██╗██║██╔══██╗██╔══██╗██║     ██║     ████╗ ████║
   ██║   ██████╔╝██║███████║██║  ██║██║     ██║     ██╔████╔██║
   ██║   ██╔══██╗██║██╔══██║██║  ██║██║     ██║     ██║╚██╔╝██║
   ██║   ██║  ██║██║██║  ██║██████╔╝███████╗███████╗██║ ╚═╝ ██║
   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═╝     ╚═╝
"""
SPLASH_ART_WIDTH = 63
SPLASH_DIALOG_WIDTH = 72


class SplashScreen(ModalScreen[None]):
    CSS = """
    SplashScreen {
        background: rgba(0, 0, 0, 0.88);
    }

    CenterMiddle {
        width: 100%;
        height: 100%;
    }

    #splash-dialog {
        width: 72;
        height: auto;
        padding: 1 2;
        border: round #1f6f46;
        background: #09100c;
    }

    #splash-art {
        width: 63;
        height: 6;
        color: #ff9f1c;
        text-style: bold;
        content-align: center middle;
    }

    #splash-tagline {
        margin-top: 1;
        color: #b6ff7a;
        width: 100%;
        content-align: center middle;
    }

    #splash-help {
        margin-top: 1;
        color: #ffcf70;
        width: 100%;
        content-align: center middle;
    }
    """

    def __init__(self, translator: Translator, timeout_seconds: float) -> None:
        super().__init__()
        self.translator = translator
        self.timeout_seconds = timeout_seconds
        self._dismissed = False

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Container(id="splash-dialog"):
                yield Static(SPLASH_ART.strip("\n"), id="splash-art")
                yield Static(self.translator.t("splash.tagline"), id="splash-tagline")
                yield Static(self.translator.t("splash.help"), id="splash-help")

    def on_mount(self) -> None:
        self.set_timer(self.timeout_seconds, self._close)

    def on_key(self, event: events.Key) -> None:
        event.stop()
        self._close()

    def _close(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self.dismiss(None)


class PermissionScreen(ModalScreen[bool]):
    BINDINGS = [
        ("escape", "deny", "Deny"),
        ("q", "deny", "Deny"),
        ("d", "deny", "Deny"),
        ("a", "approve", "Approve"),
        ("enter", "approve", "Approve"),
    ]

    CSS = """
    PermissionScreen {
        background: rgba(0, 0, 0, 0.75);
    }

    CenterMiddle {
        width: 100%;
        height: 100%;
    }

    #permission-dialog {
        width: 74;
        padding: 1 2;
        border: round #ff9f1c;
        background: #111111;
    }

    #permission-actions {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    #permission-help {
        margin-top: 1;
        color: #ffcf70;
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
        with CenterMiddle():
            with Container(id="permission-dialog"):
                yield Static(self.translator.t("permission.title"), classes="modal-title")
                yield Static(summary)
                yield Static(self.translator.t("permission.help"), id="permission-help")
                with Horizontal(id="permission-actions"):
                    yield Button(self.translator.t("permission.deny"), id="deny")
                    yield Button(self.translator.t("permission.approve"), id="approve", variant="success")

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_approve)

    def _focus_approve(self) -> None:
        self.query_one("#approve", Button).focus()

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        self._finish(event.button.id == "approve")

    def action_approve(self) -> None:
        self._finish(True)

    def action_deny(self) -> None:
        self._finish(False)

    def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        if key in {"enter", "a"}:
            event.stop()
            self._finish(True)
            return
        if key in {"escape", "q", "d"}:
            event.stop()
            self._finish(False)

    def _finish(self, approved: bool) -> None:
        if self.is_active:
            self.dismiss(approved)


class ComposerArea(TextArea):
    class SubmitRequested(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class ExpandRequested(Message):
        pass

    def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        if key == "enter":
            event.stop()
            self.post_message(self.SubmitRequested(self.text))
            return
        if key == "ctrl+j":
            event.stop()
            self.insert("\n")
            return
        if key == "ctrl+e":
            event.stop()
            self.post_message(self.ExpandRequested())


class EditorScreen(ModalScreen[str | None]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "send", "Send"),
    ]

    CSS = """
    EditorScreen {
        background: rgba(0, 0, 0, 0.82);
    }

    CenterMiddle {
        width: 100%;
        height: 100%;
    }

    #editor-dialog {
        width: 88%;
        height: 88%;
        padding: 1 2;
        border: round #1f6f46;
        background: #0b0f0c;
    }

    #editor-title {
        color: #ff9f1c;
        text-style: bold;
    }

    #editor-body {
        height: 1fr;
        margin-top: 1;
    }

    #editor-composer {
        height: 1fr;
        border: round #1f6f46;
        background: #111111;
        color: #f2ffd4;
    }

    #editor-help {
        margin-top: 1;
        color: #ffcf70;
    }

    #editor-actions {
        height: auto;
        margin-top: 1;
        align: right middle;
    }

    #editor-actions Button {
        margin-left: 1;
    }
    """

    def __init__(self, initial_text: str, translator: Translator) -> None:
        super().__init__()
        self.initial_text = initial_text
        self.translator = translator

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Container(id="editor-dialog"):
                yield Static(self.translator.t("editor.title"), id="editor-title")
                with Container(id="editor-body"):
                    yield TextArea(
                        self.initial_text,
                        id="editor-composer",
                        soft_wrap=True,
                        show_line_numbers=False,
                        placeholder=self.translator.t("editor.placeholder"),
                    )
                yield Static(self.translator.t("editor.help"), id="editor-help")
                with Horizontal(id="editor-actions"):
                    yield Button(self.translator.t("editor.cancel"), id="cancel")
                    yield Button(self.translator.t("editor.send"), id="send", variant="success")

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_editor)

    def _focus_editor(self) -> None:
        editor = self.query_one("#editor-composer", TextArea)
        editor.focus()

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            self.action_send()
        else:
            self.action_cancel()

    def action_send(self) -> None:
        self.dismiss(self.query_one("#editor-composer", TextArea).text)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfigEditorScreen(ModalScreen[str | None]):
    """Interactive configuration editor screen."""
    
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]

    CSS = """
    ConfigEditorScreen {
        background: rgba(0, 0, 0, 0.85);
    }

    CenterMiddle {
        width: 100%;
        height: 100%;
    }

    #config-editor-dialog {
        width: 80;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: round #ff9f1c;
        background: #0b0f0c;
    }

    #config-title {
        color: #ff9f1c;
        text-style: bold;
    }

    #config-body {
        height: 1fr;
        min-height: 20;
        margin-top: 1;
        overflow-y: auto;
    }

    #config-field {
        margin-bottom: 1;
    }

    #config-label {
        color: #b6ff7a;
        text-style: bold;
    }

    #config-input {
        width: 100%;
        min-height: 3;
        background: #111111;
        color: #f2ffd4;
        border: round #1f6f46;
    }

    #config-actions {
        height: auto;
        margin-top: 1;
        align: right middle;
    }

    #config-actions Button {
        margin-left: 1;
    }
    """

    def __init__(self, settings: dict, profiles: dict, translator: Translator) -> None:
        super().__init__()
        self.settings = settings
        self.profiles = profiles
        self.translator = translator
        self.current_values = settings.copy()
        self.validation_errors = {}

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Container(id="config-editor-dialog"):
                yield Static(self.translator.t("config_editor.title"), id="config-title")
                yield Static(self.translator.t("config_editor.instructions"), id="config-instructions")
                
                with VerticalScroll(id="config-body"):
                    # Language field
                    with Container(id="config-field-language"):
                        yield Static("Language:", id="config-label")
                        self.language_input = TextArea(
                            str(self.current_values.get("language", "")),
                            id="config-input-language",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.language_input
                        self.language_error = Static("", id="config-error-language")
                        yield self.language_error
                    
                    # Permission mode field
                    with Container(id="config-field-permission"):
                        yield Static("Permission Mode:", id="config-label")
                        self.permission_input = TextArea(
                            str(self.current_values.get("permission_mode", "")),
                            id="config-input-permission",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.permission_input
                        self.permission_error = Static("", id="config-error-permission")
                        yield self.permission_error
                    
                    # Show reasoning field
                    with Container(id="config-field-reasoning"):
                        yield Static("Show Reasoning:", id="config-label")
                        self.reasoning_input = TextArea(
                            str(self.current_values.get("show_reasoning", "")),
                            id="config-input-reasoning",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.reasoning_input
                        self.reasoning_error = Static("", id="config-error-reasoning")
                        yield self.reasoning_error
                    
                    # Show tool results field
                    with Container(id="config-field-toolresults"):
                        yield Static("Show Tool Results:", id="config-label")
                        self.toolresults_input = TextArea(
                            str(self.current_values.get("show_tool_results", "")),
                            id="config-input-toolresults",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.toolresults_input
                        self.toolresults_error = Static("", id="config-error-toolresults")
                        yield self.toolresults_error
                    
                    # Default profile field
                    with Container(id="config-field-profile"):
                        yield Static("Default Profile:", id="config-label")
                        self.profile_input = TextArea(
                            str(self.current_values.get("default_profile", "")),
                            id="config-input-profile",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.profile_input
                        self.profile_error = Static("", id="config-error-profile")
                        yield self.profile_error
                
                with Horizontal(id="config-actions"):
                    yield Button(self.translator.t("config_editor.cancel"), id="cancel", variant="default")
                    yield Button(self.translator.t("config_editor.save"), id="save", variant="success")

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_first_field)

    def _focus_first_field(self) -> None:
        self.language_input.focus()

    def _validate_all(self) -> bool:
        """Validate all fields and return True if all are valid."""
        self.validation_errors = {}
        
        # Validate language
        language = self.language_input.text.strip()
        if language not in ["en", "es"]:
            self.validation_errors["language"] = self.translator.t("config_editor.error.language")
            self.language_error.update(self.validation_errors["language"])
        else:
            self.language_error.update("")
            self.current_values["language"] = language
        
        # Validate permission mode
        permission = self.permission_input.text.strip()
        if permission not in ["ask", "yolo"]:
            self.validation_errors["permission_mode"] = self.translator.t("config_editor.error.permission")
            self.permission_error.update(self.validation_errors["permission_mode"])
        else:
            self.permission_error.update("")
            self.current_values["permission_mode"] = permission
        
        # Validate boolean fields
        for field_name, input_field, error_field in [
            ("show_reasoning", self.reasoning_input, self.reasoning_error),
            ("show_tool_results", self.toolresults_input, self.toolresults_error)
        ]:
            value = input_field.text.strip().lower()
            if value not in ["true", "false"]:
                self.validation_errors[field_name] = self.translator.t("config_editor.error.boolean")
                error_field.update(self.validation_errors[field_name])
            else:
                error_field.update("")
                self.current_values[field_name] = value == "true"
        
        # Validate default profile
        profile = self.profile_input.text.strip()
        if profile and profile not in self.profiles:
            self.validation_errors["default_profile"] = self.translator.t("config_editor.error.profile", profile=profile)
            self.profile_error.update(self.validation_errors["default_profile"])
        else:
            self.profile_error.update("")
            self.current_values["default_profile"] = profile if profile else None
        
        return len(self.validation_errors) == 0

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def action_save(self) -> None:
        if self._validate_all():
            self.dismiss(self.current_values)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.action_cancel()
        elif event.key == "ctrl+s":
            event.stop()
            self.action_save()


class ChatBlock(Static):
    def __init__(self, title: str, body: str, kind: str) -> None:
        super().__init__(body, classes=f"chat-block {kind}")
        self.kind = kind
        self.border_title = title


class MarkdownChatBlock(Markdown):
    def __init__(self, title: str, body: str, kind: str) -> None:
        super().__init__(body, classes=f"chat-block {kind}")
        self.kind = kind
        self.border_title = title


class TriadApp(App[None]):
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

    #transcript {
        height: 1fr;
        min-height: 8;
        margin: 0 1;
        border: round #1f6f46;
        padding: 1;
        background: #050806;
    }

    #composer-row {
        height: 5;
        min-height: 5;
        margin: 1 1 0 1;
        width: 100%;
        align: center middle;
    }

    #composer {
        width: 1fr;
        min-width: 20;
        height: 5;
        border: round #1f6f46;
        background: #111111;
        color: #f2ffd4;
    }

    #send {
        width: 10;
        height: 5;
        margin-left: 1;
        background: #ff9f1c;
        color: #111111;
    }

    #cancel-turn {
        width: 10;
        height: 5;
        margin-left: 1;
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
        runtime: TriadRuntime,
        translator: Translator,
        config_manager: ConfigManager,
        *,
        show_splash: bool = True,
        splash_timeout: float = 5.0,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.translator = translator
        self.config_manager = config_manager
        self.busy = False
        self.pending_inputs: deque[str] = deque()
        self.turn_worker: Worker[None] | None = None
        self.show_splash = show_splash
        self.splash_timeout = splash_timeout

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            yield VerticalScroll(id="transcript")
            with Horizontal(id="composer-row"):
                yield ComposerArea(
                    "",
                    id="composer",
                    soft_wrap=True,
                    show_line_numbers=False,
                    compact=True,
                    highlight_cursor_line=False,
                    placeholder="",
                )
                yield Button("", id="send")
                yield Button("", id="cancel-turn")
            yield Static(id="statusbar")

    async def on_mount(self) -> None:
        self.runtime.set_approval_handler(self._prompt_permission)
        self._refresh_chrome()
        self.query_one("#composer", ComposerArea).focus()
        await self._add_block(
            self.translator.t("event.system"),
            self.translator.t("app.welcome"),
            "system",
        )
        if not self.runtime.profiles:
            await self._add_block(
                self.translator.t("event.system"),
                self.translator.t(
                    "app.no_profiles",
                    sample=self.config_manager.sample_profiles_path(),
                    target=self.config_manager.paths.profiles_path,
                ),
                "system",
            )
        if self.show_splash:
            self.push_screen(
                SplashScreen(self.translator, timeout_seconds=self.splash_timeout),
                callback=lambda _: self.query_one("#composer", ComposerArea).focus(),
            )
        self._apply_visibility_settings()
        self._refresh_status()

    @on(ComposerArea.SubmitRequested)
    async def handle_submit(self, event: ComposerArea.SubmitRequested) -> None:
        await self._dispatch_input(event.text)

    @on(ComposerArea.ExpandRequested)
    def handle_expand_request(self, event: ComposerArea.ExpandRequested) -> None:
        event.stop()
        composer = self.query_one("#composer", ComposerArea)

        def handle_result(result: str | None) -> None:
            composer.focus()
            if result is None:
                return
            composer.load_text(result)
            self.run_worker(
                self._dispatch_input(result),
                name="editor-submit",
                group="editor-submit",
                exclusive=True,
                exit_on_error=False,
                thread=False,
            )

        self.push_screen(EditorScreen(composer.text, self.translator), callback=handle_result)

    @on(Button.Pressed, "#send")
    async def handle_send(self) -> None:
        composer = self.query_one("#composer", ComposerArea)
        await self._dispatch_input(composer.text)

    @on(Button.Pressed, "#cancel-turn")
    async def handle_cancel_turn(self) -> None:
        await self._cancel_active_turn()

    async def _dispatch_input(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return

        if self.busy and not text.startswith("/"):
            composer = self.query_one("#composer", ComposerArea)
            composer.load_text("")
            self.pending_inputs.append(text)
            await self._add_block(
                self.translator.t("event.system"),
                self.translator.t("queue.enqueued", count=len(self.pending_inputs)),
                "system",
            )
            self.runtime.logger.info(
                "message_queued",
                extra={"queued_count": len(self.pending_inputs), "message_preview": text[:500]},
            )
            self._refresh_status()
            return

        composer = self.query_one("#composer", ComposerArea)
        composer.load_text("")

        if text.startswith("/"):
            await self._handle_command(text)
            return

        self._start_turn_worker(text)

    async def _run_user_turn(self, text: str) -> None:
        try:
            events = await self.runtime.submit_user_message(text)
            for event in events:
                await self._render_event(event)
        except Exception as exc:  # noqa: BLE001
            self.runtime.logger.exception("app_turn_worker_error", extra={"message": text})
            await self._add_block(
                self.translator.t("event.error"),
                self.translator.t("system.error", error=str(exc)),
                "system",
            )
        finally:
            self.busy = False
            self.turn_worker = None
            self._refresh_status()
            self.call_after_refresh(self._start_next_queued_turn)

    async def _handle_command(self, raw: str) -> None:
        parts = shlex.split(raw)
        command = parts[0].lower()
        args = parts[1:]
        
        self.runtime.logger.debug("command_received", extra={"raw": raw, "command": command, "cmd_args": args})

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
            self.runtime.logger.debug("config_command_check", extra={"cmd_args": args, "has_args": bool(args), "first_arg": args[0] if args else None})
            if args and args[0] == "edit":
                # Open interactive configuration editor
                self.runtime.logger.info("config_edit_command_received")
                settings_dict = self.runtime.settings.model_dump()
                # Convert enum to string for editing
                if "permission_mode" in settings_dict and hasattr(settings_dict["permission_mode"], "value"):
                    settings_dict["permission_mode"] = settings_dict["permission_mode"].value
                profiles = self.runtime.profiles
                
                async def handle_edit_result(result: str | None) -> None:
                    if result is None:
                        # User cancelled
                        body = self.translator.t("config_editor.cancelled")
                    else:
                        # User saved changes
                        try:
                            # Update runtime settings
                            if "language" in result:
                                self.runtime.set_language(result["language"])
                            if "permission_mode" in result:
                                self.runtime.set_permission_mode(result["permission_mode"])
                            if "show_reasoning" in result:
                                self.runtime.set_reasoning_visibility(result["show_reasoning"])
                            if "show_tool_results" in result:
                                self.runtime.set_tool_results_visibility(result["show_tool_results"])
                            if "default_profile" in result and result["default_profile"]:
                                self.runtime.set_default_profile(result["default_profile"])
                            
                            # Save settings to disk
                            self.config_manager.save_settings(self.runtime.settings)
                            
                            # Show success message
                            body = self.translator.t("config_editor.saved")
                            
                            # Refresh UI if language changed
                            if "language" in result:
                                self._refresh_chrome()
                        except Exception as e:
                            body = self.translator.t("config_editor.error.save", error=str(e))
                    
                    await self._add_block(
                        self.translator.t("event.system"),
                        body,
                        "system"
                    )
                    self._refresh_status()
                
                # Push the editor screen
                try:
                    self.runtime.logger.info("config_edit_screen_pushed")
                    self.push_screen(
                        ConfigEditorScreen(settings_dict, profiles, self.translator),
                        callback=handle_edit_result
                    )
                    self.runtime.logger.info("config_edit_screen_push_complete")
                except Exception as e:
                    self.runtime.logger.exception("config_edit_screen_creation_failed", extra={"error": str(e)})
                    body = self.translator.t("config_editor.error.screen_creation", error=str(e))
                    await self._add_block(
                        self.translator.t("event.system"),
                        body,
                        "system"
                    )
                return
            else:
                # Regular /config command - show config summary
                snapshot = self.config_manager.config_snapshot(self.runtime.settings, self.runtime.profiles)
                paths_dict = snapshot["paths"]
                settings = snapshot["settings"]
                profiles_data = snapshot["profiles"]
                body = self.translator.t(
                    "slash.config",
                    paths_config_dir=paths_dict["config_dir"],
                    paths_settings_path=paths_dict["settings_path"],
                    paths_logs_path=paths_dict["log_dir"],
                    paths_sessions_path=paths_dict["sessions_dir"],
                    paths_profiles_path=paths_dict["profiles_path"],
                    settings_language=settings["language"],
                    settings_permission_mode=settings["permission_mode"],
                    settings_show_reasoning=settings["show_reasoning"],
                    settings_show_tool_results=settings["show_tool_results"],
                    settings_default_profile=settings.get("default_profile", "None"),
                    profiles_count=len(profiles_data),
                    sample_profiles=snapshot["sample_profiles"],
                )
                await self._add_block(
                    self.translator.t("event.system"),
                    body,
                    "system"
                )
                self._refresh_status()
                return
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
                self._apply_visibility_settings()
                body = self.translator.t("slash.reasoning.changed", state=args[0])
        elif command == "/toolresults":
            if not args or args[0] not in {"on", "off"}:
                body = self.translator.t("slash.toolresults.invalid")
            else:
                visible = args[0] == "on"
                self.runtime.set_tool_results_visibility(visible)
                self._apply_visibility_settings()
                body = self.translator.t("slash.toolresults.changed", state=args[0])
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
        elif command == "/cancel":
            cancelled = await self._cancel_active_turn()
            body = self.translator.t("slash.cancel.changed" if cancelled else "slash.cancel.idle")
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
        
        # Use Markdown widget for help messages (contains markdown formatting)
        if "**" in body or "#" in body:
            block = MarkdownChatBlock(title, body, kind)
        else:
            block = ChatBlock(title, body, kind)
        
        await transcript.mount(block)
        if kind == "reasoning" and not self.runtime.settings.show_reasoning:
            block.add_class("is-hidden")
        if kind == "tool" and not self.runtime.settings.show_tool_results:
            block.add_class("is-hidden")
        transcript.scroll_end(animate=False)

    def _refresh_chrome(self) -> None:
        self.query_one("#composer", ComposerArea).placeholder = self.translator.t("input.placeholder")
        self.query_one("#send", Button).label = self.translator.t("button.send")
        self.query_one("#cancel-turn", Button).label = self.translator.t("button.cancel")
        self.title = self.translator.t("app.title")
        self.sub_title = "Multi-agent terminal"
        self._apply_visibility_settings()
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self.runtime.status()
        state = self.translator.t("status.busy") if self.busy else self.translator.t("status.ready")
        default_profile = status.default_profile or self.translator.t("status.none")
        if len(default_profile) > 28:
            default_profile = f"{default_profile[:25]}..."
        cancel_button = self.query_one("#cancel-turn", Button)
        cancel_button.disabled = not self.busy
        self.query_one("#statusbar", Static).update(
            self.translator.t(
                "status.line",
                state=state,
                language=status.language,
                permission=status.permission_mode.value,
                profile=default_profile,
                reasoning=self.translator.t("status.on") if status.show_reasoning else self.translator.t("status.off"),
                tools=self.translator.t("status.on") if status.show_tool_results else self.translator.t("status.off"),
                queued=len(self.pending_inputs),
            )
        )

    async def _prompt_permission(self, request: ToolRequest) -> bool:
        self.runtime.logger.info(
            "permission_prompt_shown",
            extra={
                "tool": request.tool,
                "risk": request.risk.value,
                "arguments": request.arguments,
                "reason": request.reason,
            },
        )
        approved = bool(await self.push_screen_wait(PermissionScreen(request, self.translator)))
        self.runtime.logger.info(
            "permission_prompt_resolved",
            extra={
                "tool": request.tool,
                "approved": approved,
            },
        )
        return approved

    def _apply_visibility_settings(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        for child in transcript.children:
            if isinstance(child, ChatBlock) and child.kind == "reasoning":
                child.set_class(not self.runtime.settings.show_reasoning, "is-hidden")
            if isinstance(child, ChatBlock) and child.kind == "tool":
                child.set_class(not self.runtime.settings.show_tool_results, "is-hidden")

    def _start_turn_worker(self, text: str) -> None:
        self.busy = True
        self._refresh_status()
        self.turn_worker = self.run_worker(
            self._run_user_turn(text),
            name="chat-turn",
            group="chat-turn",
            exclusive=True,
            exit_on_error=False,
            thread=False,
        )

    def _start_next_queued_turn(self) -> None:
        if self.busy or not self.pending_inputs:
            self._refresh_status()
            return
        next_message = self.pending_inputs.popleft()
        self.runtime.logger.info(
            "message_dequeued",
            extra={"queued_count_after_pop": len(self.pending_inputs), "message_preview": next_message[:500]},
        )
        self._start_turn_worker(next_message)

    async def _cancel_active_turn(self) -> bool:
        worker = self.turn_worker
        if worker is None or worker.is_finished:
            return False
        worker.cancel()
        self.runtime.logger.info(
            "turn_cancel_requested",
            extra={"queued_count": len(self.pending_inputs)},
        )
        await self._add_block(
            self.translator.t("event.system"),
            self.translator.t("queue.cancelled"),
            "system",
        )
        return True

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
