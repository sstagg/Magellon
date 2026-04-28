"""Sample plugin module — test fixture only.

Real plugins put their ``PluginBase`` subclass here.
"""


def run() -> str:
    """Trivial public surface so the plugin module isn't empty."""
    return "sample-plugin ok"
