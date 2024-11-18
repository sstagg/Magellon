import os

categories = ['Best', 'Decent', 'Acceptable', 'Bad', 'Unusable']
category_mapping = {1: 'Best', 2: 'Decent', 3: 'Acceptable', 4: 'Bad', 5: 'Unusable'}

async def extractCommand(output_directory, subfolder_path):
    extractmrcfilepath = os.path.join(os.getcwd(),"2dclass_evaluator","ClassAvgLabeling","extract_mrc.py")
    command = f"python {extractmrcfilepath} --directory {output_directory} --job-dir {subfolder_path}"
    return command


def set_permissions(path, permissions):
    """
    Sets the specified permissions on the file or directory.
    
    :param path: Path to the file or directory.
    :param permissions: Permissions to set in octal format (e.g., 0o775).
    """
    try:
        os.chmod(path, permissions)
        print(f"Permissions {oct(permissions)} set for {path}")
    except Exception as e:
        print(f"Error setting permissions for {path}: {e}")