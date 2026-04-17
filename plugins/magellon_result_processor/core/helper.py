"""Plugin-local file helpers.

The single non-trivial function here is ``move_file_to_directory`` —
result_processor moves output artifacts from the plugins' working
dirs into the per-session archive layout. Pure shutil, no broker.

Pure-function bytes/JSON helpers come from
:mod:`magellon_sdk.messaging` — re-exported here only because some
older modules import them from this path. Prefer the SDK import in
new code.
"""
import os
import shutil

from magellon_sdk.messaging import (  # noqa: F401
    append_json_to_file,
    parse_message_to_task_object,
    parse_message_to_task_result_object,
)


def move_file_to_directory(file_path: str, destination_dir: str) -> None:
    """Move ``file_path`` into ``destination_dir``, creating it if missing."""
    try:
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        filename = os.path.basename(file_path)
        shutil.move(file_path, os.path.join(destination_dir, filename))
    except Exception as e:
        print(f"Error moving file {file_path}: {e}")
