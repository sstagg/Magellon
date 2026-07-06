from __future__ import annotations

import asyncio
import sys


def pytest_asyncio_loop_factories():
    if sys.platform == "win32":
        return {"proactor": asyncio.ProactorEventLoop}
    return None
