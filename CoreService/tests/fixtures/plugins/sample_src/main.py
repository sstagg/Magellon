"""Sample plugin entry point — test fixture only.

Real plugins construct a ``PluginBrokerRunner`` here and start
consuming on the bus. This fixture's main.py never gets executed by
the install tests (they verify that install COMPLETES, not that the
plugin runs); it's a placeholder so the package looks syntactically
complete to uv.
"""
print("sample-plugin fixture: main.py executed (test fixture, no-op)")
