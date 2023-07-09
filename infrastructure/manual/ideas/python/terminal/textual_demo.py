from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.events import Key
from textual.reactive import var
from textual.widgets import DirectoryTree, Footer, Header, Static, Tabs

# https://textual.textualize.io/guide/app/
# class PrideApp(App):
#     """Displays a pride flag."""
#
#     COLORS = ["red", "orange", "yellow", "green", "blue", "purple"]
#
#     def compose(self) -> ComposeResult:
#         for color in self.COLORS:
#             stripe = Static()
#             stripe.styles.height = "1fr"
#             stripe.styles.background = color
#             yield stripe
#
#
# if __name__ == "__main__":
#     PrideApp().run()


from textual.app import App, ComposeResult
from textual.widgets import Label, Button


class QuestionApp(App[str]):
    CSS_PATH = "question02.css"
    TITLE = "A Question App"
    SUB_TITLE = "The most important question"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(
            key="question_mark",
            action="help",
            description="Show help screen",
            key_display="?",
        ),
        Binding(key="delete", action="delete", description="Delete the thing"),
        Binding(key="j", action="down", description="Scroll down", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Tabs("First tab", "Second tab")
        yield Label("Do you love Textual?", id="question")
        yield Button("Yes", id="yes", variant="primary")
        yield Button("No", id="no", variant="error")
        yield Footer()

    # def on_key(self, event: Key):
    #     self.title = event.key
    #     self.sub_title = f"You just pressed {event.key}!"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.exit(event.button.id)


if __name__ == "__main__":
    app = QuestionApp()
    reply = app.run()
    print(reply)
