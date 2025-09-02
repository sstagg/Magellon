# Add these to your existing models/pydantic_models.py file

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FileCopyMode(str, Enum):
    """File handling mode for MRC files"""
    COPY = "copy"
    SYMLINK = "symlink"


class RelionStarFileGenerationRequest(BaseModel):
    """Request model for RELION star file generation from database session"""
    session_name: str = Field(..., description="Name of the session to export")
    output_directory: str = Field(..., description="Output directory path")
    magnification: Optional[int] = Field(..., description="filtering with magnification")
    has_movie: Optional[bool] = Field(..., description="filtering those who have movies")
    file_copy_mode: FileCopyMode = Field(  default=FileCopyMode.SYMLINK,     description="How to handle MRC files (copy or symlink)"    )
    source_mrc_directory: Optional[str] = Field("images",         description="Source directory containing MRC files (optional)"    )


class RelionStarFileGenerationResponse(BaseModel):
    """Response model for RELION star file generation"""
    success: bool
    message: str
    star_file_path: str
    micrographs_directory: str
    total_micrographs: int
    total_optics_groups: int
    processed_files: int = Field(0, description="Number of MRC files processed")


class RelionSessionValidationResponse(BaseModel):
    """Response model for session validation"""
    valid: bool
    message: str
    total_images: Optional[int] = None
    session_id: Optional[str] = None