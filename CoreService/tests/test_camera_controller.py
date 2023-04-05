import os
import sys

from fastapi.testclient import TestClient

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from main import app

client = TestClient(app)


def test_say_hello():
    response = client.get("/hello/world")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello world"}
