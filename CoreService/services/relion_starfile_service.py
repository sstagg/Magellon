import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from decimal import Decimal
from uuid import UUID

import pandas as pd
import starfile
from sqlalchemy.orm import Session

from models.sqlalchemy_models import Msession, Image, ImageMetaData
from models.pydantic_models import RelionStarFileGenerationRequest, FileCopyMode

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
        # Group images by common optical parameters
        optics_groups = {}
        
        for image in images:
            # Create a key based on optical parameters
            key = (
                float(image.pixel_size or 1.0),
                float(image.acceleration_voltage or 300.0),
                float(image.spherical_aberration or 2.7)
            )
            
            if key not in optics_groups:
                optics_groups[key] = {
                    'group_number': len(optics_groups) + 1,
                    'pixel_size': key[0],
                    'voltage': key[1],
                    'spherical_aberration': key[2],
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
                'rlnAmplitudeContrast': 0.1  # Default value
            })
        
        return optics_data
    
    def _generate_micrographs_data(self, images: List[Image], db: Session) -> List[Dict[str, Any]]:
        """Generate micrographs data from images"""
        micrographs_data = []
        
        # Create optics group mapping
        optics_groups = {}
        for image in images:
            key = (
                float(image.pixel_size or 1.0),
                float(image.acceleration_voltage or 300.0),
                float(image.spherical_aberration or 2.7)
            )
            if key not in optics_groups:
                optics_groups[key] = len(optics_groups) + 1
        
        for image in images:
            # Get optics group for this image
            key = (
                float(image.pixel_size or 1.0),
                float(image.acceleration_voltage or 300.0),
                float(image.spherical_aberration or 2.7)
            )
            optics_group = optics_groups[key]
            
            # Get CTF parameters from metadata
            ctf_data = self._get_ctf_data_from_metadata(image, db)
            
            # Build micrograph entry
            micrograph_entry = {
                'rlnMicrographName': f"Micrographs/{Path(image.path).name}",
                'rlnOpticsGroup': optics_group,
                'rlnCtfImage': ctf_data.get('ctf_image', f"CtfFind/Micrographs/{Path(image.path).stem}.ctf:mrc"),
                'rlnDefocusU': float(ctf_data.get('defocus_u', image.defocus or 20000.0)),
                'rlnDefocusV': float(ctf_data.get('defocus_v', image.defocus or 20000.0)),
                'rlnCtfAstigmatism': float(ctf_data.get('astigmatism', 0.0)),
                'rlnDefocusAngle': float(ctf_data.get('defocus_angle', 0.0)),
                'rlnCtfFigureOfMerit': float(ctf_data.get('figure_of_merit', 0.1)),
                'rlnCtfMaxResolution': float(ctf_data.get('max_resolution', 3.0)),
            }
            
            # Add optional ice ring density if available
            if 'ice_ring_density' in ctf_data:
                micrograph_entry['rlnCtfIceRingDensity'] = float(ctf_data['ice_ring_density'])
            
            micrographs_data.append(micrograph_entry)
        
        return micrographs_data
    
    def _get_ctf_data_from_metadata(self, image: Image, db: Session) -> Dict[str, Any]:
        """Extract CTF parameters from image metadata"""
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
                    if metadata.data_json:
                        import json
                        json_data = json.loads(metadata.data_json)
                        ctf_data.update(json_data)
                    elif metadata.data:
                        # Try to parse as float for numeric values
                        try:
                            value = float(metadata.data)
                            if 'defocus' in metadata.name.lower():
                                if 'u' in metadata.name.lower():
                                    ctf_data['defocus_u'] = value
                                elif 'v' in metadata.name.lower():
                                    ctf_data['defocus_v'] = value
                                else:
                                    ctf_data['defocus_u'] = value
                                    ctf_data['defocus_v'] = value
                            elif 'astigmatism' in metadata.name.lower():
                                ctf_data['astigmatism'] = value
                            elif 'angle' in metadata.name.lower():
                                ctf_data['defocus_angle'] = value
                            elif 'resolution' in metadata.name.lower():
                                ctf_data['max_resolution'] = value
                            elif 'merit' in metadata.name.lower() or 'fom' in metadata.name.lower():
                                ctf_data['figure_of_merit'] = value
                        except ValueError:
                            # Not a numeric value, skip
                            pass
                except Exception as e:
                    self.logger.warning(f"Error parsing metadata {metadata.name}: {e}")
        
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
                
            except Exception as e:
                self.logger.error(f"Failed to {copy_mode.value} file {filename}: {str(e)}")
                raise
        
        return processed_count
    
    def validate_session_for_starfile(self, session_name: str, db: Session) -> Dict[str, Any]:
        """Validate that a session can be used for star file generation"""
        try:
            # Check session exists
            msession = db.query(Msession).filter(
                Msession.name == session_name,
                Msession.GCRecord.is_(None)
            ).first()
            
            if not msession:
                return {
                    "valid": False,
                    "message": f"Session '{session_name}' not found"
                }
            
            # Check for MRC images
            images = db.query(Image).filter(
                Image.session_id == msession.oid,
                Image.GCRecord.is_(None),
                Image.path.like('%.mrc')
            ).all()
            
            if not images:
                return {
                    "valid": False,
                    "message": f"No MRC images found for session '{session_name}'"
                }
            
            # Check for required parameters
            missing_params = []
            for image in images:
                if not image.pixel_size:
                    missing_params.append("pixel_size")
                if not image.acceleration_voltage:
                    missing_params.append("acceleration_voltage")
            
            if missing_params:
                return {
                    "valid": False,
                    "message": f"Missing required parameters: {', '.join(set(missing_params))}"
                }
            
            return {
                "valid": True,
                "message": f"Session is valid for star file generation",
                "total_images": len(images),
                "session_id": str(msession.oid)
            }
            
        except Exception as e:
            return {
                "valid": False,
                "message": f"Error validating session: {str(e)}"
            }