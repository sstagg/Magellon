import os
import shutil
import subprocess

from starlette.responses import FileResponse


class FileService:
    def __init__(self):
        pass

    def transfer_files(self, source_path, destination_path, delete_original=False):
        if os.name == "nt":
            self._shutil_copy(source_path, destination_path, delete_original)
        else:
            self._rsync(source_path, destination_path, delete_original, True)

    def _rsync(self, source_path, destination_path, delete_original, compress):
        args = ["rsync", "-a", "--info=progress2"]
        if compress:
            args += ["-z"]
        args += [source_path, destination_path]
        if delete_original:
            args.append("--remove-source-files")
        try:
            subprocess.run(args, check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error transferring files: {e}")

    def _shutil_copy(self, source_path, destination_path, delete_original):
        try:
            shutil.copytree(source_path, destination_path)
            if delete_original:
                shutil.rmtree(source_path)
        except Exception as e:
            raise Exception(f"Error transferring files: {e}")


async def download_file(file_path: str):
    return FileResponse(path=file_path, filename=file_path.split("/")[-1])
