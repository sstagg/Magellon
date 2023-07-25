import glob
import os
import shutil
import subprocess

from starlette.responses import FileResponse


def create_directory(path):
    """
    Creates the directory for the given image path if it does not exist.

    Args:
    image_path (str): The absolute path of the image file.

    Returns:
    None
    """
    try:
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            # Set permissions to 777
            # os.chmod(directory, 0o777)
    except Exception as e:
        print(f"An error occurred while creating the directory: {str(e)}")


def copy_file(source_path, target_path):
    try:
        shutil.copy(source_path, target_path)
        print(f"File copied: {source_path} -> {target_path}")
    except Exception as e:
        print(f"Error copying File: {source_path} -> {target_path}. Error: {str(e)}")
        raise


def check_file_exists(folder, filename_without_extension):
    # file_pattern = os.path.join(folder, filename_without_extension + '.*')
    matching_files = glob.glob(os.path.join(folder, filename_without_extension + '.*'))
    return (matching_files[0]) if matching_files else None
    # return os.path.basename(matching_files[0]) if matching_files else None


class FileService:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

    def transfer_files(self, source_path, destination_path, delete_original=False, compress=True, log_events=False):
        if os.name == "nt":
            self._shutil_copy(source_path, destination_path, delete_original)
        else:
            if log_events:
                with open(self.log_file_path, "a") as log_file:
                    self._rsync2(source_path, destination_path, delete_original, compress, log_file)
            else:
                self._rsync2(source_path, destination_path, delete_original, compress)

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

    def _rsync2(self, source_path, destination_path, delete_original, compress, log_file=None):
        cmd = "rsync -a --info=progress2"
        if compress:
            cmd += " -z"
        cmd += f" {source_path} {destination_path}"
        if delete_original:
            cmd += " --remove-source-files"
        try:
            if log_file:
                log_file.write(f"Command: {cmd}\n")
            run_command(cmd, log_file)
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


def run_command(cmd, log_file=None):
    # Start a new process with the specified command
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    while True:
        # Read output and error streams and write them to the log file
        output = proc.stdout.readline()
        error = proc.stderr.readline()
        if not output and not error and proc.poll() is not None:
            # The command has finished executing
            break
        if output:
            output_str = output.decode("utf-8").strip()
            print(output_str)
            if log_file:
                log_file.write(output_str + "\n")
        if error:
            error_str = error.decode("utf-8").strip()
            print(error_str)
            if log_file:
                log_file.write(error_str + "\n")

    # Get the return code of the command
    return_code = proc.wait()

    if return_code != 0:
        error_msg = "Error: the command failed with return code {}".format(return_code)
        print(error_msg)
        if log_file:
            log_file.write(error_msg + "\n")
    else:
        success_msg = "The command has finished executing successfully."
        print(success_msg)
        if log_file:
            log_file.write(success_msg + "\n")
