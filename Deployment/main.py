import pyfiglet
from rich import print
from rich.markdown import Markdown
from rich.pretty import Pretty
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.validation import Number, Regex
from textual.widgets import Header, Footer, Tabs, Label, Button, Input, TabbedContent, TabPane

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[orange]{title}[/orange]')
print(f'Installation Wizard V:1.0')

MySql = """
# Duke Leto I Atreides

Head of House Atreides.
"""

ANSIBLE = """
# Lady Jessica

Bene Gesserit and concubine of Leto, and mother of Paul and Alia.
"""

DOCKER = """
# Paul Atreides

Son of Leto and Jessica.
"""


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
        # yield Markdown(DOCKER)
        with TabbedContent(initial="MySql"):
            with TabPane("MySql", id="MySql"):
                yield Label("MySql Server:")
                yield Input(
                    placeholder="Enter ip address or name...",
                    validators=[
                        Regex("^[a-zA-Z0-9_]{3,16}$"),
                    ],
                )
                yield Label("User Name:")
                yield Input(
                    placeholder="Enter a username...",
                    validators=[
                        Regex("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"),
                    ],
                )
                yield Label("Password:")
                yield Input(
                    placeholder="Enter mysql password...",
                    validators=[
                        Regex("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"),
                    ],
                )

            with TabPane("DOCKER", id="DOCKER"):
                yield Label("User Name:")
                # yield Markdown(DOCKER)
            with TabPane("Ansible", id="ANSIBLE"):
                yield Label("User Name:")
                # yield Markdown(ANSIBLE)

        # yield Pretty([])
        # yield Label("Do you love Textual?", id="question")
        yield Button("Install", id="install", variant="primary")
        yield Button("Exit", id="exit", variant="error")
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
