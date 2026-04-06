from textual.widgets import Header


class MagellonHeader(Header):
    """Custom header for the Magellon installation wizard."""

    DEFAULT_CSS = """
    MagellonHeader {
        background: #0a1929;
        color: #58a6ff;
        text-style: bold;
        border-bottom: solid #30363d;
        height: 3;
    }
    """
