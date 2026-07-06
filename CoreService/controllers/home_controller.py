import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from config import app_settings, fetch_image_root_dir
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_role

home_router = APIRouter()

BASE_PATH = Path(__file__).resolve().parent
static_directory = str(BASE_PATH / "../static")
TEMPLATES = Jinja2Templates(directory=static_directory)

logger = logging.getLogger(__name__)

_SENSITIVE_KEY_PARTS = (
    "password",
    "pass",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "private_key",
)
_REDACTED = "<redacted>"


@home_router.get("/")
async def home(request: Request):
    return RedirectResponse(url="/docs/")


@home_router.get("/en/{rest_of_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, rest_of_path: str):
    logger.info("rest of path :" + rest_of_path)
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@home_router.get("/health")
def health_check():
    return {"status": "ok"}


def _redact_config(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
                redacted[key] = _REDACTED if item not in (None, "") else item
            else:
                redacted[key] = _redact_config(item)
        return redacted
    if isinstance(value, list):
        return [_redact_config(item) for item in value]
    return value


@home_router.get("/configs")
async def get_configs(
    current_user: dict = Depends(require_role("Administrator")),
):
    """
    Get application configuration settings.

    Requires the Administrator role. Sensitive configuration values are
    redacted recursively before returning the payload.
    """
    user_id = current_user["user_id"]
    logger.warning(f"SECURITY: User {user_id} accessing application configs")
    return _redact_config(app_settings.model_dump())


@home_router.get("/image_root_dir")
async def get_image_root_dir(
    user_id=Depends(get_current_user_id),
):
    """
    Get the image root directory path.

    **Requires:** Authentication
    **Security:** Authenticated users can view the image root directory path
    """
    logger.debug(f"User {user_id} requesting image root directory")
    root_dir = fetch_image_root_dir()
    return {"image_root_dir": root_dir}


@home_router.get("/html")
async def html(request: Request):
    html_content = """
    <h1>Hello, world!</h1>
    <p>This is an example of returning an HTML page using FastAPI and Jinja templates.</p>
    """
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request, "html_content": html_content},
    )
