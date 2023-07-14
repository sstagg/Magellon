import os

import pyfiglet
from ansible_runner import run_async, AnsibleRunnerException
from jinja2 import Template
from rich import print
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.validation import Regex, Number
from textual.widgets import Header, Footer, Label, Button, Input, TabbedContent, TabPane, ProgressBar, TextLog

from libs.models import InstallationData
from screens.quit_screen import QuitScreen

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[orange]{title}[/orange]')
print(f'Installation Wizard V:1.0')

load_gui: bool = False
installation_data: InstallationData = InstallationData()
# Create an instance of InstallationData and load settings if the file exists


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
        Binding(key="q", action="quit_app", description="Quit the app"),
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
                    validators=[Regex("^[a-zA-Z0-9_]{3,16}$"), ], id="mysql_server_ip"
                )
                yield Label("User Name:")
                yield Input(
                    placeholder="Enter a username...",
                    validators=[
                        Regex("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"),
                    ], id="mysql_server_db_username"
                )
                yield Label("Password:")
                yield Input(
                    placeholder="Enter mysql password...",
                    validators=[
                        Regex("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"),
                    ], id="mysql_server_db_password"
                )
                yield Input(
                    placeholder="Database Name..",
                    validators=[
                        Regex("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"),
                    ], id="mysql_server_db_dbname"
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
        yield TextLog(highlight=True, markup=True, id="text_logger")
        yield Footer()

    # def on_key(self, event: Key):
    #     self.title = event.key
    #     self.sub_title = f"You just pressed {event.key}!"
    def on_mount(self) -> None:
        # self.push_screen(MySqlScreen())
        if load_gui:
            self.load_gui_from_model()

    def check_quit(self, do_quit: bool) -> None:
        """Called when QuitScreen is dismissed."""
        if do_quit:
            installation_data.save_settings('settings.json')
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

    def action_quit_app(self) -> None:
        self.push_screen(QuitScreen(), self.check_quit)

    def action_install_magellon(self):
        self.save_gui_to_model()
        self.install(installation_data)
        self.query_one(ProgressBar).advance(10)

    def save_gui_to_model(self):
        installation_data.server_ip = self.query_one("#server_ip", Input).value
        installation_data.server_username = self.query_one("#server_username", Input).value
        installation_data.server_password = self.query_one("#server_password", Input).value
        installation_data.server_port = self.query_one("#server_core_port", Input).value
        installation_data.webapp_port = self.query_one("#server_webapp_port", Input).value
        installation_data.mysql_server_ip = self.query_one("#mysql_server_ip", Input).value
        installation_data.mysql_server_db_username = self.query_one("#mysql_server_db_username", Input).value
        installation_data.mysql_server_db_password = self.query_one("#mysql_server_db_password", Input).value
        installation_data.mysql_server_db_dbname = self.query_one("#mysql_server_db_dbname", Input).value

    def load_gui_from_model(self):
        if installation_data is None:
            return
        if installation_data.server_ip is not None:
            self.query_one("#server_ip", Input).value = installation_data.server_ip
        if installation_data.server_username is not None:
            self.query_one("#server_username", Input).value = installation_data.server_username
        if installation_data.server_password is not None:
            self.query_one("#server_password", Input).value = installation_data.server_password

        if installation_data.server_port is not None:
            self.query_one("#server_core_port", Input).value = str(installation_data.server_port)

        if installation_data.webapp_port is not None:
            self.query_one("#server_webapp_port", Input).value = str(installation_data.webapp_port)

        if installation_data.mysql_server_ip is not None:
            self.query_one("#mysql_server_ip", Input).value = installation_data.mysql_server_ip
        if installation_data.mysql_server_db_username is not None:
            self.query_one("#mysql_server_db_username", Input).value = installation_data.mysql_server_db_username
        if installation_data.mysql_server_db_password is not None:
            self.query_one("#mysql_server_db_password", Input).value = installation_data.mysql_server_db_password
        if installation_data.mysql_server_db_dbname is not None:
            self.query_one("#mysql_server_db_dbname", Input).value = installation_data.mysql_server_db_dbname

    def install(self, data: InstallationData):
        # installing the required packages
        if os.path.exists('assets/templates/deployment_playbook_template.yml.j2'):
            text_log = self.query_one(TextLog)
            try:
                with open('assets/templates/deployment_playbook_template.yml.j2', 'r') as file:
                    template = Template(file.read())

                rendered_playbook = template.render(data=data)

                text_log.write(rendered_playbook)
                # print(rendered_playbook)

                # run_data = run_async(playbook=rendered_playbook, extravars={'target_ip': data.}, quiet=True)
                run_data = run_async(playbook=rendered_playbook, quiet=True)

                while run_data.return_code is None:
                    text_log.write(f"Playbook running... Current status: {run_data.status}")
                    # Perform additional actions or checks as needed
                    run_data = run_async(status=run_data.status)
                if run_data.return_code == 0:
                    text_log.write("Playbook execution completed successfully.")
                else:
                    text_log.write(f"Playbook execution failed with return code: {run_data.return_code}")

            except AnsibleRunnerException as e:
                text_log.write(f"An error occurred while running the playbook: {str(e)}")


if __name__ == "__main__":
    app = MagellonInstallationApp()

    if os.path.exists('settings.json'):
        installation_data = InstallationData.load_settings('settings.json')
        load_gui = True

    reply = app.run()
    print(reply)
