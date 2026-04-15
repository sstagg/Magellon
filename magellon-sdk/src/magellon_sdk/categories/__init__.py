"""Category contracts — the stable slots plugins implement.

A CategoryContract defines, for one role (fft, ctf, pp, motioncor):

  - the canonical input model dispatchers publish,
  - the canonical output model plugins must produce,
  - the broker subject names for tasks, results, heartbeats,
    announce, and config.

Substitutability is the point: any plugin claiming ``CTF`` speaks
``CtfTaskData`` in and ``CtfOutput`` out, so a scheduler can replace
ctffind with gctf without the downstream projector caring.

Usage:

    from magellon_sdk.categories import CTF, get_category

    # Dispatcher side — publish to the task subject
    subject = CTF.task_subject         # "magellon.tasks.ctf"

    # Plugin side — subscribe, validate, execute
    data = CTF.validate_input(payload)

    # Generic lookup from a TaskDto's integer type code
    contract = get_category(task.type.code)
"""
from magellon_sdk.categories.contract import (
    CATEGORIES,
    CONFIG_BROADCAST_SUBJECT,
    CTF,
    CategoryContract,
    FFT,
    MOTIONCOR_CATEGORY,
    PARTICLE_PICKER,
    PluginInputExtras,
    announce_subject,
    config_subject,
    get_category,
    heartbeat_subject,
    result_subject,
    task_subject,
)
from magellon_sdk.categories.outputs import (
    CategoryOutput,
    CtfOutput,
    FftOutput,
    MotionCorOutput,
    ParticlePickingOutput,
)

__all__ = [
    # Contracts.
    "CategoryContract",
    "PluginInputExtras",
    "FFT",
    "CTF",
    "MOTIONCOR_CATEGORY",
    "PARTICLE_PICKER",
    "CATEGORIES",
    "CONFIG_BROADCAST_SUBJECT",
    "get_category",
    # Subject helpers.
    "task_subject",
    "result_subject",
    "heartbeat_subject",
    "announce_subject",
    "config_subject",
    # Canonical outputs.
    "CategoryOutput",
    "FftOutput",
    "CtfOutput",
    "MotionCorOutput",
    "ParticlePickingOutput",
]
