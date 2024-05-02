from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse
import logging

from services.docker_deployment_service import DockerContainerInput, DockerDeployment

deployment_docker_router = APIRouter()
logger = logging.getLogger(__name__)

@deployment_docker_router.post("/deploy-container-by-image-name")
async def deploy_docker_container_by_image_name(request: DockerContainerInput):
    deployer = DockerDeployment()
    # input_data = DockerContainerInput(
    #     image_name="khoshbin/magellon-main-service",
    #     target_host="localhost",
    #     target_username="your_username",
    #     target_password="your_password",
    #     restart="always",
    #     network="magellon",
    #     port_bindings={"8000": 80},
    #     volumes={
    #         "/magellon/data": {"bind": "/app/data", "mode": "rw"},
    #         "/magellon/configs": {"bind": "/app/config", "mode": "ro"},
    #         "/gpfs": {"bind": "/app/nfs", "mode": "rw"}
    #     },
    #     container_name="magellon-core-service01"
    # )

    deployer.create_and_run_container(request)
