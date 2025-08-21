import os
import shutil
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from decimal import Decimal
from uuid import UUID

import pandas as pd
import starfile
from sqlalchemy.orm import Session

from models.sqlalchemy_models import Msession, Image, ImageMetaData
from models.relion_pydantic_models import RelionStarFileGenerationRequest, FileCopyMode

logger = logging.getLogger(__name__)


class RelionStarFileService:
    """Service class for generating RELION star files from database data"""

    def __init__(self):
        self.logger = logger

    def generate_starfile_from_session(
        self,
        session_name: str,
        output_directory: str,
        file_copy_mode: FileCopyMode,
        source_mrc_directory: Optional[str],
        db: Session
    ) -> Dict[str, Any]:
        """
        Generate RELION star file from database session data

        Args:
            session_name: Name of the session to export
            output_directory: Directory where to create the star file
            file_copy_mode: Whether to copy or symlink MRC files
            source_mrc_directory: Source directory containing MRC files
            db: Database session

        Returns:
            Dict containing generation results
        """
        try:
            # Get session from database
            msession = db.query(Msession).filter(
                Msession.name == session_name,
                Msession.GCRecord.is_(None)
            ).first()

            if not msession:
                raise ValueError(f"Session '{session_name}' not found")

            # Get images for this session (filter for micrographs)
            images = db.query(Image).filter(
                Image.session_id == msession.oid,
                Image.GCRecord.is_(None),
                Image.path.like('%.mrc')  # Only MRC files
            ).all()

            if not images:
                raise ValueError(f"No MRC images found for session '{session_name}'")

            # Validate output directory
            output_path = Path(output_directory)
            if not output_path.exists():
                raise ValueError(f"Output directory does not exist: {output_directory}")

            # Create session directory structure
            session_dir = output_path / session_name
            session_dir.mkdir(exist_ok=True)

            micrographs_dir = session_dir / "Micrographs"
            micrographs_dir.mkdir(exist_ok=True)

            # Generate optics and micrographs data
            optics_data = self._generate_optics_data(images, db)
            micrographs_data = self._generate_micrographs_data(images, db)

            # Create DataFrames
            optics_df = pd.DataFrame(optics_data)
            optics_df.name = 'optics'

            micrographs_df = pd.DataFrame(micrographs_data)
            micrographs_df.name = 'micrographs'

            # Prepare star file data
            star_data = {
                'optics': optics_df,
                'micrographs': micrographs_df
            }

            # Generate star file
            star_file_path = session_dir / f"{session_name}_micrographs_ctf.star"
            starfile.write(star_data, star_file_path, float_format='%.6f')

            # Handle MRC files if source directory provided
            processed_files_count = 0
            if source_mrc_directory:
                processed_files_count = self._handle_mrc_files(
                    images, source_mrc_directory, str(micrographs_dir), file_copy_mode
                )

            return {
                "success": True,
                "message": f"Star file generated successfully with {len(images)} micrographs",
                "star_file_path": str(star_file_path),
                "micrographs_directory": str(micrographs_dir),
                "total_micrographs": len(images),
                "total_optics_groups": len(optics_data),
                "processed_files": processed_files_count
            }

        except Exception as e:
            self.logger.error(f"Error generating star file: {str(e)}", exc_info=True)
            raise

    def _generate_optics_data(self, images: List[Image], db: Session) -> List[Dict[str, Any]]:
        """Generate optics group data from images"""
        optics_groups = {}

        for image in images:
            # Get CTF data to extract pixel size
            ctf_data = self._get_ctf_data_from_metadata(image, db)

            # Create a key based on optical parameters
            pixel_size = ctf_data.get('apix', image.pixel_size or 1.0)
            voltage = ctf_data.get('volts', image.acceleration_voltage or 300000.0)
            cs = ctf_data.get('cs', image.spherical_aberration or 2.7)
            amplitude_contrast = ctf_data.get('amplitude_contrast', 0.1)

            key = (float(pixel_size), float(voltage), float(cs), float(amplitude_contrast))

            if key not in optics_groups:
                optics_groups[key] = {
                    'group_number': len(optics_groups) + 1,
                    'pixel_size': key[0],
                    'voltage': key[1] / 1000.0,  # Convert V to kV
                    'spherical_aberration': key[2],
                    'amplitude_contrast': key[3],
                    'count': 0
                }

            optics_groups[key]['count'] += 1

        # Convert to RELION format
        optics_data = []
        for i, (key, group) in enumerate(optics_groups.items(), 1):
            optics_data.append({
                'rlnOpticsGroupName': f'opticsGroup{i}',
                'rlnOpticsGroup': i,
                'rlnMicrographPixelSize': group['pixel_size'],
                'rlnMicrographOriginalPixelSize': group['pixel_size'],
                'rlnVoltage': group['voltage'],
                'rlnSphericalAberration': group['spherical_aberration'],
                'rlnAmplitudeContrast': group['amplitude_contrast']
            })

        return optics_data

    def _generate_micrographs_data(self, images: List[Image], db: Session) -> List[Dict[str, Any]]:
        """Generate micrographs data from images"""
        micrographs_data = []

        # Create optics group mapping
        optics_groups = {}
        for image in images:
            ctf_data = self._get_ctf_data_from_metadata(image, db)
            pixel_size = ctf_data.get('apix', image.pixel_size or 1.0)
            voltage = ctf_data.get('volts', image.acceleration_voltage or 300000.0)
            cs = ctf_data.get('cs', image.spherical_aberration or 2.7)
            amplitude_contrast = ctf_data.get('amplitude_contrast', 0.1)

            key = (float(pixel_size), float(voltage), float(cs), float(amplitude_contrast))
            if key not in optics_groups:
                optics_groups[key] = len(optics_groups) + 1

        for image in images:
            # Get optics group for this image
            ctf_data = self._get_ctf_data_from_metadata(image, db)
            pixel_size = ctf_data.get('apix', image.pixel_size or 1.0)
            voltage = ctf_data.get('volts', image.acceleration_voltage or 300000.0)
            cs = ctf_data.get('cs', image.spherical_aberration or 2.7)
            amplitude_contrast = ctf_data.get('amplitude_contrast', 0.1)

            key = (float(pixel_size), float(voltage), float(cs), float(amplitude_contrast))
            optics_group = optics_groups[key]

            # Convert defocus from meters to Angstroms (if needed)
            defocus_u = ctf_data.get('defocus1', image.defocus or 20000.0)
            defocus_v = ctf_data.get('defocus2', image.defocus or 20000.0)

            # If defocus values are in meters (scientific notation), convert to Angstroms
            if isinstance(defocus_u, float) and defocus_u < 1.0:
                defocus_u = defocus_u * 1e10  # Convert from meters to Angstroms
            if isinstance(defocus_v, float) and defocus_v < 1.0:
                defocus_v = defocus_v * 1e10  # Convert from meters to Angstroms

            # Calculate astigmatism and angle
            astigmatism = abs(defocus_u - defocus_v)
            defocus_angle = ctf_data.get('angle_astigmatism', 0.0)

            # Convert radians to degrees if needed
            if abs(defocus_angle) < 6.28:  # Likely in radians (< 2π)
                defocus_angle = defocus_angle * 180.0 / 3.14159

            # Get other CTF parameters
            figure_of_merit = ctf_data.get('confidence', 0.1)
            max_resolution = ctf_data.get('resolution_80_percent', 3.0)

            # Build micrograph entry
            micrograph_entry = {
                'rlnMicrographName': f"Micrographs/{Path(image.path).name}",
                'rlnOpticsGroup': optics_group,
                'rlnCtfImage': f"CtfFind/job005/Micrographs/{Path(image.path).stem}.ctf:mrc",
                'rlnDefocusU': float(defocus_u),
                'rlnDefocusV': float(defocus_v),
                'rlnCtfAstigmatism': float(astigmatism),
                'rlnDefocusAngle': float(defocus_angle),
                'rlnCtfFigureOfMerit': float(figure_of_merit),
                'rlnCtfMaxResolution': float(max_resolution),
            }

            # Add optional ice ring density if available
            ice_ring_density = ctf_data.get('ice_ring_density')
            if ice_ring_density is not None:
                micrograph_entry['rlnCtfIceRingDensity'] = float(ice_ring_density)

            micrographs_data.append(micrograph_entry)

        return micrographs_data

    def _get_ctf_data_from_metadata(self, image: Image, db: Session) -> Dict[str, Any]:
        """Extract CTF parameters from image metadata

        Handles the specific format where metadata.data contains JSON like:
        [{"key": "CTF", "value": "{\"volts\": 300000.0, \"cs\": 2.7, ...}"}]
        """
        ctf_data = {}

        # Query metadata for this image
        metadata_entries = db.query(ImageMetaData).filter(
            ImageMetaData.image_id == image.oid,
            ImageMetaData.GCRecord.is_(None)
        ).all()

        for metadata in metadata_entries:
            # Look for CTF-related metadata
            if metadata.name and 'ctf' in metadata.name.lower():
                try:
                    # First try to parse data_json if available
                    if metadata.data_json:
                        json_data = json.loads(metadata.data_json) if isinstance(metadata.data_json, str) else metadata.data_json
                        if isinstance(json_data, list):
                            for item in json_data:
                                if isinstance(item, dict) and item.get('key') == 'CTF':
                                    ctf_json = json.loads(item.get('value', '{}'))
                                    ctf_data.update(ctf_json)
                        else:
                            ctf_data.update(json_data)

                    # Also try parsing from data field
                    elif metadata.data:
                        # Try to parse as JSON array first
                        try:
                            data_list = json.loads(metadata.data)
                            if isinstance(data_list, list):
                                for item in data_list:
                                    if isinstance(item, dict) and item.get('key') == 'CTF':
                                        ctf_json = json.loads(item.get('value', '{}'))
                                        ctf_data.update(ctf_json)
                            else:
                                ctf_data.update(data_list)
                        except json.JSONDecodeError:
                            # Try to parse as float for numeric values
                            try:
                                value = float(metadata.data)
                                if 'defocus' in metadata.name.lower():
                                    if 'u' in metadata.name.lower():
                                        ctf_data['defocus1'] = value
                                    elif 'v' in metadata.name.lower():
                                        ctf_data['defocus2'] = value
                                    else:
                                        ctf_data['defocus1'] = value
                                        ctf_data['defocus2'] = value
                                elif 'astigmatism' in metadata.name.lower():
                                    ctf_data['angle_astigmatism'] = value
                                elif 'resolution' in metadata.name.lower():
                                    ctf_data['resolution_80_percent'] = value
                                elif 'confidence' in metadata.name.lower():
                                    ctf_data['confidence'] = value
                            except ValueError:
                                # Not a numeric value, skip
                                pass

                except Exception as e:
                    self.logger.warning(f"Error parsing CTF metadata for image {image.name}: {e}")

        return ctf_data

    def _handle_mrc_files(
        self,
        images: List[Image],
        source_directory: str,
        target_directory: str,
        copy_mode: FileCopyMode
    ) -> int:
        """Handle copying or symlinking of MRC files"""
        processed_count = 0

        for image in images:
            filename = Path(image.path).name
            source_path = Path(source_directory) / filename
            target_path = Path(target_directory) / filename

            if not source_path.exists():
                self.logger.warning(f"Source MRC file not found: {source_path}")
                continue

            try:
                if copy_mode == FileCopyMode.COPY:
                    shutil.copy2(source_path, target_path)
                else:  # SYMLINK
                    if target_path.exists():
                        target_path.unlink()
                    target_path.symlink_to(source_path.absolute())

                processed_count += 1
                self.logger.info(f"Processed MRC file: {filename}")

            except Exception as e:
                self.logger.error(f"Error processing MRC file {filename}: {e}")

        return processed_count

    def validate_session_for_starfile(self, session_name: str, db: Session) -> Dict[str, Any]:
        """Validate that a session can be used for RELION star file generation"""
        try:
            # Get session from database
            msession = db.query(Msession).filter(
                Msession.name == session_name,
                Msession.GCRecord.is_(None)
            ).first()

            if not msession:
                return {
                    "valid": False,
                    "message": f"Session '{session_name}' not found",
                    "total_images": None,
                    "session_id": None
                }

            # Get images for this session
            images = db.query(Image).filter(
                Image.session_id == msession.oid,
                Image.GCRecord.is_(None),
                Image.path.like('%.mrc')
            ).all()

            if not images:
                return {
                    "valid": False,
                    "message": f"No MRC images found for session '{session_name}'",
                    "total_images": 0,
                    "session_id": str(msession.oid)
                }

            # Check for CTF metadata availability
            ctf_count = 0
            for image in images:
                ctf_data = self._get_ctf_data_from_metadata(image, db)
                if ctf_data:
                    ctf_count += 1

            if ctf_count == 0:
                return {
                    "valid": False,
                    "message": f"No CTF metadata found for images in session '{session_name}'",
                    "total_images": len(images),
                    "session_id": str(msession.oid)
                }

            return {
                "valid": True,
                "message": f"Session '{session_name}' is valid for star file generation. Found {len(images)} images with {ctf_count} having CTF data.",
                "total_images": len(images),
                "session_id": str(msession.oid)
            }

        except Exception as e:
            self.logger.error(f"Error validating session: {str(e)}", exc_info=True)
            return {
                "valid": False,
                "message": f"Error validating session: {str(e)}",
                "total_images": None,
                "session_id": None
            }