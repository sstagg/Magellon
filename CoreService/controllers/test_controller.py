from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
import tempfile
import os
import logging
import uuid
from typing import Optional

from services.importers.EPUImporter import parse_xml, scan_directory, parse_directory, EPUImporter
from services.importers.SerialEmImporter import parse_mdoc

# from EPUImporter import parse_xml, EPUMetadata, scan_directory, parse_directory
# from models.pydantic_models import EPUImportJobDto

test_router = APIRouter(prefix="/test", tags=["testing"])

logger = logging.getLogger(__name__)

@test_router.post("/parse-xml")
async def test_parse_xml(file: UploadFile = File(...)):
    """
    Test the EPUImporter's XML parsing functionality with an uploaded XML file.
    """
    # Create a temporary file to store the uploaded XML
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)

    try:
        # Write the uploaded file to the temporary location
        with open(temp_file_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)

        # Parse the XML file using EPUImporter's parse_xml function
        result = parse_xml(temp_file_path)

        # Convert to dict for JSON response
        return {"status": "success", "result": result.dict()}
    except Exception as e:
        logger.error(f"Error parsing XML: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error parsing XML: {str(e)}"}
        )
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        os.rmdir(temp_dir)

@test_router.post("/parse-xml-content")
async def test_parse_xml_content(xml_content: str = Form(...)):
    """
    Test the EPUImporter's XML parsing functionality with raw XML content.
    """
    try:
        # Create a temporary file with the XML content
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, "test.xml")

        with open(temp_file_path, "w") as f:
            f.write(xml_content)

        # Parse the XML using the function from EPUImporter
        result = parse_xml(temp_file_path)

        return {"status": "success", "result": result.dict()}
    except Exception as e:
        logger.error(f"Error parsing XML content: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error parsing XML content: {str(e)}"}
        )
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        os.rmdir(temp_dir)

@test_router.post("/scan-directory")
async def test_scan_directory(directory_path: str = Form(...)):
    """
    Test scanning a directory for XML files and parsing them.
    """
    try:
        # Scan the directory
        directory_structure = scan_directory(directory_path)

        # Parse the XML files found in the directory
        metadata_list = parse_directory(directory_structure)

        return {
            "status": "success",
            "files_found": len(metadata_list),
            "results": [metadata.dict() for metadata in metadata_list]
        }
    except Exception as e:
        logger.error(f"Error scanning directory: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error scanning directory: {str(e)}"}
        )

# @test_router.post("/epu-import-job")
# async def test_epu_import_job(
#         epu_dir_path: str = Form(...),
#         session_name: str = Form(...),
#         magellon_project_name: Optional[str] = Form(None),
#         magellon_session_name: Optional[str] = Form(None),
#         replace_type: str = Form("none"),
#         replace_pattern: Optional[str] = Form(None),
#         replace_with: Optional[str] = Form(None),
#         skip_tasks: bool = Form(False)
# ):
#     """
#     Test creating an EPU import job with the provided parameters.
#     """
#     try:
#         from database import get_db
#
#         # Create job parameters
#         job_dto = EPUImportJobDto(
#             job_id=str(uuid.uuid4()),
#             session_name=session_name,
#             epu_dir_path=epu_dir_path,
#             magellon_project_name=magellon_project_name,
#             magellon_session_name=magellon_session_name,
#             replace_type=replace_type,
#             replace_pattern=replace_pattern,
#             replace_with=replace_with,
#             if_do_subtasks=not skip_tasks,
#             task_list=[]
#         )
#
#         # Create an instance of EPUImporter
#         importer = EPUImporter()
#         importer.params = job_dto
#
#         # Get database session
#         db_session = next(get_db())
#
#         # Run the process method
#         result = importer.process(db_session)
#
#         return {"status": "success", "job_id": job_dto.job_id, "result": result}
#     except Exception as e:
#         logger.error(f"Error creating EPU import job: {str(e)}")
#         return JSONResponse(
#             status_code=500,
#             content={"status": "error", "message": f"Error creating EPU import job: {str(e)}"}
#         )




@test_router.post("/parse-mdoc")
async def test_parse_mdoc(file: UploadFile = File(...)):
    """
    Test parsing a SerialEM .mdoc file.
    """
    # Create a temporary file to store the uploaded mdoc
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)

    try:
        # Write the uploaded file to the temporary location
        with open(temp_file_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)

        # Parse the mdoc file
        result = parse_mdoc(temp_file_path)

        # Convert to dict for JSON response
        return {"status": "success", "result": result.dict()}
    except Exception as e:
        logger.error(f"Error parsing SerialEM mdoc: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error parsing SerialEM mdoc: {str(e)}"}
        )
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        os.rmdir(temp_dir)

@test_router.post("/parse-mdoc-content")
async def test_parse_mdoc_content(mdoc_content: str = Form(...)):
    """
    Test parsing raw SerialEM .mdoc content.
    """
    try:
        # Create a temporary file with the mdoc content
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, "test.mdoc")

        with open(temp_file_path, "w") as f:
            f.write(mdoc_content)

        # Parse the mdoc
        result = parse_mdoc(temp_file_path)

        return {"status": "success", "result": result.dict()}
    except Exception as e:
        logger.error(f"Error parsing SerialEM mdoc content: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error parsing SerialEM mdoc content: {str(e)}"}
        )
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        os.rmdir(temp_dir)

