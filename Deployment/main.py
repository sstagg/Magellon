import pyfiglet
from rich import print
from rich.pretty import Pretty
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.validation import Number,Regex
from textual.widgets import Header, Footer, Tabs, Label, Button, Input

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[orange]{title}[/orange]')
print(f'Installation Wizard V:1.0')


class MagellonInstallationApp(App[str]):
    CSS_PATH = "magellon_installation.css"
    TITLE = "Magellon Installation Wizard"
    SUB_TITLE = "Welcome to Magellon Installation Wizard"
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
        yield Tabs("MySql", "Docker","Ansible")
        yield Label("User Name:")
        yield Input(
            placeholder="Enter a username...",
            # validators=[
            #     Number(minimum=1, maximum=100),
            #     Regex("Value is not even."),
            # ],
        )
        # yield Pretty([])
        # yield Label("Do you love Textual?", id="question")
        # yield Button("Yes", id="yes", variant="primary")
        # yield Button("No", id="no", variant="error")
        yield Footer()

    # def on_key(self, event: Key):
    #     self.title = event.key
    #     self.sub_title = f"You just pressed {event.key}!"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.exit(event.button.id)


if __name__ == "__main__":
    app = MagellonInstallationApp()
    reply = app.run()
    print(reply)
