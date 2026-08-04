"""File transfer service and compatibility helpers."""
from __future__ import annotations

import glob
import os
import shutil
import shlex
from collections.abc import Sequence

from starlette.responses import FileResponse

from core.exceptions import FileProcessingError
from core.process_runner import ProcessExecutionError, run_process


def create_directory(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def copy_file(source_path, target_path):
    try:
        shutil.copy(source_path, target_path)
    except OSError as exc:
        raise FileProcessingError(f"Unable to copy file to {target_path}") from exc


def check_file_exists(folder, filename_without_extension):
    matching_files = glob.glob(os.path.join(folder, filename_without_extension + ".*"))
    return matching_files[0] if matching_files else None


class FileService:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

    def transfer_files(self, source_path, destination_path, delete_original=False, compress=True, log_events=False):
        if os.name == "nt":
            self._shutil_copy(source_path, destination_path, delete_original)
            return
        log_file = open(self.log_file_path, "a") if log_events else None
        try:
            self._rsync(source_path, destination_path, delete_original, compress, log_file)
        finally:
            if log_file:
                log_file.close()

    def _rsync(self, source_path, destination_path, delete_original, compress, log_file=None):
        command = ["rsync", "-a", "--info=progress2"]
        if compress:
            command.append("-z")
        command.extend([source_path, destination_path])
        if delete_original:
            command.append("--remove-source-files")
        if log_file:
            log_file.write(f"Command: {shlex.join(command)}\n")
        try:
            run_command(command, log_file)
        except (OSError, ProcessExecutionError, ValueError) as exc:
            raise FileProcessingError("Error transferring files") from exc

    _rsync2 = _rsync

    def _shutil_copy(self, source_path, destination_path, delete_original):
        try:
            shutil.copytree(source_path, destination_path)
            if delete_original:
                shutil.rmtree(source_path)
        except OSError as exc:
            raise FileProcessingError("Error transferring files") from exc

    def run_command(self, command: Sequence[str]):
        return run_command(command)


async def download_file(file_path: str):
    return FileResponse(path=file_path, filename=os.path.basename(file_path))


def run_command(command: Sequence[str], log_file=None):
    """Run an argv command through the audited process boundary."""
    result = run_process(command)
    for line in ((result.stdout or "") + "\n" + (result.stderr or "")).splitlines():
        if line and log_file:
            log_file.write(line + "\n")
    return result
