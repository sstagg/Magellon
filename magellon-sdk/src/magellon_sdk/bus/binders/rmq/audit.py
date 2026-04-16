"""Publish-time audit log writer.

Preserves today's behavior from
``CoreService/core/helper.py::publish_message_to_queue``:

  1. Resolve ``<root>/<subject>/messages.json`` as the target path.
  2. ``makedirs(exist_ok=True)`` on the directory.
  3. Open in append mode, write one JSON line per message.

The one intentional difference: the path segment is the route's
subject string (e.g. ``magellon.tasks.ctf``) rather than today's
legacy queue name (``ctf_tasks_queue``). Bus routes abstract queue
names; tying audit paths to subjects keeps the single source of
truth. Operators reading audit files post-MB3 see the new layout.

Failures are non-fatal and logged at debug — audit is diagnostics,
not correctness. A broken audit file must never break a dispatch.
"""
from __future__ import annotations

import logging
import os

from magellon_sdk.bus.policy import AuditLogConfig
from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)


def write_audit_entry(
    config: AuditLogConfig, subject: str, envelope: Envelope
) -> None:
    """Append one JSON line to the audit file if this subject is in scope."""
    if not config.applies_to(subject):
        return
    try:
        destination_dir = os.path.join(config.root, subject)
        os.makedirs(destination_dir, exist_ok=True)
        path = os.path.join(destination_dir, "messages.json")
        with open(path, "a") as f:
            f.write(envelope.model_dump_json() + "\n")
    except Exception as e:  # noqa: BLE001
        logger.debug("audit write failed for %s (non-fatal): %s", subject, e)


__all__ = ["write_audit_entry"]
