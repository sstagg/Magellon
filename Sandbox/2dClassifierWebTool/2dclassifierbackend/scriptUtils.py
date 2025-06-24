import os

REPLACE_INF = 999
categories = ['Best', 'Decent', 'Acceptable', 'Bad', 'Unusable']
category_mapping = {1: 'Best', 2: 'Decent', 3: 'Acceptable', 4: 'Bad', 5: 'Unusable'}


async def extractCommand(output_directory: str, subfolder_path: str) -> str:
    """
    Generate the shell command to run the extract_mrc.py script.
    """
    try:
        extract_script_path = os.path.join(
            os.getcwd(), "2dclass_evaluator", "ClassAvgLabeling", "extract_mrc.py"
        )
        command = f"python {extract_script_path} --directory {output_directory} --job-dir {subfolder_path}"
        return command
    except Exception as e:
        log_error("Failed to build extract command", e)
        raise


def set_permissions(path: str, permissions: int) -> None:
    """
    Set file or directory permissions.
    """
    try:
        os.chmod(path, permissions)
        print(f"Permissions {oct(permissions)} set for {path}")
    except Exception as e:
        log_error(f"Error setting permissions for {path}", e)


def log_error(message: str, exception: Exception) -> None:
    """
    Log errors in a consistent format.
    """
    print(f"[ERROR] {message}: {exception}")


def ensure_directory_exists(path: str) -> None:
    """
    Ensure a directory exists and set appropriate permissions.
    """
    try:
        os.makedirs(path, exist_ok=True)
        set_permissions(path, 0o775)
    except Exception as e:
        log_error(f"Failed to create or set permissions for directory {path}", e)
        raise
