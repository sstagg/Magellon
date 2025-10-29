import json
import re
import os
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import Depends, HTTPException
import shutil
from core.helper import custom_replace, dispatch_ctf_task
from database import get_db
from models.pydantic_models import SerialEMImportTaskDto
from models.sqlalchemy_models import Image, Msession, Project, ImageJob, ImageJobTask
from config import DEFECTS_SUB_URL, FFT_SUB_URL, GAINS_SUB_URL, IMAGE_SUB_URL, MAGELLON_HOME_DIR, MAGELLON_JOBS_DIR, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX, app_settings, ATLAS_SUB_URL, CTF_SUB_URL

import logging
from services.file_service import copy_file
from services.importers.BaseImporter import BaseImporter, FileError, TaskFailedException
from services.mrc_image_service import MrcImageService
import mrcfile
import tifffile
import numpy as np
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
logger = logging.getLogger(__name__)
mont_block_re = re.compile(r'\[MontSection\s*=\s*(\d+)\](.*?)(?=\[MontSection|\Z)', re.DOTALL)
zval_re = re.compile(
    r'\[ZValue\s*=\s*(\d+)\].*?'
    r'PieceCoordinates\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+).*?'
    r'NavigatorLabel\s*=\s*(\S+).*?'
    r'(?:AlignedPieceCoords\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+).*?)?'
    r'(?:XedgeDxyVS\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+).*?)?'
    r'(?:YedgeDxyVS\s*=\s*([-0-9.eE]+)\s+([-0-9.eE]+))?',
    re.DOTALL
)
# Model for SerialEM metadata
class SerialEMMetadata(BaseModel):
    oid: Optional[str] = None
    name: Optional[str] = None
    file_path: Optional[str] = None
    magnification: Optional[float] = None
    defocus: Optional[float] = None
    dose: Optional[float] = None
    pixel_size: Optional[float] = None
    binning_x: Optional[int] = None
    binning_y: Optional[int] = None
    stage_alpha_tilt: Optional[float] = None
    stage_x: Optional[float] = None
    stage_y: Optional[float] = None
    acceleration_voltage: Optional[float] = None
    atlas_dimxy: Optional[float] = None
    atlas_delta_row: Optional[float] = None
    atlas_delta_column: Optional[float] = None
    level: Optional[str] = None
    previous_id: Optional[str] = None
    spherical_aberration: Optional[float] = None
    session_id: Optional[str] = None

    class Config:
        allow_population_by_field_name = True

class DirectoryStructure(BaseModel):
    name: str
    path: str
    type: str
    children: list = None

