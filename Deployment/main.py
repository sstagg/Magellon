import pyfiglet
from rich import print
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.validation import Regex, Number
from textual.widgets import Header, Footer, Label, Button, Input, TabbedContent, TabPane, ProgressBar, TextLog

from screens.quit_screen import QuitScreen

from pydantic import BaseModel, Field, Json
from typing import Optional, List, Union


class InstallationData(BaseModel):
    # input_movie: Optional[str]
    server_ip: Optional[str] = None
    server_username: Optional[str] = None
    server_password: Optional[str] = None
    server_port: Optional[int] = 8181

    webapp_port: Optional[int] = 8080

    create_mysql_server: Optional[bool] = False
    create_core_server: Optional[bool] = False
    create_webapp_server: Optional[bool] = False
    install_mysql: Optional[bool] = False

    mysql_server_ip: Optional[str] = None
    mysql_server_username: Optional[str] = None
    mysql_server_password: Optional[str] = None

    mysql_server_db_username: Optional[str] = None
    mysql_server_db_password: Optional[str] = None
    mysql_server_db_dbname: Optional[str] = None


title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[orange]{title}[/orange]')
print(f'Installation Wizard V:1.0')

installation_data = InstallationData()

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
    # CSS_PATH = "magellon_installation.css"
    TITLE = "Magellon Installation Wizard"
    SUB_TITLE = "Welcome to Magellon Installation Wizard"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(key="i", action="install_magellon()", description="Install Magellon"),
        Binding(
            key="question_mark",
            action="help",
            description="Show help screen",
            key_display="?",
        ),
        Binding(key="m", action="push_screen('MySqlScreen')", description="License Agreement", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        # yield Markdown(DOCKER)
        with TabbedContent(initial="SeverTabPane"):
            with TabPane("Server", id="SeverTabPane"):
                yield Label("IP address:")
                yield Input(
                    placeholder="Enter accessible ip address or name...",
                    validators=[Regex("^[a-zA-Z0-9_]{3,16}$"), ], id="server_ip"
                )
                yield Label("Username:")
                yield Input(
                    placeholder="Enter server's username...",
                    validators=[Regex(
                        "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"), ],
                    id="server_username"
                )
                yield Label("Password:")
                yield Input(
                    placeholder="Enter server's password",
                    validators=[Regex("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"), ],
                    id="server_password"
                )
                yield Label("Core Service's Port Number:")
                yield Input(
                    placeholder="Enter core app port number", value="8000",
                    validators=[Number(minimum=1, maximum=65500), ], id="server_core_port"
                )
                yield Label("WebApp's Port Number:")
                yield Input(
                    placeholder="Enter web app's port number", value="8080",
                    validators=[Number(minimum=1, maximum=65500), ], id="server_webapp_port"
                )

            with TabPane("MySql", id="MySqlTabPane"):
                yield Label("MySql Server:")
                yield Input(
                    placeholder="Enter accessible ip address or name...",
                    validators=[Regex("^[a-zA-Z0-9_]{3,16}$"), ],
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
                yield Input(
                    placeholder="Database Name..",
                    validators=[
                        Regex("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"),
                    ],
                )

            # with TabPane("Ansible", id="ANSIBLE"):
            #     yield Label("User Name:")
            # yield Markdown(ANSIBLE)

        # yield Pretty([])
        # yield Label("Do you love Textual?", id="question")
        yield Horizontal(
             Button("Install", id="install", variant="primary"),
             Button("Exit", id="exit", variant="error")
        )
        yield ProgressBar(total=100, show_eta=False)
        yield TextLog(highlight=True, markup=True,id="text_logger")
        yield Footer()

    # def on_key(self, event: Key):
    #     self.title = event.key
    #     self.sub_title = f"You just pressed {event.key}!"
    # def on_mount(self) -> None:
    #     # self.push_screen(MySqlScreen())
    #     self.push_screen(QuitScreen())
    def check_quit(self, quit: bool) -> None:
        """Called when QuitScreen is dismissed."""
        if quit:
            self.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "install":
            print(event.button.id)
            self.action_install_magellon()
        else:
            self.push_screen(QuitScreen(), self.check_quit)
            # self.exit(event.button.id)

        def action_request_quit(self) -> None:
            """Action to display the quit dialog."""

    def action_install_magellon(self):
        self.query_one(TextLog).write("installataion advanced")
        self.query_one(ProgressBar).advance(10)


if __name__ == "__main__":
    app = MagellonInstallationApp()
    reply = app.run()
    print(reply)
