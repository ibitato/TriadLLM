from __future__ import annotations

import logging

from textual import events, on
from textual.app import ComposeResult
from textual.containers import CenterMiddle, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from triadllm.domain import ToolRequest
from triadllm.i18n import Translator

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
        max-height: 85%;
        padding: 1 2;
        border: round #ff9f1c;
        background: #0b0f0c;
        overflow: hidden;
    }

    #config-title {
        color: #ff9f1c;
        text-style: bold;
        margin-bottom: 1;
    }

    #config-body {
        height: 1fr;
        min-height: 15;
        max-height: 60;
        margin-top: 1;
        overflow-y: auto;
        border: round #1f6f46 20%;
        padding: 0 1;
    }

    #config-field {
        margin-bottom: 1;
        padding: 0 1;
    }

    #config-label {
        color: #b6ff7a;
        text-style: bold;
    }

    TextArea {
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
        padding-bottom: 1;
    }

    #config-actions Button {
        margin-left: 1;
        min-width: 12;
    }

    /* Scrollbar styling */
    Scrollbar {
        scrollbar-background: #1f6f46 50%;
        scrollbar-color: #ff9f1c;
        scrollbar-size: 8 12;
    }

    VerticalScroll {
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, settings: dict, profiles: dict, translator: Translator) -> None:
        super().__init__()
        self.settings = settings
        self.profiles = profiles
        self.translator = translator
        self.current_values = settings.copy()
        self.validation_errors: dict[str, str] = {}

        self.logger = logging.getLogger(__name__)
        self.logger.info("ConfigEditorScreen initialized with settings: %s", self.settings)
        self.logger.info("ConfigEditorScreen current_values: %s", self.current_values)

    def compose(self) -> ComposeResult:
        with CenterMiddle():
            with Container(id="config-editor-dialog"):
                yield Static(self.translator.t("config_editor.title"), id="config-title")
                yield Static(self.translator.t("config_editor.instructions"), id="config-instructions")

                with VerticalScroll(id="config-body"):
                    with Container(id="config-field-language"):
                        yield Static("Language:", id="config-label")
                        language_val = self.current_values.get("language", "")
                        self.logger.info("Language field value: %s (type: %s)", language_val, type(language_val))
                        self.language_input = TextArea(
                            str(language_val) if language_val is not None else "",
                            id="config-input-language",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        self.logger.info("Language TextArea text: %s", self.language_input.text)
                        yield self.language_input
                        self.language_error = Static("", id="config-error-language")
                        yield self.language_error

                    with Container(id="config-field-permission"):
                        yield Static("Permission Mode:", id="config-label")
                        permission_val = self.current_values.get("permission_mode", "")
                        self.permission_input = TextArea(
                            str(permission_val) if permission_val is not None else "",
                            id="config-input-permission",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.permission_input
                        self.permission_error = Static("", id="config-error-permission")
                        yield self.permission_error

                    with Container(id="config-field-reasoning"):
                        yield Static("Show Reasoning:", id="config-label")
                        reasoning_val = self.current_values.get("show_reasoning", "")
                        self.reasoning_input = TextArea(
                            str(reasoning_val) if reasoning_val is not None else "",
                            id="config-input-reasoning",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.reasoning_input
                        self.reasoning_error = Static("", id="config-error-reasoning")
                        yield self.reasoning_error

                    with Container(id="config-field-toolresults"):
                        yield Static("Show Tool Results:", id="config-label")
                        toolresults_val = self.current_values.get("show_tool_results", "")
                        self.toolresults_input = TextArea(
                            str(toolresults_val) if toolresults_val is not None else "",
                            id="config-input-toolresults",
                            soft_wrap=True,
                            show_line_numbers=False,
                        )
                        yield self.toolresults_input
                        self.toolresults_error = Static("", id="config-error-toolresults")
                        yield self.toolresults_error

                    with Container(id="config-field-profile"):
                        yield Static("Default Profile:", id="config-label")
                        profile_val = self.current_values.get("default_profile", "")
                        self.profile_input = TextArea(
                            str(profile_val) if profile_val is not None else "",
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
        language_input = self.query_one("#config-input-language", TextArea)
        if language_input:
            language_input.focus()

    def _validate_all(self) -> bool:
        """Validate all fields and return True if all are valid."""
        self.validation_errors = {}

        language_input = self.query_one("#config-input-language", TextArea)
        permission_input = self.query_one("#config-input-permission", TextArea)
        reasoning_input = self.query_one("#config-input-reasoning", TextArea)
        toolresults_input = self.query_one("#config-input-toolresults", TextArea)
        profile_input = self.query_one("#config-input-profile", TextArea)

        language_error = self.query_one("#config-error-language", Static)
        permission_error = self.query_one("#config-error-permission", Static)
        reasoning_error = self.query_one("#config-error-reasoning", Static)
        toolresults_error = self.query_one("#config-error-toolresults", Static)
        profile_error = self.query_one("#config-error-profile", Static)

        language = language_input.text.strip()
        if language not in ["en", "es"]:
            self.validation_errors["language"] = self.translator.t("config_editor.error.language")
            language_error.update(self.validation_errors["language"])
        else:
            language_error.update("")
            self.current_values["language"] = language

        permission = permission_input.text.strip()
        if permission not in ["ask", "yolo"]:
            self.validation_errors["permission_mode"] = self.translator.t("config_editor.error.permission")
            permission_error.update(self.validation_errors["permission_mode"])
        else:
            permission_error.update("")
            self.current_values["permission_mode"] = permission

        for field_name, input_field, error_field in [
            ("show_reasoning", reasoning_input, reasoning_error),
            ("show_tool_results", toolresults_input, toolresults_error),
        ]:
            value = input_field.text.strip().lower()
            if value not in ["true", "false"]:
                self.validation_errors[field_name] = self.translator.t("config_editor.error.boolean")
                error_field.update(self.validation_errors[field_name])
            else:
                error_field.update("")
                self.current_values[field_name] = value == "true"

        profile = profile_input.text.strip()
        if profile and profile not in self.profiles:
            self.validation_errors["default_profile"] = self.translator.t(
                "config_editor.error.profile", profile=profile
            )
            profile_error.update(self.validation_errors["default_profile"])
        else:
            profile_error.update("")
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
