import os

import pyfiglet
# from ansible_runner import run_async, AnsibleRunnerException
from jinja2 import Template, Environment
from rich import print
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Grid
from textual.validation import Regex, Number
from textual.widgets import Header, Footer, Label, Button, Input, TabbedContent, TabPane, ProgressBar, TextLog, Switch

from libs.models import InstallationData
from screens.quit_screen import QuitScreen

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[orange]{title}[/orange]')
print(f'Installation Wizard V:1.0')

load_gui: bool = False
installation_data: InstallationData = InstallationData()


# Create an instance of InstallationData and load settings if the file exists

class MagellonInstallationApp(App[str]):
    CSS_PATH = "magellon_installation.css"
    TITLE = "Magellon Installation Wizard"
    SUB_TITLE = "Welcome to Magellon Installation Wizard"

    BINDINGS = [
        Binding(key="q", action="quit_app", description="Quit the app"),
        Binding(key="i", action="install_magellon()", description="Install Magellon"),
        Binding(key="c", action="copy_server_info()", description="Copy Server"),
        Binding(key="m", action="push_screen('MySqlScreen')", description="License Agreement", show=True),
        Binding(
            key="question_mark",
            action="help",
            description="Help",
            key_display="?",
        ),

    ]

    def compose(self) -> ComposeResult:
        yield Header()

        # yield Markdown(DOCKER)
        with TabbedContent(initial="SeverTabPane"):
            with TabPane("Core Server", id="SeverTabPane"):
                yield Grid(
                    Label("IP address:"),
                    Input(
                        placeholder="Enter accessible ip address or name...",
                        validators=[Regex("^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$"), ], id="server_ip"
                    ),
                    Label("Port Number:"),
                    Input(
                        placeholder="Enter core app port number", value="8000",
                        validators=[Number(minimum=1, maximum=65500), ], id="server_core_port"
                    ),
                    Label("Username:"),
                    Input(
                        placeholder="Enter server's username...",
                        validators=[Regex(
                            "^[a-zA-Z0-9_.-]+$"), ],
                        id="server_username"
                    ),

                    Label("Password:"),
                    Input(
                        placeholder="Enter server's password : at least one digit, one uppercase letter, at least one lowercase letter, at least one special character",
                        validators=[Regex("^(?=.*[\d])(?=.*[A-Z])(?=.*[a-z])(?=.*[@#$])[\w\d@#$]{6,12}$"), ],
                        id="server_password"
                    )
                    ,

                    Label("Base Directory:"),
                    Input(
                        placeholder="Enter accessible base Directory...",
                        id="core_server_base_directory"
                    ),

                )

            with TabPane("WebApp", id="WebAppTabPane"):
                yield Grid(
                    Label("IP address:"),
                    Input(
                        placeholder="Enter accessible ip address or name...",
                        validators=[Regex("^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$"), ], id="web_server_ip"
                    ),
                    Label("WebApp's Port Number:"),
                    Input(
                        placeholder="Enter web app's port number", value="8080",
                        validators=[Number(minimum=1, maximum=65500), ], id="server_webapp_port"
                    ),
                    Label("Username:"),
                    Input(
                        placeholder="Enter server's username...",
                        validators=[Regex(
                            "^[a-zA-Z0-9_.-]+$"), ],
                        id="web_server_username"
                    ),

                    Label("Password:"),
                    Input(
                        placeholder="Enter server's password : at least one digit, one uppercase letter, at least one lowercase letter, at least one special character",
                        validators=[Regex("^(?=.*[\d])(?=.*[A-Z])(?=.*[a-z])(?=.*[@#$])[\w\d@#$]{6,12}$"), ],
                        id="web_server_password"
                    )
                    ,

                    # Label("Host Name:"),
                    # Input(
                    #     placeholder="Enter accessible host name...",
                    #     validators=[Regex("^[a-zA-Z0-9_.-]+$"), ], id="web_server_name"
                    # ),
                )
            with TabPane("MySql", id="MySqlTabPane"):
                yield Label("MySql Server:")
                yield Input(
                    placeholder="Enter accessible ip address or name...",
                    validators=[Regex("^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$"), ], id="mysql_server_ip"
                )

                yield Label("User Name:")
                yield Input(
                    placeholder="Enter a username...",
                    validators=[
                        Regex("^[a-zA-Z0-9_.-]+$"),
                    ], id="mysql_server_db_username"
                )
                yield Label("Password:")
                yield Input(
                    placeholder="Enter mysql password...",
                    validators=[
                        Regex("^(?=.*[\d])(?=.*[A-Z])(?=.*[a-z])(?=.*[@#$])[\w\d@#$]{6,12}$"),
                    ], id="mysql_server_db_password"
                )
                yield Label("Database Name:")
                yield Input(
                    placeholder="Database Name..",
                    validators=[
                        Regex("^[a-zA-Z0-9_.-]+$"),
                    ], id="mysql_server_db_dbname"
                )
                yield Label("Install MySql Server  ")
                yield Switch(value=False, id="if_install_mysql_server")

                yield Vertical(
                    Label("Server User Name:"),
                    Input(
                        placeholder="Enter a username...",
                        validators=[
                            Regex("^[a-zA-Z0-9_.-]+$"),
                        ], id="mysql_server_username"
                    ),
                    Label("Server Password:"),
                    Input(
                        placeholder="Enter Server's password...",
                        validators=[
                            Regex("^(?=.*[\d])(?=.*[A-Z])(?=.*[a-z])(?=.*[@#$])[\w\d@#$]{6,12}$"),
                        ], id="mysql_server_password"
                    ), id="mysql_server_info"

                )
                # yield Horizontal(
                #     Switch(value=False,id="install_mysql_server"),
                #     Label("Install MySql Server  "),
                #
                # )

            # with TabPane("Ansible", id="ANSIBLE"):
            #     yield Label("User Name:")
            # yield Markdown(ANSIBLE)

        # yield Pretty([])
        # yield Label("Do you love Textual?", id="question")
        yield Vertical(
            ProgressBar(total=100, show_eta=False),
            TextLog(highlight=True, markup=True, id="text_logger"),
            Horizontal(
                Button("Install", id="install", variant="primary"),
                Button("Exit", id="exit", variant="error")
            )
        )

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

    def on_switch_changed(self, event: Switch.Changed) -> None:
        panel = self.query_one("#mysql_server_info")
        panel.styles.visibility = 'visible' if event.value else 'hidden'
        # self.query_one(TextLog).write("Pressed")

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

    def action_copy_server_info(self):
        self.copy_core_to_web()

    def copy_core_to_web(self):
        if self.query_one("#server_ip", Input).value is not None:
            self.query_one("#web_server_ip", Input).value = self.query_one("#server_ip", Input).value
        if self.query_one("#server_username", Input).value is not None:
            self.query_one("#web_server_username", Input).value = self.query_one("#server_username", Input).value
        if self.query_one("#server_password", Input).value is not None:
            self.query_one("#web_server_password", Input).value = self.query_one("#server_password", Input).value

        if self.query_one("#server_ip", Input).value is not None:
            self.query_one("#mysql_server_ip", Input).value = self.query_one("#server_ip", Input).value
        if self.query_one("#server_username", Input).value is not None:
            self.query_one("#mysql_server_username", Input).value = self.query_one("#server_username", Input).value
        if self.query_one("#server_password", Input).value is not None:
            self.query_one("#mysql_server_password", Input).value = self.query_one("#server_password", Input).value

    def save_gui_to_model(self):
        installation_data.core_service_server_ip = self.query_one("#server_ip", Input).value
        installation_data.core_service_server_username = self.query_one("#server_username", Input).value
        installation_data.core_service_server_password = self.query_one("#server_password", Input).value
        installation_data.core_service_server_port = self.query_one("#server_core_port", Input).value
        installation_data.core_service_server_base_directory = self.query_one("#core_server_base_directory", Input).value

        installation_data.webapp_server_ip = self.query_one("#web_server_ip", Input).value
        installation_data.webapp_server_username = self.query_one("#web_server_username", Input).value
        installation_data.webapp_server_password = self.query_one("#web_server_password", Input).value
        installation_data.webapp_port = self.query_one("#server_webapp_port", Input).value

        installation_data.if_install_mysql = self.query_one("#if_install_mysql_server", Switch).value
        installation_data.mysql_server_ip = self.query_one("#mysql_server_ip", Input).value
        installation_data.mysql_server_username = self.query_one("#mysql_server_username", Input).value
        installation_data.mysql_server_password = self.query_one("#mysql_server_password", Input).value
        installation_data.mysql_server_db_username = self.query_one("#mysql_server_db_username", Input).value
        installation_data.mysql_server_db_password = self.query_one("#mysql_server_db_password", Input).value
        installation_data.mysql_server_db_dbname = self.query_one("#mysql_server_db_dbname", Input).value

    def load_gui_from_model(self):
        if installation_data is None:
            return
        if installation_data.core_service_server_ip is not None:
            self.query_one("#server_ip", Input).value = installation_data.core_service_server_ip
        if installation_data.core_service_server_username is not None:
            self.query_one("#server_username", Input).value = installation_data.core_service_server_username
        if installation_data.core_service_server_password is not None:
            self.query_one("#server_password", Input).value = installation_data.core_service_server_password
        if installation_data.core_service_server_port is not None:
            self.query_one("#server_core_port", Input).value = str(installation_data.core_service_server_port)
        if installation_data.core_service_server_base_directory is not None:
            self.query_one("#core_server_base_directory", Input).value = str(installation_data.core_service_server_base_directory)

        if installation_data.webapp_server_ip is not None:
            self.query_one("#web_server_ip", Input).value = installation_data.webapp_server_ip
        if installation_data.webapp_server_username is not None:
            self.query_one("#web_server_username", Input).value = installation_data.webapp_server_username
        if installation_data.webapp_server_password is not None:
            self.query_one("#web_server_password", Input).value = installation_data.webapp_server_password
        if installation_data.webapp_port is not None:
            self.query_one("#server_webapp_port", Input).value = str(installation_data.webapp_port)

        if installation_data.if_install_mysql is not None:
            self.query_one("#if_install_mysql_server", Switch).value = installation_data.if_install_mysql
        if installation_data.mysql_server_ip is not None:
            self.query_one("#mysql_server_ip", Input).value = installation_data.mysql_server_ip
        if installation_data.mysql_server_username is not None:
            self.query_one("#mysql_server_username", Input).value = installation_data.mysql_server_username
        if installation_data.mysql_server_password is not None:
            self.query_one("#mysql_server_password", Input).value = installation_data.mysql_server_password
        if installation_data.mysql_server_db_username is not None:
            self.query_one("#mysql_server_db_username", Input).value = installation_data.mysql_server_db_username
        if installation_data.mysql_server_db_password is not None:
            self.query_one("#mysql_server_db_password", Input).value = installation_data.mysql_server_db_password
        if installation_data.mysql_server_db_dbname is not None:
            self.query_one("#mysql_server_db_dbname", Input).value = installation_data.mysql_server_db_dbname

    def install(self, data: InstallationData):
        # env = Environment('<!--', '-->', '${', '}', '<!--#', '-->')
        # installing the required packages
        if os.path.exists('assets/templates/deployment_playbook_template.yml.j2'):
            text_log = self.query_one(TextLog)
            try:
                with open('assets/templates/deployment_playbook_template.yml.j2', 'r') as file:
                    template = Template(file.read(), variable_start_string='${', variable_end_string='}')

                rendered_playbook = template.render(data=data)

                text_log.write(rendered_playbook)
                # print(rendered_playbook)
                with open("playbook-content.yml", 'w') as file:
                    file.write(rendered_playbook)
            except Exception as e:
                print(e.__str__())
                # run_data = run_async(playbook=rendered_playbook, extravars={'target_ip': data.}, quiet=True)
                # run_data = run_async(playbook=rendered_playbook,  quiet=True)
                #
                # while run_data.return_code is None:
                #     text_log.write(f"Playbook running... Current status: {run_data.status}")
                #     # Perform additional actions or checks as needed
                #     run_data = run_async(status=run_data.status)
                # if run_data.return_code == 0:
                #     text_log.write("Playbook execution completed successfully.")
                # else:
                #     text_log.write(f"Playbook execution failed with return code: {run_data.return_code}")

            # except AnsibleRunnerException as e:
            #     text_log.write(f"An error occurred while running the playbook: {str(e)}")


if __name__ == "__main__":
    app = MagellonInstallationApp()

    if os.path.exists('settings.json'):
        installation_data = InstallationData.load_settings('settings.json')
        load_gui = True

    reply = app.run()
    print(reply)
