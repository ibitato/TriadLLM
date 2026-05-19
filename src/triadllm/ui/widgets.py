from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea


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
