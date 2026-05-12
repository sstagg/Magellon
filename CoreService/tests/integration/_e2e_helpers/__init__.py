"""Shared helpers for the Phase 0–4 e2e wave.

These tests assume a docker-compose stack (mysql, rabbitmq, nats,
CoreService) is up but DON'T assume any specific plugin container is
running — they install/uninstall plugins via the admin endpoints as
part of the test.

Gated on ``MAGELLON_E2E_STACK=up`` to prevent accidental runs in the
unit-test loop.
"""
from __future__ import annotations

from tests.integration._e2e_helpers.dispatch import (  # noqa: F401
    build_fft_task_message,
    dispatch_fft_task_via_rmq,
    generate_input_image,
)
from tests.integration._e2e_helpers.install import (  # noqa: F401
    install_plugin_from_archive,
    uninstall_plugin,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

__all__ = [
    "build_fft_task_message",
    "dispatch_fft_task_via_rmq",
    "generate_input_image",
    "install_plugin_from_archive",
    "uninstall_plugin",
    "wait_for_lifecycle_status",
    "wait_for_plugin_announce",
]
