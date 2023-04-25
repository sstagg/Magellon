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

    def _rsync2(self, source_path, destination_path, delete_original, compress):
        cmd = "rsync -a --info=progress2"
        if compress:
            cmd += " -z"
        cmd += f" {source_path} {destination_path}"
        if delete_original:
            cmd += " --remove-source-files"
        try:
            self.run_command(cmd)
        except Exception as e:
            raise Exception(f"Error transferring files: {e}")

    def run_command(self, cmd):
        # Start a new process with the specified command
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while True:
            # Read output and error streams and print them
            output = proc.stdout.readline()
            error = proc.stderr.readline()
            if not output and not error and proc.poll() is not None:
                # The command has finished executing
                break
            if output:
                print(output.decode("utf-8").strip())
            if error:
                print(error.decode("utf-8").strip())

        # Get the return code of the command
        return_code = proc.wait()

        if return_code != 0:
            print("Error: the command failed with return code {}".format(return_code))
        else:
            print("The command has finished executing successfully.")


async def download_file(file_path: str):
    return FileResponse(path=file_path, filename=file_path.split("/")[-1])
