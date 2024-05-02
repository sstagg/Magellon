import logging
import os
from typing import Dict, Optional

import docker
from docker.errors import BuildError
from pydantic import BaseModel


logger = logging.getLogger(__name__)

class DockerContainerInput(BaseModel):
    image_name: str
    # target_host: str
    # target_username: str
    # target_password: str
    restart: Optional[str] = "always"
    network: Optional[str] = None
    port_bindings: Optional[Dict[str, int]] = None
    volumes: Optional[Dict[str, Dict[str, str]]] = None
    container_name: Optional[str] = None
    environment_variables: Optional[Dict[str, str]] = None


class DockerDeployment:
    def __init__(self):
        self.client = docker.from_env()
        # self.client = docker(base_url=f"tcp://{target_ip}:2375")

    def create_and_run_container(self, input_data: DockerContainerInput):
        # Generate container name if not provided
        input_data.container_name = input_data.container_name or f"{input_data.image_name}-container"

        # Define container options
        container_options = {
            "image": input_data.image_name,
            "name": input_data.container_name,
            "restart_policy": {"Name": input_data.restart},
            "detach": True,
            "environment": {
                # "TARGET_USERNAME": input_data.target_username,
                # "TARGET_PASSWORD": input_data.target_password,
                **(input_data.environment_variables or {})
            }
        }

        # Network settings
        if input_data.network:
            container_options["network"] = input_data.network

        # Port bindings
        if input_data.port_bindings:
            container_options["ports"] = input_data.port_bindings

        # Volume bindings
        if input_data.volumes:
            container_options["volumes"] = input_data.volumes

        # Pull the image (if not already available)
        try:
            self.client.images.pull(input_data.image_name)
        except docker.errors.ImageNotFound:
            print(f"Image {input_data.image_name} not found. Pulling from Docker Hub...")
            self.client.images.pull(input_data.image_name)

        # Create and run the container
        container = self.client.containers.run(**container_options)

        return container

    def build_image_from_dockerfile(self, dockerfile_path: str, input_data: DockerContainerInput, tag: Optional[str] = None):
        """
        Builds a Docker image from a Dockerfile at the specified path.

        Args:
            dockerfile_path (str): Path to the Dockerfile.
            tag (str, optional): Tag for the built image. Defaults to None.

        Raises:
            BuildError: If there's an error during the build process.
        """

        # Build context (directory containing Dockerfile)
        build_context = os.path.dirname(dockerfile_path)

        # Build arguments (optional)
        # You can add logic to accept and pass build arguments here

        try:
            # Build the image with optional tag
            self.client.images.build(path=build_context, tag=tag)
            logger.info(f"Image built successfully: {tag or input_data.image_name}")
        except BuildError as e:
            logger.error(f"Error building image: {e}")
            raise