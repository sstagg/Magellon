"""Step-event helpers for the SAM2 plugin."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

STEP_NAME = "sam2_pick"

_publisher = None
_loop: Optional[asyncio.AbstractEventLoop] = None


async def get_publisher():
    global _publisher, _loop
    try:
        from magellon_sdk.runner import get_step_event_loop, make_step_publisher
        _loop = get_step_event_loop()
        _publisher = await make_step_publisher()
    except Exception:
        logger.debug("Step-event publisher unavailable (non-fatal)")
    return _publisher
