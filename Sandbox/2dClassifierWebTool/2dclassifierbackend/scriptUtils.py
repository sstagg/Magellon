import os
REPLACE_INF = 999
categories = ['Best', 'Decent', 'Acceptable', 'Bad', 'Unusable']
category_mapping = {1: 'Best', 2: 'Decent', 3: 'Acceptable', 4: 'Bad', 5: 'Unusable'}

async def extractCommand(output_directory, subfolder_path):
    extractmrcfilepath = os.path.join(os.getcwd(),"2dclass_evaluator","ClassAvgLabeling","extract_mrc.py")
    command = f"python {extractmrcfilepath} --directory {output_directory} --job-dir {subfolder_path}"
    return command

def set_permissions(path, permissions):
    try:
        os.chmod(path, permissions)
        print(f"Permissions {oct(permissions)} set for {path}")
    except Exception as e:
        print(f"Error setting permissions for {path}: {e}")

def log_error(message: str, exception: Exception):
    print(f"{message}: {exception}")

def ensure_directory_exists(path: str):
    os.makedirs(path, exist_ok=True)
    set_permissions(path, 0o775)