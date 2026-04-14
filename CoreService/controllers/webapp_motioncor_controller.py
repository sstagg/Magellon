import asyncio
import io
import json
import mimetypes
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from uuid import UUID

import mrcfile
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from pathlib import Path
from starlette.responses import FileResponse, StreamingResponse

from config import app_settings
from core.helper import dispatch_ctf_task, create_motioncor_task
from dependencies.auth import get_current_user_id
from services.mrc_image_service import MrcImageService

import logging

motioncor_router = APIRouter()

logger = logging.getLogger(__name__)


@motioncor_router.get('/do_ctf')
async def get_do_image_ctf_route(
    full_image_path: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Dispatch a CTF (Contrast Transfer Function) processing task.

    **Requires:** Authentication
    **Security:** Authenticated users can trigger CTF processing
    **Note:** This is a CPU-intensive operation
    """
    logger.info(f"User {user_id} dispatching CTF task for image: {full_image_path}")

    # full_image_path="/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"
    # session_name = "23oct13x"
    # file_name = "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex"

    # Extract file name without extension
    result = await dispatch_ctf_task(uuid.uuid4(), full_image_path)
    logger.info(f"User {user_id} successfully dispatched CTF task for: {full_image_path}")
    return result




class DirectoryNode(BaseModel):
    id: str
    label: str
    abs_path: str  # Absolute path for each directory or file
    children: Optional[List["DirectoryNode"]] = None

def get_directory_structure(root_path: str) -> List[DirectoryNode]:
    if not os.path.isdir(root_path):
        raise HTTPException(status_code=400, detail="Invalid root directory path")

    def build_tree(path: str) -> DirectoryNode:
        label = os.path.basename(path) or path  # Root may not have a basename

        node_id = str(uuid.uuid4())  # Unique ID for each node
        children = []

        try:
            for entry in os.scandir(path):
                if entry.is_dir():
                    children.append(build_tree(entry.path))
                elif entry.is_file() and (entry.name.endswith('.mrc') or entry.name.endswith('.tiff')):
                    # Including the absolute path for each file
                    children.append(DirectoryNode(id=str(uuid.uuid4()), label=entry.name, abs_path=entry.path))
        except PermissionError:
            pass  # Skip directories/files that can't be accessed

        # Return node with the absolute path
        return DirectoryNode(id=node_id, label=label, abs_path=path, children=children or None)

    return [build_tree(root_path)]




# @motioncor_router.get("/directory-tree", response_model=List[DirectoryNode])
# def directory_tree(root_path: str):
#     root_path=r"C:\temp\test"
#     return get_directory_structure(root_path)



class ImageResponse(BaseModel):
    images: List[List[List[float]]]
    total_images: int
    height: int
    width: int

class MetadataResponse(BaseModel):
    metadata: Dict[str, List[int]]



def read_images_from_mrc(file_path: str, start_idx: int, count: int) -> ImageResponse:
    """Read a subset of images from an MRC file."""
    try:
        with mrcfile.mmap(file_path, mode='r', permissive=True) as mrc:
            data = mrc.data
            total_images = data.shape[0]

            # Validate indices
            if start_idx >= total_images:
                raise HTTPException(status_code=400, message="Start index out of range")

            end_idx = min(start_idx + count, total_images)
            subset = data[start_idx:end_idx]

            # Normalize the data
            data_min = subset.min()
            data_max = subset.max()
            normalized_data = ((subset - data_min) / (data_max - data_min) * 255).tolist()

            return ImageResponse(
                images=normalized_data,
                total_images=total_images,
                height=data.shape[1],
                width=data.shape[2]
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@motioncor_router.get("/mrc/")
async def get_images(
    file_path: str,
    start_idx: int = 0,
    count: int = 10,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
) -> ImageResponse:
    """
    Get a subset of images from an MRC file.

    **Requires:** Authentication
    **Security:** Authenticated users can read MRC files
    **Note:** This allows direct file system access
    """
    logger.debug(f"User {user_id} reading MRC file: {file_path} (start: {start_idx}, count: {count})")
    return read_images_from_mrc(file_path, start_idx, count)



class FileItem(BaseModel):
    id: int
    name: str = Field(..., description="The name of the file or folder")
    is_directory: bool = Field(..., description="True if the item is a folder, False if it's a file")
    path: str = Field(..., description="The full path of the item")
    parent_id: Optional[int] = Field(None, description="The ID of the parent folder")
    size: Optional[int] = Field(None, description="The size of the file in bytes (only for files)")
    mime_type: Optional[str] = Field(None, description="The MIME type of the file (only for files)")
    created_at: datetime
    updated_at: datetime

@motioncor_router.get("/files/browse", response_model=List[FileItem])
async def browse_directory(
    path: str = "/gpfs",
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Browse filesystem directories.

    **Requires:** Authentication
    **Security:** Authenticated users can browse the filesystem
    **WARNING:** This exposes filesystem structure and file metadata
    """
    logger.warning(f"SECURITY: User {user_id} browsing filesystem path: {path}")

    try:
        development = False
        if development and path.startswith("/gpfs"):
            path = path.replace("/gpfs", "C:/magellon/gpfs", 1)

        directory = Path(path)
        if not directory.exists():
            raise HTTPException(status_code=404, detail="Directory not found")

        items = []
        for item in directory.iterdir():
            stat = item.stat()
            file_item = FileItem(
                id=hash(str(item)),  # Generate a unique ID based on path hash
                name=item.name,
                is_directory=item.is_dir(),
                path=str(item),
                parent_id=hash(str(item.parent).replace("C:/magellon/gpfs", "/gpfs", 1) if development else str(item.parent)) if str(item.parent) != path else None,
                size=stat.st_size if not item.is_dir() else None,
                mime_type=mimetypes.guess_type(item.name)[0] if not item.is_dir() else None,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                updated_at=datetime.fromtimestamp(stat.st_mtime)
            )
            items.append(file_item)

        # Sort: directories first, then files
        items.sort(key=lambda x: (not x.is_directory, x.name))

        logger.debug(f"User {user_id} retrieved {len(items)} items from path: {path}")
        return items
    except Exception as e:
        logger.error(f"Error browsing directory for user {user_id}, path: {path}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


PREVIEW_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
PREVIEW_MRC_EXTS = {".mrc", ".mrcs", ".map"}


def _render_mrc_to_png_bytes(abs_path: str, height: int = 1024) -> bytes:
    """Open an MRC file and return normalized PNG bytes (in-memory, no disk writes)."""
    with mrcfile.open(abs_path, permissive=True) as mrc:
        data = mrc.data
        # Collapse stacks: take first frame if the file is a movie/tilt series.
        if data.ndim == 3:
            frame = data[0]
        elif data.ndim == 2:
            frame = data
        else:
            frame = np.asarray(data).reshape(data.shape[-2], data.shape[-1])

    img = MrcImageService().scale_image(frame, height)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


@motioncor_router.get("/files/preview")
async def preview_file(
    path: str,
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Serve an image file by absolute path for preview purposes.

    **Requires:** Authentication
    **Security:** Only allows a whitelisted set of image extensions.
    MRC/MRCS/MAP files are rendered to PNG on the fly using
    MrcImageService (percentile-clipped, downsampled).
    Used by the standalone plugin runner to preview test images that
    live outside any session directory.
    """
    logger.warning(f"SECURITY: User {user_id} previewing file: {path}")

    target = Path(path)
    ext = target.suffix.lower()

    if ext in PREVIEW_MRC_EXTS:
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        try:
            png_bytes = _render_mrc_to_png_bytes(str(target))
        except Exception as e:
            logger.error(f"MRC preview failed for {path}: {e}")
            raise HTTPException(status_code=500, detail=f"MRC render failed: {e}")
        return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")

    if ext in PREVIEW_IMAGE_EXTS:
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        mime, _ = mimetypes.guess_type(target.name)
        return FileResponse(str(target), media_type=mime or "application/octet-stream")

    raise HTTPException(status_code=415, detail="Unsupported file type for preview")


@motioncor_router.post("/test-motioncor")
async def test_motioncor(
        image_file: UploadFile = File(...),
        gain_file: UploadFile = File(...),
        defects_path: Optional[str] = Form(None),
        data: str = Form(...),  # JSON string
        session_name: str = Form("testing"),
        user_id: UUID = Depends(get_current_user_id)
):
    """
    Test motioncor task with uploaded image, gain, and config data.

    Sends task to motioncor test queue for processing.
    Returns immediately with task_id for WebSocket subscription.

    **Requires:** Authentication
    **Returns:** {status, task_id} - Client uses task_id to connect to WebSocket for updates
    """
    from services.motioncor_test_service import MotioncorTestTaskManager

    logger.warning(f"SECURITY: User {user_id} triggering test motioncor for session: {session_name}")

    task_id = uuid.uuid4()

    try:
        # Parse JSON parameters
        params: dict = json.loads(data)
        base_tmp_dir = Path("/gpfs/tmp")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded files
        image_path = base_tmp_dir / image_file.filename
        gain_path = base_tmp_dir / gain_file.filename

        with open(image_path, "wb") as f:
            f.write(await image_file.read())

        with open(gain_path, "wb") as f:
            f.write(await gain_file.read())

        # Extract params from form data (params contains the actual form parameters directly)
        params.setdefault("magellon_project_name", "test_project")
        params.setdefault("magellon_session_name", session_name)

        # Log the incoming params for debugging
        logger.info(f"Received params: {params}")

        # Prepare motioncor settings with frontend parameters
        # Map frontend parameter names to backend parameter names
        motioncor_settings = {}

        param_mappings = {
            'FmDose': (float, 'FmDose'),
            'PixSize': (float, 'PixSize'),
            'kV': (float, 'kV'),
            'Patchrows': (int, 'PatchesX'),  # Frontend sends Patchrows -> backend uses PatchesX
            'Patchcols': (int, 'PatchesY'),  # Frontend sends Patchcols -> backend uses PatchesY
            'PatchesX': (int, 'PatchesX'),   # Also support direct PatchesX
            'PatchesY': (int, 'PatchesY'),   # Also support direct PatchesY
            'Group': (int, 'Group'),
            'FtBin': (float, 'FtBin'),
            'Iter': (int, 'Iter'),
            'Tol': (float, 'Tol'),
            'FlipGain': (int, 'FlipGain'),
            'RotGain': (int, 'RotGain'),
            'Bft_global': (int, 'Bft_global'),
            'Bft_local': (int, 'Bft_local')
        }

        for frontend_param, (param_type, backend_param) in param_mappings.items():
            if frontend_param in params and params[frontend_param] is not None:
                try:
                    motioncor_settings[backend_param] = param_type(params[frontend_param])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid value for {frontend_param}: {params[frontend_param]}, skipping")

        logger.info(f"Built motioncor_settings: {motioncor_settings}")

        # Create the test task
        motioncor_task = MotioncorTestTaskManager.create_test_task(
            task_id=task_id,
            image_path=str(image_path),
            gain_path=str(gain_path),
            defects_path=defects_path,
            session_name=session_name,
            task_params=params,
            motioncor_settings=motioncor_settings
        )

        # Publish task to the test input queue
        if MotioncorTestTaskManager.publish_task_to_queue(motioncor_task):
            logger.info(f"Motioncor test task {task_id} queued successfully for user {user_id}")

            return {
                "status": "queued",
                "task_id": str(task_id),
                "message": "Task has been queued for processing. Connect to WebSocket with this task_id to receive updates.",
                "websocket_url": f"/ws/motioncor-test/{task_id}"
            }
        else:
            logger.error(f"Failed to queue motioncor test task {task_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to queue task. Please try again."
            )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in test_motioncor data: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON in request data")
    except Exception as e:
        logger.error(f"Error in test_motioncor endpoint for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@motioncor_router.get("/download-motioncor-output/{task_id}/{filename}")
async def download_motioncor_output(
    task_id: str,
    filename: str,
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Download motioncor output files (_DW.mrc or _DWS.mrc file only)

    **Requires:** Authentication
    **Returns:** File download
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    logger.warning(f"SECURITY: User {user_id} downloading motioncor output: {filename}")

    try:
        # Construct the file path - files are stored in /jobs/{task_id}/
        file_path = os.path.join(app_settings.jobs_dir, task_id, filename)

        # Security: Ensure the file path is within the jobs directory
        file_path = os.path.abspath(file_path)
        jobs_dir = os.path.abspath(app_settings.jobs_dir)

        if not file_path.startswith(jobs_dir):
            logger.error(f"Security: Attempted to access file outside jobs directory: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")

        # Security: Only allow downloading _DW.mrc or _DWS.mrc files
        if not (filename.endswith("_DW.mrc") or filename.endswith("_DWS.mrc")):
            logger.error(f"Security: Attempted to download non-DW file: {filename}")
            raise HTTPException(status_code=403, detail="Only DW/DWS files can be downloaded")

        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"Serving file for download: {file_path}")
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading motioncor output for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

def create_task(session_name="24mar28a", file_name="20241203_54449_integrated_movie",gain_path = "/gpfs/20241202_53597_gain_multi_ref.tif"):
    """
    Creates a motioncor task with specified session name and file name

    Args:
        session_name (str): Name of the session, defaults to "24mar28a"
        file_name (str): Base name of the file, defaults to "20241203_54449_integrated_movie"

    Returns:
        MotioncorTask: Created task object or False if error occurs
    """

    try:
        # Construct the full image path
        image_path = f"/gpfs/{file_name}.mrc.tif"

        # Use the consolidated create_motioncor_task function
        motioncor_task = create_motioncor_task(
            image_path=image_path,
            gain_path=gain_path,
            session_name=session_name,
            task_id=str(uuid.uuid4()),  # Generate new UUID for task
            job_id=uuid.uuid4()  # Generate new UUID for job
        )

        return motioncor_task

    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False


@motioncor_router.websocket("/ws/motioncor-test/{task_id}")
async def websocket_motioncor_test(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time motioncor test task updates.

    Clients connect to this endpoint using the task_id returned from /test-motioncor.
    Receives status updates and final results as they become available.

    **Requires:** Authentication token via query parameter
    **Usage:**
        - Connect to: ws://host/ws/motioncor-test/{task_id}?token=<your_jwt_token>
        - Receive messages with: type (status_update/result/error), status, and data
    """
    from services.motioncor_test_service import (
        register_websocket_connection,
        unregister_websocket_connection
    )
    from jose import JWTError, jwt
    from uuid import UUID

    logger.info(f"WebSocket connection attempt for task {task_id}")

    # CRITICAL: Accept the WebSocket connection IMMEDIATELY
    # This must happen before any other WebSocket operations
    try:
        await websocket.accept()
        logger.debug(f"WebSocket accepted for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to accept WebSocket for task {task_id}: {e}")
        return

    # NOW authenticate after accepting
    user_id = None

    # Get token from query parameters
    token = websocket.query_params.get("token")

    logger.debug(f"Token present: {bool(token)}")

    # If we have a token, validate it
    if token:
        try:
            # Manually decode JWT token to avoid HTTPException
            SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-CHANGE-THIS-IN-PRODUCTION-min-32-chars")
            ALGORITHM = "HS256"

            logger.debug(f"Decoding JWT token for task {task_id}")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id_str = payload.get("sub")

            if not user_id_str:
                logger.warning(f"WebSocket auth failed for task {task_id}: No user ID in token")
                await websocket.send_json({
                    "type": "error",
                    "error": "Unauthorized - no user ID in token"
                })
                await websocket.close(code=1008, reason="Unauthorized - no user ID")
                return

            # Convert to UUID
            try:
                user_id = UUID(user_id_str)
                logger.info(f"User {user_id} authenticated for WebSocket task {task_id}")
            except (ValueError, TypeError):
                logger.warning(f"WebSocket auth failed for task {task_id}: Invalid user ID format")
                await websocket.send_json({
                    "type": "error",
                    "error": "Unauthorized - invalid user format"
                })
                await websocket.close(code=1008, reason="Unauthorized - invalid user format")
                return

        except jwt.ExpiredSignatureError:
            logger.warning(f"WebSocket auth failed for task {task_id}: Token expired")
            await websocket.send_json({
                "type": "error",
                "error": "Unauthorized - token expired"
            })
            await websocket.close(code=1008, reason="Unauthorized - token expired")
            return
        except JWTError as e:
            logger.warning(f"WebSocket auth failed for task {task_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Unauthorized - invalid token: {str(e)}"
            })
            await websocket.close(code=1008, reason="Unauthorized - invalid token")
            return
        except Exception as e:
            logger.warning(f"WebSocket auth error for task {task_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Unauthorized - auth error: {str(e)}"
            })
            await websocket.close(code=1008, reason="Unauthorized")
            return
    else:
        # No token provided, reject connection
        logger.warning(f"WebSocket connection attempted without token for task {task_id}")
        await websocket.send_json({
            "type": "error",
            "error": "Unauthorized - token required"
        })
        await websocket.close(code=1008, reason="Unauthorized - token required")
        return

    # Register the WebSocket connection after authentication
    try:
        connection = await register_websocket_connection(task_id, websocket)
        # Mark the connection as accepted since we already called websocket.accept() above
        connection.is_connected = True
        logger.info(f"WebSocket registered for task {task_id}, user {user_id}")
    except Exception as e:
        logger.error(f"Failed to register WebSocket for task {task_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "error": f"Failed to register connection: {str(e)}"
            })
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
        return

    # Send initial connection message
    try:
        await connection.send_json({
            "type": "connected",
            "task_id": task_id,
            "user_id": str(user_id),
            "message": "Connected to task updates. Waiting for task results..."
        })
        logger.debug(f"Sent connected message for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to send initial message for task {task_id}: {e}")

    try:
        # Keep connection alive and listen for client messages
        while True:
            # Wait for any message from client (mainly for keep-alive)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                logger.debug(f"Received message from client for task {task_id}: {data}")
            except asyncio.TimeoutError:
                # Send keep-alive ping
                try:
                    await connection.send_json({
                        "type": "ping",
                        "task_id": task_id,
                        "message": "Connection alive"
                    })
                except Exception as e:
                    logger.debug(f"Error sending ping for task {task_id}: {e}")
            except json.JSONDecodeError:
                # Client sent invalid JSON, but keep connection open
                logger.warning(f"Invalid JSON received from client for task {task_id}")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket for task {task_id}")
        try:
            await unregister_websocket_connection(task_id, connection)
        except Exception as e:
            logger.error(f"Error unregistering connection for task {task_id}: {e}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection for task {task_id}: {e}")
        try:
            await unregister_websocket_connection(task_id, connection)
        except:
            pass
