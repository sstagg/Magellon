from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Input, Switch, Label
from textual.containers import Vertical, Horizontal, Grid
from textual.validation import Regex


class MySqlScreen(Screen):
    """Screen for configuring MySQL database settings."""

    def __init__(self, data=None):
        super().__init__()
        self.data = data or {}

    def compose(self) -> ComposeResult:
        yield Static("MySQL Database Configuration", id="mysql-title")

        with Vertical(id="mysql-container"):
            with Horizontal(id="mysql-install-option"):
                yield Label("Install MySQL Server:", id="mysql-install-label")
                yield Switch(value=self.data.get('if_install_mysql', True), id="mysql-install-switch")

            with Grid(id="mysql-grid"):
                yield Label("Database Host:")
                yield Input(
                    placeholder="Enter database host...",
                    validators=[Regex("^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$|^localhost$"), ],
                    id="mysql-host",
                    value=self.data.get('mysql_server_ip', 'localhost')
                )

                yield Label("Database Name:")
                yield Input(
                    placeholder="Database Name..",
                    validators=[Regex("^[a-zA-Z0-9_.-]+$"), ],
                    id="mysql-dbname",
                    value=self.data.get('mysql_server_db_dbname', 'magellon01')
                )

                yield Label("Database User:")
                yield Input(
                    placeholder="Enter database username...",
                    validators=[Regex("^[a-zA-Z0-9_.-]+$"), ],
                    id="mysql-username",
                    value=self.data.get('mysql_server_db_username', 'magellon_user')
                )

                yield Label("Database Password:")
                yield Input(
                    placeholder="Enter database password...",
                    password=True,
                    validators=[Regex("^.+$"), ],
                    id="mysql-password",
                    value=self.data.get('mysql_server_db_password', 'behd1d2')
                )

                yield Label("Database Port:")
                yield Input(
                    placeholder="Enter database port...",
                    validators=[Regex("^[0-9]+$"), ],
                    id="mysql-port",
                    value=str(self.data.get('mysql_server_db_port_no', 3306))
                )

            with Vertical(id="mysql-server-options"):
                yield Static("MySQL Server Settings (if installing MySQL server)", id="mysql-server-title")

                with Grid(id="mysql-server-grid"):
                    yield Label("Root Password:")
                    yield Input(
                        placeholder="Enter MySQL root password...",
                        password=True,
                        validators=[Regex("^.+$"), ],
                        id="mysql-root-password",
                        value=self.data.get('mysql_server_db_password', 'behd1d2')
                    )

                    yield Label("Data Directory:")
                    yield Input(
                        placeholder="Enter MySQL data directory...",
                        id="mysql-data-dir",
                        value=self.data.get('mysql_data_dir', '/opt/magellon/services/mysql/data')
                    )

        with Horizontal(id="mysql-buttons"):
            yield Button("Cancel", variant="primary", id="cancel-btn")
            yield Button("Generate Random Passwords", variant="warning", id="generate-pwd-btn")
            yield Button("Save Settings", variant="success", id="save-btn")

    def on_mount(self) -> None:
        """Initialize the screen after mounting."""
        # Update visibility of server options based on install switch
        self.update_mysql_server_options()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch toggle events."""
        if event.switch.id == "mysql-install-switch":
            self.update_mysql_server_options()

    def update_mysql_server_options(self) -> None:
        """Update visibility of MySQL server options based on install switch."""
        install_mysql = self.query_one("#mysql-install-switch", Switch).value
        server_options = self.query_one("#mysql-server-options", Vertical)

        # Show or hide server options
        server_options.display = True if install_mysql else False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss()
        elif event.button.id == "generate-pwd-btn":
            self.generate_random_passwords()
        elif event.button.id == "save-btn":
            self.save_mysql_settings()

    def generate_random_passwords(self) -> None:
        """Generate random secure passwords for MySQL."""
        import secrets
        import string

        # Generate a random password (12 chars with letters, digits, and symbols)
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(chars) for _ in range(12))

        # Set the password in the input fields
        self.query_one("#mysql-password", Input).value = password
        self.query_one("#mysql-root-password", Input).value = password

    def save_mysql_settings(self) -> None:
        """Save the MySQL configuration and dismiss the screen."""
        # Collect data from inputs
        mysql_config = {
            'if_install_mysql': self.query_one("#mysql-install-switch", Switch).value,
            'mysql_server_ip': self.query_one("#mysql-host", Input).value,
            'mysql_server_db_dbname': self.query_one("#mysql-dbname", Input).value,
            'mysql_server_db_username': self.query_one("#mysql-username", Input).value,
            'mysql_server_db_password': self.query_one("#mysql-password", Input).value,
            'mysql_server_db_port_no': int(self.query_one("#mysql-port", Input).value),
            'mysql_data_dir': self.query_one("#mysql-data-dir", Input).value
        }

        # Return the configuration through dismiss
        self.dismiss(mysql_config)