from fastapi.testclient import TestClient
from loguru import logger
from pydantic import BaseModel, Field, SecretStr

from tashtiot_apis_library.fastapi_template import general_create_app
from tashtiot_apis_library.fastapi_template.config_api import (
    install_coordinate_validation_error_handler,
)

SECRET = "hunter2-do-not-log"


class Body(BaseModel):
    password: SecretStr = Field(..., min_length=32)


def test_validation_error_never_exposes_submitted_values():
    app = general_create_app()

    @app.post("/things")
    def create(body: Body):
        return {}

    records = []
    sink = logger.add(records.append, level="DEBUG", format="{message} {exception}")
    try:
        response = TestClient(app).post("/things", json={"password": SECRET})
    finally:
        logger.remove(sink)

    logged = "".join(str(r) for r in records)
    assert SECRET not in logged
    assert SECRET not in response.text
    assert response.status_code == 422
    # Still says where and why it failed, in FastAPI's usual {"detail": [...]} shape.
    assert response.json() == {
        "detail": [
            {
                "loc": ["body", "password"],
                "msg": "Value should have at least 32 items after validation, not 18",
                "type": "too_short",
            }
        ]
    }
    assert "Validation error on POST /things" in logged


def test_coordinate_validation_handler_never_exposes_submitted_values():
    app = general_create_app()
    install_coordinate_validation_error_handler(app)

    @app.get("/things")
    def read():
        Body(password=SECRET)  # a model built in app code raises pydantic.ValidationError

    response = TestClient(app).get("/things")

    assert response.status_code == 422
    assert SECRET not in response.text
    assert response.json()["detail"][0]["loc"] == ["query", "password"]
