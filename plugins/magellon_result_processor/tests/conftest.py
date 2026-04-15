import os
import sys


def pytest_configure():
    # Plugin imports use bare `core.*` / `services.*` — put the plugin
    # root on sys.path so tests can drive them without a package install.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
