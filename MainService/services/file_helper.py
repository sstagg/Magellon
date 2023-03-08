import shutil
from pathlib import Path


class FileHelper:
    def __init__(self, source_path: Path, target_path: Path, delete=False):
        self.source_path = source_path
        self.target_path = target_path
        self.delete = delete

    def transfer_files_and_directories(self) -> int:
        transfer_count = 0
        for path in self.source_path.glob('**/*'):
            target_file_path = self.target_path / path.relative_to(self.source_path)
            if path.is_dir():
                target_file_path.mkdir(exist_ok=True)
            else:
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                target_file_path.write_bytes(path.read_bytes())
            transfer_count += 1
        return transfer_count

    def copy_files(self, source_path, target_path):
        try:
            shutil.copytree(source_path, target_path)
            print("Files copied successfully!")
            if self.delete:
                shutil.rmtree(source_path)
                print("Source directory and its contents deleted successfully!")
        except Exception as e:
            print(f"Error copying files: {e}")

    def copy_rsync_files(self, source_path, target_path):
        try:
            # construct rsync command
            rsync_cmd = ["rsync", "-avz", "--progress", source_path, target_path]

            # execute rsync command
            subprocess.run(rsync_cmd, check=True)

            # delete source directory if specified
            if self.delete:
                rm_cmd = ["rm", "-rf", source_path]
                subprocess.run(rm_cmd, check=True)

            print("Files copied successfully!")
        except Exception as e:
            print(f"Error copying files: {e}")
    def delete_source(self):
        for path in self.source_path.glob('**/*'):
            path.unlink() if path.is_file() else path.rmdir()
        self.source_path.rmdir()
