from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.exception_handlers import register_exception_handlers


def test_http_errors_keep_detail_and_add_stable_metadata():
    app = FastAPI()
    register_exception_handlers(app, is_production=lambda: True)

    @app.get("/failure")
    def failure():
        raise HTTPException(status_code=409, detail="already exists")

    response = TestClient(app).get("/failure")

    assert response.status_code == 409
    assert response.json()["detail"] == "already exists"
    assert response.json()["code"] == "HTTP_409"
    assert response.json()["message"] == "already exists"