def scan_directory(path):
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Path not found")

        if os.path.isfile(path):
            return DirectoryStructure(name=os.path.basename(path), path=path, type="file")

        structure = DirectoryStructure(name=os.path.basename(path), path=path, type="directory", children=[])

        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                structure.children.append(DirectoryStructure(name=item, path=item_path, type="file"))
            elif os.path.isdir(item_path):
                structure.children.append(scan_directory(item_path))

        return structure
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
def find_two_files(directory, file1, file2):
    """
    Search for two specific files in a directory recursively.
    Returns full paths if both files are found, else returns False.
    Handles errors gracefully.
    
    Args:
        directory (str): Directory to search.
        file1 (str): Name of the first file.
        file2 (str): Name of the second file.
    
    Returns:
        tuple(Path, Path) or False
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return False
        
        found = {}
        
        # Check root first
        for f in [file1, file2]:
            file_path = dir_path / f
            if file_path.exists():
                found[f] = file_path
        
        # If any file is still missing, search recursively
        missing_files = [f for f in [file1, file2] if f not in found]
        if missing_files:
            for path in dir_path.rglob('*'):
                if path.name in missing_files:
                    found[path.name] = path
                    missing_files.remove(path.name)
                if not missing_files:
                    break
        
        # Return False if any file is missing
        if len(found) != 2:
            return False
        
        return (found[file1], found[file2])
    
    except Exception:
        return False

def parse_mdoc(file_path: str, settings_file_path: str) -> SerialEMMetadata:
    """Parse a SerialEM .mdoc file and extract metadata"""
    # Define mapping of SerialEM keys to our metadata model
    keys = [
        ('oid', 'oid'),
        ('name', 'name'),
        ('Magnification', 'magnification'),
        ('Defocus', 'defocus'),
        ('TargetDefocus', 'target_defocus'), 
        ('ExposureDose', 'dose'),
        ('PixelSpacing', 'pixel_size'),
        ('Binning', 'binning_x'),
        ('Binning', 'binning_y'),
        ('TiltAngle', 'stage_alpha_tilt'),
        ('StagePosition', 'stage_x'),
        ('StagePosition', 'stage_y'),
        ('Voltage', 'acceleration_voltage'),
        ('atlas_dimxy', 'atlas_dimxy'),
        ('atlas_delta_row', 'atlas_delta_row'),
        ('atlas_delta_column', 'atlas_delta_column'),
        ('level', 'level'),
        ('previous_id', 'previous_id'),
        ('spherical_aberration', 'spherical_aberration'),
        ('session_id', 'session_id')
    ]

    result = {new_key: None for _, new_key in keys}

    try:
        with open(file_path, 'r') as file:
            for line in file:
                match = re.match(r"(\w+) = (.+)", line)
                if match:
                    file_key, value = match.groups()

                    # Handle StagePosition as a special case (it has two values)
                    if file_key == "StagePosition":
                        x, y = map(float, value.split())
                        for orig_key, new_key in keys:
                            if orig_key == "StagePosition":
                                if new_key == "stage_x":
                                    result[new_key] = x
                                elif new_key == "stage_y":
                                    result[new_key] = y
                    else:
                        for orig_key, new_key in keys:
                            if orig_key == file_key:
                                try:
                                    result[new_key] = float(value) if '.' in value or value.isdigit() else value
                                except ValueError:
                                    result[new_key] = value
        if result.get("target_defocus") is not None:
            result["defocus"] = result["target_defocus"] * 10 ** -6
        else:
            result["defocus"] = result["defocus"] * 10 ** -6
        # Todo get the spherical abbrevation from the settings file
        # it will be like ctffindParams[5]

        
    except Exception as e:
        logger.error(f"Error parsing mdoc file {file_path}: {str(e)}")
    try:
        with open(settings_file_path, 'r') as settings_file:
           for line in settings_file:
            line = line.strip()
            # Check if line starts with CtffindParams
            if line.startswith("CtffindParams"):
                parts = line.split()
                # 5th value has index 5 (0-based)
                result['spherical_aberration'] = float(parts[5])
                break
    except Exception as e:
        logger.error(f"Error reading settings file {settings_file_path}: {str(e)}")

    # Set file path
    result['file_path'] = file_path

    # Set name if not found in the file
    if not result['name']:
        result['name'] = os.path.splitext(os.path.basename(file_path))[0]
    # TOdo convert required strings to float

    return SerialEMMetadata(**result)
def extract_navigator_label(mdoc_path: str) -> str | None:
    """
    Reads an .mdoc file and returns the NavigatorLabel if present.
    If multiple NavigatorLabels exist, returns the first one.
    """
    if not os.path.exists(mdoc_path):
        return None

    with open(mdoc_path, "r") as f:
        for line in f:
            if line.strip().startswith("NavigatorLabel"):
                # line looks like: NavigatorLabel = MyLabel
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return None
def parse_directory(directory_structure, settings_file_path, default_params, unique_navigator_labels):
    try:
        metadata_list = []
        navigator_dict = {}
        valid_extensions = (".tif", ".tiff", ".eer", ".mrc")

        def extract_navigator_label(mdoc_path: str):
            """Read .mdoc file again and extract NavigatorLabel if present."""
            try:
                with open(mdoc_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip().startswith("NavigatorLabel"):
                            # line format looks like: NavigatorLabel = SomeValue
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                return parts[1].strip()
            except Exception as e:
                logger.error(f"Failed to read NavigatorLabel from {mdoc_path}: {e}")
            return None
        def traverse_directory(structure):
            if structure.type == "file" and structure.name.endswith(".mdoc"):
                clean_path = structure.path.strip()
                image_path = os.path.splitext(clean_path)[0]  # removes ".mdoc"

                if os.path.exists(image_path) and image_path.lower().endswith(valid_extensions):
                    navigator_label = extract_navigator_label(clean_path)

                    

                    
                    metadata = parse_mdoc(clean_path, settings_file_path)
                    metadata_dict = metadata.__dict__.copy()
                    metadata_dict["file_path"] = image_path
                    metadata_dict["name"] = os.path.splitext(os.path.basename(image_path))[0]

                    metadata_list.append(SerialEMMetadata(**metadata_dict))

                    # Always update navigator_dict if label exists
                    if navigator_label:
                        navigator_dict.setdefault(navigator_label, set()).add(os.path.splitext(os.path.basename(image_path))[0]
)

                else:
                    logger.warning(f"Skipping {structure.path}, no matching image: {image_path}")

            elif structure.type == "directory" and structure.children:
                for child in structure.children:
                    traverse_directory(child)

        traverse_directory(directory_structure)
        return metadata_list, navigator_dict

    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.error(f"Unexpected error while parsing directory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")




# def get_frame_file(source_image_path):
#     # Get the base name of the source image without extension
#     base_name = os.path.splitext(source_image_path)[0]

#     # Common frame file extensions
#     frame_extensions = ['.tif','.frames', '.eer', '.tiff']

#     # Check for frame files with common extensions
#     for ext in frame_extensions:
#         frame_path = f"{base_name}{ext}"
#         if os.path.exists(frame_path):
#             return frame_path

#     return None
def stitch_mmm(pieces, mrc_path, option="AlignedPieceCoordsVS"):
        if option not in ("PieceCoordinates", "AlignedPieceCoords", "AlignedPieceCoordsVS"):
            raise ValueError(f"Unknown option: {option}")
        with mrcfile.mmap(mrc_path, permissive=True) as mrc:
            slices = [mrc.data[piece['sequence']] for piece in pieces]

        coords = []
        for piece in pieces:
            if option not in piece:
                x, y = piece["PieceCoordinates"][1], piece["PieceCoordinates"][0]
            else:
                x, y = piece[option][1], piece[option][0]
                if x < -1_000_000_000 or y < -1_000_000_000:
                    x, y = piece["PieceCoordinates"][1], piece["PieceCoordinates"][0]
            coords.append((x, y))

        piece_stageXYs = [piece['StagePosition'] if 'StagePosition' in piece else (0,0) for piece in pieces]

        shapes = [slice.shape for slice in slices]

        min_y = min(y for (y, x) in coords)
        min_x = min(x for (y, x) in coords)

        offset_y = -min_y if min_y < 0 else 0
        offset_x = -min_x if min_x < 0 else 0

        max_y = max(y + shape[0] for (y, x), shape in zip(coords, shapes))
        max_x = max(x + shape[1] for (y, x), shape in zip(coords, shapes))

        montage_shape = (int(offset_y + max_y), int(offset_x + max_x))

        montage = np.zeros(montage_shape, dtype=np.int16)

        piece_CenterCoords = []
        for slice, (y, x) in zip(slices, coords):
            h, w = slice.shape
            y_off, x_off = y + offset_y, x + offset_x
            montage[int(y_off):int(y_off) + int(h), int(x_off):int(x_off) + int(w)] = slice

            piece_CenterCoords.append([x_off + w / 2, y_off + h / 2])

        return montage, piece_stageXYs, piece_CenterCoords
def parse_mmm_mdoc(mdoc_text):
    montages = []
    navigator_labels = set()  # to store unique labels

    for mont_match in mont_block_re.finditer(mdoc_text):
        block = mont_match.group(2)
        coords_list = []

        for z_match in zval_re.finditer(block):
            z_idx = int(z_match.group(1))
            piece_x, piece_y = float(z_match.group(2)), float(z_match.group(3))
            navigator_label = z_match.group(4)
            navigator_labels.add(navigator_label)  # add to set

            if z_match.group(5) and z_match.group(6):
                aligned_x, aligned_y = float(z_match.group(5)), float(z_match.group(6))
            else:
                aligned_x, aligned_y = piece_x, piece_y

            x_edge_offset = float(z_match.group(7)) if z_match.group(7) else 0
            y_edge_offset = float(z_match.group(9)) if z_match.group(9) else 0

            coords_list.append({
                'ZValue': z_idx,
                'NavigatorLabel': navigator_label,
                'PieceCoordinates': (piece_x, piece_y),
                'AlignedPieceCoords': (aligned_x, aligned_y),
                'XedgeDxyVS': x_edge_offset,
                'YedgeDxyVS': y_edge_offset,
                'sequence': z_idx
            })

        coords_list.sort(key=lambda d: d['ZValue'])
        for i in range(0, len(coords_list), 24):
            group = coords_list[i:i+24]
            if group:
                montages.append(group)

    return montages, navigator_labels

def find_parent_with_partial_child(child_pattern, image_dict, unique_labels, session_name):
    
    child_pattern = child_pattern.strip()
    # If child_pattern starts with session_name, strip the prefix
    if child_pattern.startswith(f"{session_name}_"):
        normalized_pattern = child_pattern[len(session_name) + 1:]
    else:
        normalized_pattern = child_pattern
    # If normalized pattern is in unique_labels, it's itself a parent
    if normalized_pattern in unique_labels:
        return None

    # Otherwise, search inside dictionary values
    for key, values in image_dict.items():
        for val in values:
            if re.search(re.escape(normalized_pattern), val):
                return key  # return the parent key

    return None# not found

def convert_tiff_to_mrc(moviename: str, gainname: str, outname: str) -> str:
    """
    Process a movie (TIFF) and gain reference (MRC), then output a summed MRC file.

    Args:
        moviename (str): Path to input TIFF movie.
        gainname (str): Path to input gain MRC file.
        outname (str): Path to output MRC file.

    Returns:
        str: Path to the output file if successful.

    Raises:
        ValueError: If input shapes don’t match or writing fails.
    """
    try:
        # Read movie and convert to float32
        os.makedirs(os.path.dirname(outname), exist_ok=True)
        movie = tifffile.imread(moviename).astype(np.float32)
        gain = mrcfile.read(gainname)
        # Flip gain for alignment (adjust as per your dataset)
        gain = np.fliplr(gain)

        print("Movie dtype/shape:", movie.dtype, movie.shape)
        print("Gain dtype/shape:", gain.dtype, gain.shape)

        if gain.shape != movie.shape[1:]:
            raise ValueError(
                f"Gain shape {gain.shape} must match frame shape {movie.shape[1:]}"
            )

        # Apply gain correction if needed
        # summed = (movie / gain).sum(axis=0)
        summed = movie.sum(axis=0)

        # Write to MRC
        with mrcfile.new(outname, overwrite=True) as m:
            m.set_data(summed.astype(np.float32))

        print("✅ Done! Output written to:", outname)
        return outname

    except Exception as e:
        raise ValueError(f"convertion of tiff to mrc failed- premade image for ctf: {str(e)}") from e
    
def find_nav_file(directory: str) -> str | None:
    """
    Recursively search for a .nav file in the given directory.

    Args:
        directory (str): The root directory to search in.

    Returns:
        str | None: The full path to the first .nav file found, or None if not found.
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".nav"):
                return os.path.join(root, file)
    return None

