"""Compatibility shim — ``core.helper`` was split by cohesion (2026-07-06).

The grab-bag now lives in focused modules; every existing
``from core.helper import X`` keeps working via the re-exports below.
New code should import from the specific module:

  - :mod:`core.paths` — /gpfs wire-path canonicalization
    (``to_canonical_gpfs_path`` and friends)
  - :mod:`core.queue_names` — task-category → RMQ queue-name mapping
  - :mod:`core.file_utils` — small file / string utilities
  - :mod:`core.task_dispatch` — ``push_task_to_task_queue`` chokepoint
    (raises :class:`core.exceptions.TaskDispatchError` on dispatch failure)
  - :mod:`core.dispatch_builders` — per-category dispatch builders
  - :mod:`core.motioncor_dispatch` — MotionCor task creation + dispatch
"""
from core.dispatch_builders import (
    _dispatch_ptolemy_task,
    dispatch_ctf_task,
    dispatch_fft_task,
    dispatch_hole_detection_task,
    dispatch_micrograph_denoise_task,
    dispatch_particle_pick_task,
    dispatch_square_detection_task,
    dispatch_topaz_pick_task,
)
from core.file_utils import (
    append_json_to_file,
    create_directory,
    custom_replace,
    find_matching_file,
)
from core.motioncor_dispatch import (
    create_motioncor_task,
    create_motioncor_task_data,
    dispatch_motioncor_task,
)
from core.paths import (
    canonicalize_paths_in_payload,
    from_canonical_gpfs_path,
    is_under_gpfs_root,
    to_canonical_gpfs_path,
)
from core.queue_names import get_queue_name_by_task_type
from core.task_dispatch import (
    _audit_outgoing_message,
    _emit_outgoing_envelope,
    _stamp_image_subject,
    push_task_to_task_queue,
)

__all__ = [
    "_audit_outgoing_message",
    "_dispatch_ptolemy_task",
    "_emit_outgoing_envelope",
    "_stamp_image_subject",
    "append_json_to_file",
    "canonicalize_paths_in_payload",
    "create_directory",
    "create_motioncor_task",
    "create_motioncor_task_data",
    "custom_replace",
    "dispatch_ctf_task",
    "dispatch_fft_task",
    "dispatch_hole_detection_task",
    "dispatch_micrograph_denoise_task",
    "dispatch_motioncor_task",
    "dispatch_particle_pick_task",
    "dispatch_square_detection_task",
    "dispatch_topaz_pick_task",
    "find_matching_file",
    "from_canonical_gpfs_path",
    "get_queue_name_by_task_type",
    "is_under_gpfs_root",
    "push_task_to_task_queue",
    "to_canonical_gpfs_path",
]
