import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from models.pydantic_models import MagellonImportJobDto


import logging

from services.importers.BaseImporter import BaseImporter
logger = logging.getLogger(__name__)



class MagellonImporter(BaseImporter):
    """
    Concrete implementation of BaseImporter for Magellon microscopy data.
    Handles importing and processing of microscopy images and associated data.
    """

    def __init__(self):
        super().__init__()
        self.params: Optional[MagellonImportJobDto] = None
        self.imported_data: Dict[str, Any] = {}
        # self.tasks: List[MagellonImportTaskDto] = []

    def setup_data(self) -> None:
        """Initialize importer with Magellon-specific parameters"""
        if not hasattr(self.params, 'source_directory'):
            raise ImportError("Source directory not specified")

    def import_data(self) -> Dict[str, Any]:
        """
        Import data from source system.
        Returns a dictionary containing the imported data.
        """
        try:
            # Scan source directory for images
            image_files = self._scan_directory(self.params.source_directory)

            # Parse metadata from files
            self.imported_data = {
                'image_files': image_files,
                'metadata': self._extract_metadata(image_files)
            }

            return self.imported_data

        except Exception as e:
            raise ImportError(f"Failed to import data: {str(e)}")

    def process_imported_data(self) -> None:
        """Process the imported data and create necessary records"""
        try:
            # Create image records
            for image_data in self.imported_data['metadata']:
                image = self._create_image_record(image_data)
                self.image_list.append(image)
                self.image_dict[image.name] = image.oid

            # Set parent-child relationships
            self._set_image_relationships()

            # Create tasks
            self._create_processing_tasks()

            # Save records
            self._save_records()

        except Exception as e:
            raise ImportError(f"Failed to process imported data: {str(e)}")


