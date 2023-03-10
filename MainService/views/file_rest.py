from pathlib import Path

from flask import jsonify
from pydantic import BaseModel

from services.file_helper import FileHelper


class TransferInput(BaseModel):
    source: str
    target: str
    delete: bool = False


def transfer_file_and_dir(input_data):
    """
    Transfer files and directories from source path to target path.

    Returns:
        JSON object with transfer status message.
    """
    source_path = Path(input_data.source)
    target_path = Path(input_data.target)
    # Check if source path exists and is a directory
    if not source_path.is_dir():
        return jsonify({'error': 'Source path is not a directory.'}), 400
    # Create target path if it doesn't exist
    if not target_path.exists():
        target_path.mkdir(parents=True)
    # Transfer files and directories using FileHelper
    file_helper = FileHelper(source_path, target_path)
    transfer_count = file_helper.transfer_files_and_directories()
    # Delete source path if requested
    if input_data.delete:
        file_helper.delete_source()
    return jsonify({'message': f'{transfer_count} files and directories transferred successfully.'}), 200
