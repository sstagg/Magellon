from fastapi.testclient import TestClient

from main import app
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

client = TestClient(app)


def test_say_hello():
    response = client.get("/hello/world")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello world"}
