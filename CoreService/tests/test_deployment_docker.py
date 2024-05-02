import unittest
import pytest
import requests

# Define the base URL for your API
BASE_URL = "http://your_server_address_here/deploy-container-by-image-name"

@pytest.fixture
def valid_input_data():
    return {
        "image_name": "khoshbin/magellon-main-service",
        "target_host": "localhost",
        "target_username": "your_username",
        "target_password": "your_password",
        "restart": "always",
        "network": "magellon",
        "port_bindings": {"8000": 80},
        "volumes": {
            "/magellon/data": {"bind": "/app/data", "mode": "rw"},
            "/magellon/configs": {"bind": "/app/config", "mode": "ro"},
            "/gpfs": {"bind": "/app/nfs", "mode": "rw"}
        },
        "container_name": "magellon-core-service01"
    }


def test_deploy_container_by_image_name(valid_input_data):
    response = requests.post(BASE_URL, json=valid_input_data)
    assert response.status_code == 200
    assert "container_id" in response.json()  # Assuming the API returns the container ID in the response

    # You can add more assertions based on the expected behavior of your API

# Run the tests
if __name__ == "__main__":
    pytest.main()