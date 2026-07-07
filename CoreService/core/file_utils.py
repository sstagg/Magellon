"""Small file / string utilities shared by importers and dispatch code.

Split out of ``core.helper`` (2026-07-06); import from here in new code,
``core.helper`` re-exports for existing call sites.
"""
import glob
import os
import re


def append_json_to_file(file_path, json_str):
    try:
        # Append the JSON string as a new line to the file
        with open(file_path, 'a') as file:
            file.write(json_str + '\n')

        return True  # Success
    except Exception as e:
        print(f"Error appending JSON to file: {e}")
        return False  # Failure


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


def custom_replace(input_string, replace_type, replace_pattern, replace_with):
    """
    Function to perform various types of string replacement based on the specified replace_type.

    Parameters:
        input_string (str): The input string to be modified.
        replace_type (str): Type of replacement. Can be 'none', 'normal', or 'regex'.
        replace_pattern (str): Pattern to search for in the input string.
        replace_with (str): String to replace the replace_pattern with.

    Returns:
        str: The modified string after replacement.
    """
    if replace_type == 'none':
        return input_string

    elif replace_type == 'standard':
        return input_string.replace(replace_pattern, replace_with)

    elif replace_type == 'regex':
        return re.sub(replace_pattern, replace_with, input_string)

    else:
        raise ValueError("Invalid replace_type. Use 'none', 'normal', or 'regex'.")


def find_matching_file(base_path, frame_name):
    # Priority order
    extensions_priority = [".eer", ".tiff", ".tif", ".mrc"]

    for ext in extensions_priority:
        pattern = os.path.join(base_path, frame_name + "*" + ext)
        files = glob.glob(pattern)
        if files:
            return files[0]  # return first file matching in priority
    return None
