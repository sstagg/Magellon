from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse
from uuid import UUID
import logging

from services.docker_deployment_service import DockerContainerInput, DockerDeployment
from dependencies.permissions import require_role
from dependencies.auth import get_current_user_id

deployment_docker_router = APIRouter()
logger = logging.getLogger(__name__)

# ✅ Whitelist of allowed Docker images (SECURITY CRITICAL)
# Only images in this list can be deployed through the API
# Add your trusted images here
ALLOWED_DOCKER_IMAGES = [
    "khoshbin/magellon-main-service",
    "khoshbin/magellon-worker",
    "khoshbin/magellon-core-service",
    # Add other trusted Magellon images here
]

@deployment_docker_router.post("/deploy-container-by-image-name")
async def deploy_docker_container_by_image_name(
    request: DockerContainerInput,
    _: None = Depends(require_role('Administrator')),  # ✅ Admin-only
    user_id: UUID = Depends(get_current_user_id)       # ✅ Audit trail
):
    """
    Deploy a Docker container from a whitelisted image.

    **Requires:** Administrator role
    **Security:** Only pre-approved images in the whitelist can be deployed

    **Example Request:**
    ```json
    {
        "image_name": "khoshbin/magellon-main-service",
        "target_host": "localhost",
        "restart": "always",
        "network": "magellon",
        "port_bindings": {"8000": 80},
        "volumes": {
            "/magellon/data": {"bind": "/app/data", "mode": "rw"}
        },
        "container_name": "magellon-core-service01"
    }
    ```
    """

    # ✅ SECURITY: Validate image is in whitelist (prevents malicious image deployment)
    if request.image_name not in ALLOWED_DOCKER_IMAGES:
        logger.warning(
            f"SECURITY: User {user_id} attempted to deploy non-whitelisted image: "
            f"{request.image_name}"
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Image not in whitelist",
                "message": f"Image '{request.image_name}' is not approved for deployment.",
                "allowed_images": ALLOWED_DOCKER_IMAGES,
                "note": "Contact administrator to add trusted images to the whitelist."
            }
        )

    # ✅ Comprehensive audit logging
    logger.warning(
        f"DOCKER DEPLOYMENT initiated by user {user_id}: "
        f"image={request.image_name}, "
        f"container={request.container_name}, "
        f"host={request.target_host}"
    )

    try:
        deployer = DockerDeployment()
        result = deployer.create_and_run_container(request)

        logger.info(
            f"DOCKER DEPLOYMENT successful: "
            f"container '{request.container_name}' deployed by user {user_id}"
        )

        # ✅ Return result with audit information
        return {
            **result,
            "deployed_by": str(user_id),
            "image": request.image_name,
            "container_name": request.container_name,
            "security_status": "Image verified against whitelist"
        }

    except Exception as e:
        logger.error(
            f"DOCKER DEPLOYMENT failed for user {user_id}: "
            f"image={request.image_name}, error={str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Deployment failed",
                "message": str(e),
                "image": request.image_name,
                "requested_by": str(user_id)
            }
        )