class SerialEmImporter(BaseImporter):
    """Handles SerialEM data import with proper error handling and modular design."""
    
    def __init__(self):
        super().__init__()
        self.image_tasks = []
        self.mrc_service = MrcImageService()
    
    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        """Main entry point for the import process."""
        try:
            start_time = time.time()
            result = self.create_db_project_session(db_session)
            execution_time = time.time() - start_time
            logger.info(f"Total import process completed in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            logger.error(f"Import process failed: {e}", exc_info=True)
            return {
                'status': 'failure',
                'message': f'Job failed with error: {str(e)}'
            }
    
    def _get_or_create_project(self, db_session: Session) -> Optional[Project]:
        """Get existing project or create new one."""
        if self.params.magellon_project_name is None:
            return None
        
        try:
            project = db_session.query(Project).filter(
                Project.name == self.params.magellon_project_name
            ).first()
            
            if not project:
                project = Project(name=self.params.magellon_project_name)
                db_session.add(project)
                db_session.commit()
                db_session.refresh(project)
                logger.info(f"Created new project: {self.params.magellon_project_name}")
            else:
                logger.info(f"Using existing project: {self.params.magellon_project_name}")
            
            return project
        except Exception as e:
            logger.error(f"Failed to get/create project: {e}", exc_info=True)
            raise
    
    def _get_or_create_session(
        self, 
        db_session: Session, 
        project: Optional[Project]
    ) -> Optional[Msession]:
        """Get existing session or create new one."""
        if self.params.magellon_session_name is None:
            return None
        
        try:
            session_name = (
                self.params.magellon_session_name or 
                self.params.session_name
            )
            
            session = db_session.query(Msession).filter(
                Msession.name == session_name
            ).first()
            
            if not session:
                if project is None:
                    raise ValueError(
                        "Cannot create session without a valid project"
                    )
                
                session = Msession(
                    name=session_name,
                    project_id=project.oid
                )
                db_session.add(session)
                db_session.commit()
                db_session.refresh(session)
                logger.info(f"Created new session: {session_name}")
            else:
                logger.info(f"Using existing session: {session_name}")
            
            return session
        except Exception as e:
            logger.error(f"Failed to get/create session: {e}", exc_info=True)
            raise

    def _validate_directory_structure(self) -> Tuple[str, str, str]:
        """Validate required directories exist and return paths."""
        try:
            settings_dir = os.path.join(
                self.params.serial_em_dir_path, 
                "settings"
            )
            gains_dir = os.path.join(
                self.params.serial_em_dir_path, 
                "gains"
            )
            medium_mag_dir = os.path.join(
                self.params.serial_em_dir_path, 
                "medium_mag"
            )
            defects_dir = os.path.join(
                self.params.serial_em_dir_path,
                "defects"
            )
            if not os.path.isdir(settings_dir):
                raise FileNotFoundError(
                    f"'settings' folder not found in {self.params.serial_em_dir_path}"
                )
            
            if not os.path.isdir(gains_dir):
                raise FileNotFoundError(
                    f"'gains' folder not found in {self.params.serial_em_dir_path}"
                )
            if not os.path.isdir(medium_mag_dir):
                raise FileNotFoundError(
                    f"'medium_mag' folder not found in {self.params.serial_em_dir_path}"
                )
            
            if not os.path.isdir(defects_dir):
                defects_dir = None
                logger.warning(
                    f"'defects' folder not found in {self.params.serial_em_dir_path}. Continuing without it."
                )

            return settings_dir, gains_dir, medium_mag_dir, defects_dir
        except Exception as e:
            logger.error(f"Directory validation failed: {e}", exc_info=True)
            raise
    
    def _find_settings_file(self, settings_dir: str) -> str:
        """Find the settings .txt file in settings directory."""
        try:
            for fname in os.listdir(settings_dir):
                if fname.endswith('.txt'):
                    settings_path = os.path.abspath(os.path.join(settings_dir, fname))
                    logger.info(f"Found settings file: {settings_path}")
                    return settings_path
            
            raise FileNotFoundError(
                f"No settings .txt file found in: {settings_dir}"
            )
        except OSError as e:
            raise OSError(
                f"Failed to access settings directory {settings_dir}: {e}"
            ) from e
    
    def _find_gains_file(self, gains_dir: str) -> str:
        """Find the first gains file in gains directory."""
        try:
            gains_files = [
                f for f in os.listdir(gains_dir) 
                if os.path.isfile(os.path.join(gains_dir, f))
            ]
            
            if not gains_files:
                raise FileNotFoundError(
                    f"No files found in gains directory: {gains_dir}"
                )
            
            gains_path = os.path.abspath(os.path.join(gains_dir, gains_files[0]))
            logger.info(f"Found gains file: {gains_path}")
            return gains_path
        except OSError as e:
            raise OSError(
                f"Failed to access gains directory {gains_dir}: {e}"
            ) from e
    def _find_defects_file(self, defects_dir: str) -> Optional[str]:
        """Find the first defects file in defects directory."""
        try:
            defects_files = [
                f for f in os.listdir(defects_dir) 
                if os.path.isfile(os.path.join(defects_dir, f))
            ]
            
            if not defects_files:
                logger.info(f"No defects files found in directory: {defects_dir}")
                return None
            
            defects_path = os.path.abspath(os.path.join(defects_dir, defects_files[0]))
            logger.info(f"Found defects file: {defects_path}")
            return defects_path
        except OSError as e:
            logger.error(
                f"Failed to access defects directory {defects_dir}: {e}"
            )
            return None

    def get_mrc_mdoc_pairs(self, medium_mag_dir: str):
        """Return list of dicts containing .mrc and corresponding .mrc.mdoc files."""
        pairs = []
        missing_pairs = []

        try:
            if not os.path.isdir(medium_mag_dir):
                raise FileNotFoundError(f"Directory not found: {medium_mag_dir}")

            files = os.listdir(medium_mag_dir)

            # Filter for .mrc files (exclude .mrc.mdoc)
            mrc_files = [f for f in files if f.endswith(".mrc") ]

            if not mrc_files:
                logger.warning(f"No .mrc files found in directory: {medium_mag_dir}")

            for mrc in mrc_files:
                mdoc = f"{mrc}.mdoc"
                mdoc_path = os.path.join(medium_mag_dir, mdoc)
                mrc_path = os.path.join(medium_mag_dir, mrc)

                if os.path.exists(mdoc_path):
                    pairs.append({
                        "mrc": mrc_path,
                        "mdoc": mdoc_path
                    })
                else:
                    missing_pairs.append(mrc)

            if missing_pairs:
                logger.warning(
                    f"Missing corresponding .mdoc files for the following .mrc files: {missing_pairs}"
                )

            if not pairs:
                logger.warning("No valid .mrc and .mrc.mdoc pairs found in directory.")

            return pairs

        except Exception as e:
            logger.exception(f"Error while fetching MRC-MDOC pairs: {e}")
            raise
    
    def _process_montages(
        self,
        magellon_session_name: str,
        mrc_mdoc_pairs: List[Dict[str, str]]
    ) -> Tuple[List[str], Optional[List], Optional[List]]:
        """Process montage files from a list of MRC-MDOC dictionaries."""
        montage_paths = []
        all_montages = []
        all_unique_labels = set()

        for pair_idx, pair in enumerate(mrc_mdoc_pairs):
            mrc_path = pair.get("mrc")
            mdoc_path = pair.get("mdoc")

            if not mrc_path or not mdoc_path:
                logger.warning(f"Skipping pair {pair_idx}: missing MRC or MDOC path")
                continue

            if not os.path.exists(mrc_path) or not os.path.exists(mdoc_path):
                logger.warning(f"Skipping pair {pair_idx}: files not found ({mrc_path}, {mdoc_path})")
                continue

            logger.info(f"Processing montage pair {pair_idx + 1}/{len(mrc_mdoc_pairs)}: {mdoc_path}")

            try:
                with open(mdoc_path, 'r') as f:
                    mdoc_text = f.read()

                montages, unique_navigator_labels = parse_mmm_mdoc(mdoc_text)
                all_montages.extend(montages)
                all_unique_labels.update(unique_navigator_labels)

                for idx, montage_pieces in enumerate(montages):
                    try:
                        stitched_img, stage_positions, centers = stitch_mmm(
                            montage_pieces,
                            mrc_path,
                            option="AlignedPieceCoords"
                        )

                        filename = os.path.join(
                            os.environ.get("MAGELLON_HOME_PATH", "/magellon"),
                            magellon_session_name,
                            "montages",
                            f"{magellon_session_name}_{montage_pieces[0]['NavigatorLabel']}.mrc"
                        )

                        os.makedirs(os.path.dirname(filename), exist_ok=True)

                        with mrcfile.new(filename, overwrite=True) as mrc:
                            mrc.set_data(stitched_img.astype(np.float32))

                        montage_paths.append(filename)
                        logger.info(f"✅ Saved stitched montage {idx + 1}/{len(montages)}: {filename}")

                    except Exception as e:
                        logger.error(f"Failed to process montage {idx} in pair {pair_idx}: {e}", exc_info=True)
                        continue

            except Exception as e:
                logger.error(f"Failed to parse or process MDOC {mdoc_path}: {e}", exc_info=True)
                continue

        logger.info(f"📂 Successfully processed {len(montage_paths)} montages from {len(mrc_mdoc_pairs)} pairs")
        return montage_paths, all_montages, list(all_unique_labels)

    
    def _copy_gains_file(self, gains_file_path: str, target_directory: str) -> str:
        """Copy gains file to target directory and return filename."""
        try:
            dest_path = os.path.join(target_directory, GAINS_SUB_URL)
            gain_file_name = os.path.basename(gains_file_path)
            
            if not os.path.exists(gains_file_path):
                raise FileNotFoundError(f"Gains file not found: {gains_file_path}")
            
            if os.path.isdir(gains_file_path):
                shutil.copytree(gains_file_path, dest_path, dirs_exist_ok=True)
            else:
                os.makedirs(dest_path, exist_ok=True)
                shutil.copy(gains_file_path, dest_path)
            
            logger.info(f"Copied gains file to: {dest_path}")
            return gain_file_name
        except Exception as e:
            logger.error(f"Failed to copy gains file: {e}", exc_info=True)
            raise
    
    def _copy_defects_file(self, defects_file_path: str, target_directory: str) -> Optional[str]:
        """Copy defects file to defects directory and return filename."""
        try:
            if defects_file_path is None:
                logger.info("No defects file provided, skipping copy.")
                return None
            
            dest_path = os.path.join(target_directory, DEFECTS_SUB_URL)
            defect_file_name = os.path.basename(defects_file_path)
            
            if not os.path.exists(defects_file_path):
                logger.warning(f"Defects file not found: {defects_file_path}, skipping copy.")
                return None
            
            if os.path.isdir(defects_file_path):
                shutil.copytree(defects_file_path, dest_path, dirs_exist_ok=True)
            else:
                os.makedirs(dest_path, exist_ok=True)
                shutil.copy(defects_file_path, dest_path)
            
            logger.info(f"Copied defects file to: {dest_path}")
            return defect_file_name
        except Exception as e:
            logger.error(f"Failed to copy defects file: {e}", exc_info=True)
            return None
    
    def _create_montage_image_entry(
        self,
        montage_path: str,
        magellon_session: Msession,
        job: ImageJob,
        defocus: float = 0.0,
        dose: float = 0.0
    ) -> Tuple[Optional[Image], Optional[ImageJobTask], Optional[object]]:
        """Create database entries for a single montage."""
        try:
            filename = os.path.splitext(os.path.basename(montage_path))[0]
            task_id = uuid.uuid4()
            
            db_image = Image(
                oid=uuid.uuid4(),
                name=filename,
                magnification=self.params.default_data.magnification,
                defocus=defocus,
                dose=dose,
                pixel_size=self.params.default_data.pixel_size * 10**-10,
                binning_x=1,
                binning_y=1,
                stage_x=0.0,
                stage_y=0.0,
                stage_alpha_tilt=0.0,
                atlas_delta_row=0.0,
                atlas_delta_column=0.0,
                acceleration_voltage=self.params.default_data.acceleration_voltage,
                spherical_aberration=self.params.default_data.spherical_aberration,
                session_id=magellon_session.oid
            )
            
            job_item = ImageJobTask(
                oid=uuid.uuid4(),
                job_id=job.oid,
                frame_name=filename,
                frame_path=montage_path,
                image_name=filename,
                image_path=montage_path,
                status_id=1,
                stage=0,
                image_id=db_image.oid,
            )
            
            task = SerialEMImportTaskDto(
                task_id=task_id,
                task_alias=f"montage_{filename}_{job.oid}",
                file_name=filename,
                image_id=db_image.oid,
                image_name=filename,
                frame_name=filename,
                image_path=montage_path,
                frame_path=montage_path,
                job_dto=self.params,
                status=1,
                pixel_size=self.params.default_data.pixel_size * 10**-10,
                acceleration_voltage=self.params.default_data.acceleration_voltage,
                spherical_aberration=self.params.default_data.spherical_aberration
            )
            
            return db_image, job_item, task
            
        except Exception as e:
            logger.error(
                f"Failed to create montage entry for {montage_path}: {e}",
                exc_info=True
            )
            return None, None, None
    
    def _process_metadata_entry(
        self,
        metadata,
        magellon_session: Msession,
        job: ImageJob,
        gain_file_name: str
    ) -> Tuple[Optional[Image], Optional[ImageJobTask], Optional[object]]:
        """Process a single metadata entry and create database objects."""
        try:
            filename = os.path.splitext(os.path.basename(metadata.file_path))[0]
            task_id = uuid.uuid4()
            
            directory_path = os.path.join(
                os.environ.get("MAGELLON_JOBS_PATH", "/jobs"),
                str(task_id)
            )
            
            moviename = metadata.file_path
            gainname = os.path.join(
                self.params.target_directory, 
                GAINS_SUB_URL, 
                gain_file_name
            )
            outname = os.path.join(
                directory_path,
                f"{os.path.splitext(os.path.basename(metadata.file_path))[0]}.mrc"
            )
            
            # Check if file exists and is TIFF format
            if not os.path.exists(moviename):
                logger.warning(f"Movie file not found: {moviename}, skipping")
                return None, None, None
            
            if not moviename.lower().endswith((".tif", ".tiff")):
                logger.warning(f"Unsupported file format (not TIFF): {moviename}, skipping")
                return None, None, None
            
            # Convert TIFF to MRC
            try:
                result_file = convert_tiff_to_mrc(moviename, gainname, outname)
            except Exception as e:
                raise ValueError(
                    f"TIFF to MRC conversion failed for {metadata.file_path}: {e}"
                ) from e
            
            # Create Image database entry
            db_image = Image(
                oid=uuid.uuid4(),
                name=filename,
                magnification=(
                    metadata.magnification if metadata.magnification is not None 
                    else self.params.default_data.magnification
                ),
                defocus=metadata.defocus,
                dose=metadata.dose,
                pixel_size=(
                    metadata.pixel_size * 10**-10 if metadata.pixel_size is not None 
                    else self.params.default_data.pixel_size * 10**-10
                ),
                binning_x=metadata.binning_x,
                binning_y=metadata.binning_y,
                stage_x=metadata.stage_x,
                stage_y=metadata.stage_y,
                stage_alpha_tilt=metadata.stage_alpha_tilt,
                atlas_delta_row=metadata.atlas_delta_row,
                atlas_delta_column=metadata.atlas_delta_column,
                acceleration_voltage=(
                    metadata.acceleration_voltage if metadata.acceleration_voltage is not None 
                    else self.params.default_data.acceleration_voltage
                ),
                spherical_aberration=(
                    metadata.spherical_aberration if metadata.spherical_aberration is not None 
                    else self.params.default_data.spherical_aberration
                ),
                session_id=magellon_session.oid
            )
            
            # Prepare paths
            source_image_path = result_file
            source_frame_path = metadata.file_path
            
            # Handle path replacements if configured
            if all(hasattr(self.params, attr) for attr in ['replace_type', 'replace_pattern', 'replace_with']):
                if self.params.replace_type in ["regex", "standard"]:
                    if source_frame_path:
                        source_frame_path = custom_replace(
                            source_frame_path,
                            self.params.replace_type,
                            self.params.replace_pattern,
                            self.params.replace_with
                        )
                    source_image_path = custom_replace(
                        source_image_path,
                        self.params.replace_type,
                        self.params.replace_pattern,
                        self.params.replace_with
                    )
            
            frame_name = (
                os.path.splitext(os.path.basename(source_frame_path))[0] 
                if source_frame_path else ""
            )
            
            # Create job item
            job_item = ImageJobTask(
                oid=uuid.uuid4(),
                job_id=job.oid,
                frame_name=frame_name,
                frame_path=source_frame_path,
                image_name=os.path.splitext(os.path.basename(source_image_path))[0],
                image_path=source_image_path,
                status_id=1,
                stage=0,
                image_id=db_image.oid,
            )
            
            # Create task
            task = SerialEMImportTaskDto(
                task_id=task_id,
                task_alias=f"lftj_{filename}_{job.oid}",
                file_name=f"{filename}",
                image_id=db_image.oid,
                image_name=os.path.splitext(os.path.basename(source_image_path))[0],
                frame_name=frame_name,
                image_path=source_image_path,
                frame_path=source_frame_path,
                job_dto=self.params,
                status=1,
                pixel_size=(
                    metadata.pixel_size * 10**-10 if metadata.pixel_size is not None 
                    else self.params.default_data.pixel_size * 10**-10
                ),
                acceleration_voltage=(
                    metadata.acceleration_voltage if metadata.acceleration_voltage is not None 
                    else self.params.default_data.acceleration_voltage
                ),
                spherical_aberration=(
                    metadata.spherical_aberration if metadata.spherical_aberration is not None 
                    else self.params.default_data.spherical_aberration
                )
            )
            
            return db_image, job_item, task
            
        except ValueError as e:
            logger.error(
                f"Conversion failed for {metadata.file_path}: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to process metadata entry for {metadata.file_path}: {e}",
                exc_info=True
            )
            return None, None, None
    
    def _establish_parent_child_relationships(
    self,
    db_session: Session,
    db_image_list: List[Image],
    navigator_dict: Dict,
    unique_navigator_labels: List,
    magellon_session_name: str,
    image_dict: Dict[str, uuid.UUID],
    nav_hierarchy: Dict[str, Dict]
):
        if not unique_navigator_labels or not navigator_dict:
            logger.warning(
                "Navigator data not available, skipping parent-child relationship mapping"
            )
            return

        parent_child = {}
        for parent_label, info in nav_hierarchy.items():
            children = info.get("Children", [])
            for child_label in children:
                if child_label in navigator_dict:
                    for img_name in navigator_dict[child_label]:
                        full_child_key = img_name
                        parent_key = f"{magellon_session_name}_{parent_label}"
                        parent_label_clean = parent_label.strip()
                        if parent_label_clean.endswith("-A"):
                            parent_label_clean = parent_label_clean[:-2]
                        parent_key = f"{magellon_session_name}_{parent_label_clean}"
                        if full_child_key in image_dict and parent_key in image_dict:
                            parent_child[image_dict[full_child_key]] = image_dict[parent_key]
                            logger.info(
                                f"Mapped child '{img_name}' to parent '{parent_label}'"
                            )
        

        # Update DB
        if parent_child:
            try:
                logger.info(
                    f"Setting parent-child relationships for {len(parent_child)} images"
                )
                for child_id, parent_id in parent_child.items():
                    db_session.query(Image).filter(
                        Image.oid == child_id
                    ).update({"parent_id": parent_id})
                db_session.commit()
                logger.info("Parent-child relationships successfully established")
            except Exception as e:
                logger.warning(
                    f"Failed to set some parent-child relationships: {e}. Continuing with import."
                )
        else:
            logger.warning("No parent-child relationships identified for this session")

    
    def process_task(self, task_dto: Any) -> Dict[str, str]:
        print(" process_task inside serialem called")
        """
        Process a single import task

        This method handles the standard file processing operations:
        1. Transfer frame file
        2. Copy original image (optional)
        3. Convert to PNG
        4. Compute FFT
        5. Dispatch CTF computation
        6. Dispatch motion correction

        Args:
            task_dto: Task data transfer object

        Returns:
            Dict with status and message
        """
        try:
            # 1. Transfer frame if it exists
            self.transfer_frame(task_dto)

            # 2. Copy original image if specified
            if hasattr(self.params, 'copy_images') and self.params.copy_images:
                self.copy_image(task_dto)

            # Get current image path
            image_path = getattr(task_dto, 'image_path', None)
            if not image_path or not os.path.exists(image_path):
                raise FileError(f"Image file not found: {image_path}")

            # 3. Convert to PNG
            self.convert_image_to_png(image_path)

            # 4. Compute FFT
            self.compute_fft(image_path)
            
            if "/montages/" in image_path.replace("\\", "/").lower():
                logger.info(f"Skipping CTF and MotionCor for montage image: {image_path}")
            else:
                # 5. Compute CTF if needed
                self.compute_ctf(image_path, task_dto)

                # 6. Compute motion correction if frame exists
                frame_name = getattr(task_dto, 'frame_name', '')
                if frame_name:
                    self.compute_motioncor(image_path, task_dto)


            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            logger.error(f"Task processing failed: {str(e)}", exc_info=True)
            raise TaskFailedException(f"Failed to process task: {str(e)}")
    
    def run_tasks(self, task_list: List[Any] = None) -> None:
        """
        Run all processing tasks

        Args:
            task_list: List of task DTOs, if None uses self.task_dto_list
        """
        try:
            tasks = task_list or self.task_dto_list
            if not tasks:
                logger.warning("No tasks to process")
                return

            for task in tasks:
                self.process_task(task)

        except Exception as e:
            logger.error(f"Error running tasks: {str(e)}", exc_info=True)
            raise
    import re

    def parse_nav_file(self, nav_file_path: str, unique_navigator_labels: list[str]) -> dict[str, dict]:
        """
        Parse .nav file to build parent-child relationships based on MapID and DrawnID.

        Args:
            nav_file_path (str): Path to .nav file
            unique_navigator_labels (list[str]): List of navigator labels like ['6', '15', ...]

        Returns:
            dict: { "6-A": {"MapID": <int>, "Children": [<items>]}, ... }
        """
        with open(nav_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Split the file into individual "Item" blocks
        item_blocks = re.findall(r"\[Item\s*=\s*([^\]]+)\](.*?)(?=\[Item|\Z)", content, re.DOTALL)

        items = []
        for item_name, block_content in item_blocks:
            item_info = {"Item": item_name.strip()}
            for line in block_content.strip().splitlines():
                if "=" in line:
                    key, value = [x.strip() for x in line.split("=", 1)]
                    item_info[key] = value
            items.append(item_info)

        # Build lookup dictionaries
        mapid_to_item = {}
        drawnid_to_items = {}

        for item in items:
            if "MapID" in item:
                mapid_to_item[item["Item"]] = item["MapID"]
            if "DrawnID" in item:
                drawnid_to_items.setdefault(item["DrawnID"], []).append(item["Item"])

        # Now link parents (MapID) to children (DrawnID)
        relationships = {}
        for label in unique_navigator_labels:
            parent_label = f"{label}-A"
            parent_item = next((i for i in items if i["Item"] == parent_label), None)

            if parent_item and "MapID" in parent_item:
                map_id = parent_item["MapID"]
                children = drawnid_to_items.get(map_id, [])
                relationships[parent_label] = {"MapID": map_id, "Children": children}

        return relationships

    def create_db_project_session(self, db_session: Session):
        """Main workflow for creating database project/session and importing data."""
        try:
            start_time = time.time()
            
            # Step 1: Get or create project and session
            magellon_project = self._get_or_create_project(db_session)
            magellon_session = self._get_or_create_session(db_session, magellon_project)
            
            if magellon_session is None:
                raise ValueError("Failed to create or retrieve session")
            
            magellon_session_name = (
                self.params.magellon_session_name or 
                self.params.session_name
            )
            session_name = self.params.session_name
            
            # Step 2: Validate directory structure
            settings_dir, gains_dir, medium_mag_dir, defects_dir = self._validate_directory_structure()

            # Step 3: Find required files
            settings_txt_path = self._find_settings_file(settings_dir)
            gains_file_path = self._find_gains_file(gains_dir)
            mrc_mdoc_pairs = self.get_mrc_mdoc_pairs(medium_mag_dir)
            defects_file_path = None
            if defects_dir:
                defects_file_path = self._find_defects_file(defects_dir)

            # Step 4: Scan directory
            
            try:
                files = scan_directory(self.params.serial_em_dir_path)
                logger.info(f"Scanned directory, found files")
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"SerialEM directory not found: {self.params.serial_em_dir_path}"
                ) from e
            
            # Step 5: Process montages
            montage_paths, montages, unique_navigator_labels = self._process_montages(
                magellon_session_name,mrc_mdoc_pairs
            )
            
            # Step 6: Parse metadata
            try:
                metadata_list, navigator_dict = parse_directory(
                    files,
                    settings_txt_path,
                    self.params.default_data.dict(),
                    unique_navigator_labels
                )
                logger.info(f"Parsed {len(metadata_list)} metadata entries")
            except Exception as e:
                logger.error(f"Failed to parse directory metadata: {e}", exc_info=True)
                raise
            
            job = None
            
            if len(metadata_list) > 0:
                # Step 7: Setup target directory
                target_dir = os.path.join(MAGELLON_HOME_DIR, magellon_session_name)
                self.params.target_directory = target_dir
                self.create_directories(target_dir)
                
                # Step 8.1: Copy gains file
                try:
                    gain_file_name = self._copy_gains_file(gains_file_path, target_dir)
                except Exception as e:
                    logger.error(f"Failed to copy gains file: {e}", exc_info=True)
                    raise

                # Step 8.2: Copy defects file
                if defects_file_path:
                    try:
                        defects_file_name = self._copy_defects_file(defects_file_path, target_dir)
                    except Exception as e:
                        logger.error(f"Failed to copy defects file: {e}", exc_info=True)
                        raise
                
                # Step 9: Create job
                try:
                    job = ImageJob(
                        name=f"SerialEM Import: {session_name}",
                        description=f"SerialEM Import for session: {session_name}",
                        created_date=datetime.now(),
                        output_directory=self.params.camera_directory,
                        msession_id=magellon_session.oid
                    )
                    db_session.add(job)
                    db_session.flush()
                    logger.info(f"Created job: {job.name}")
                except Exception as e:
                    logger.error(f"Failed to create job: {e}", exc_info=True)
                    raise
                
                # Initialize lists for batch operations
                db_image_list = []
                db_job_item_list = []
                task_todo_list = []
                image_dict = {}
                
                # Step 10: Process montages
                logger.info(f"Processing {len(montage_paths)} montage entries")
                for montage_path in montage_paths:
                    db_image, job_item, task = self._create_montage_image_entry(
                        montage_path,
                        magellon_session,
                        job,
                        metadata_list[0].defocus,
                        metadata_list[0].dose
                    )
                    
                    if db_image and job_item and task:
                        db_image_list.append(db_image)
                        db_job_item_list.append(job_item)
                        task_todo_list.append(task)
                        image_dict[db_image.name] = db_image.oid
                
                # Step 11: Process metadata entries
                logger.info(f"Processing {len(metadata_list)} metadata entries")
                processed_count = 0
                failed_count = 0
                
                for metadata in metadata_list:
                    try:
                        db_image, job_item, task = self._process_metadata_entry(
                            metadata,
                            magellon_session,
                            job,
                            gain_file_name
                        )
                        
                        if db_image and job_item and task:
                            db_image_list.append(db_image)
                            db_job_item_list.append(job_item)
                            task_todo_list.append(task)
                            image_dict[db_image.name] = db_image.oid
                            processed_count += 1
                    except ValueError as e:
                        # TIFF conversion error - log and re-raise
                        logger.error(
                            f"Conversion failed for {metadata.file_path}: {e}",
                            exc_info=True
                        )
                        failed_count += 1
                        raise
                    except Exception as e:
                        # Other errors - log and continue
                        logger.error(
                            f"Failed to process {metadata.file_path}: {e}",
                            exc_info=True
                        )
                        failed_count += 1
                        continue
                
                logger.info(
                    f"Metadata processing complete: {processed_count} successful, "
                    f"{failed_count} failed"
                )
                
                # Step 12: Save all records
                try:
                    db_session.bulk_save_objects(db_image_list)
                    db_session.bulk_save_objects(db_job_item_list)
                    db_session.commit()
                    logger.info(
                        f"Saved {len(db_image_list)} images and "
                        f"{len(db_job_item_list)} job items to database"
                    )
                except Exception as e:
                    logger.error(f"Failed to save database records: {e}", exc_info=True)
                    raise
                
                # Step 13: Establish parent-child relationships (warning only)
                nav_file = find_nav_file(self.params.serial_em_dir_path)
                if nav_file:
                    
                    # Parse .nav file and build parent-child relationships
                    relationships = self.parse_nav_file(nav_file, unique_navigator_labels)
                    
                    if isinstance(relationships, list):
                        # Convert to dict if parse_nav_file accidentally returns a list
                        relationships = {
                            list(item.keys())[0]: list(item.values())[0]
                            for item in relationships
                        }
                    
                    # Pass parsed relationships into the function
                    self._establish_parent_child_relationships(
                        db_session,
                        db_image_list,
                        navigator_dict,
                        unique_navigator_labels,
                        magellon_session_name,
                        image_dict,
                        relationships 
                    )
                else:
                    logger.info("No .nav file found, skipping parent-child relationship mapping")


                # Step 14: Run tasks if needed
                if getattr(self.params, 'if_do_subtasks', True):
                    try:
                        logger.info(f"Running {len(task_todo_list)} tasks")
                        self.run_tasks(task_todo_list)
                    except Exception as e:
                        logger.error(f"Task execution failed: {e}", exc_info=True)
                        raise
            
            execution_time = time.time() - start_time
            logger.info(f"SerialEM import completed in {execution_time:.2f} seconds")
            
            if job:
                return {
                    'status': 'success',
                    'message': 'Job completed successfully.',
                    'job_id': job.oid
                }
            else:
                return {
                    'status': 'success',
                    'message': 'No valid .mdoc/movie files found, no job created.'
                }
        
        except FileNotFoundError as e:
            error_message = f"File not found error: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'SerialEM import failed: {str(e)}'
            }
        
        except OSError as e:
            error_message = f"OS error while accessing files or directories: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'SerialEM import failed: {str(e)}'
            }
        
        except ValueError as e:
            error_message = f"Data value error: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'SerialEM import failed: {str(e)}'
            }
        
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': error_message
            }