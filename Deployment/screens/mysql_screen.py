from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from main import DOCKER


class MySqlScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def compose(self) -> ComposeResult:
        yield Static(" Windows ", id="title")
        yield Static(DOCKER)
        yield Static("Press any key to continue [blink]_[/]", id="any-key")
