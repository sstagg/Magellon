from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from pathlib import Path
import logging
from config import fetch_image_root_dir, app_settings
from lib.image_not_found import get_image_not_found

home_router = APIRouter()

BASE_PATH = Path(__file__).resolve().parent
static_directory=str(BASE_PATH / "../static")
TEMPLATES = Jinja2Templates(directory=static_directory)

logger = logging.getLogger(__name__)

# home_router.mount("/static", StaticFiles(directory=static_directory), name="static")


@home_router.get("/")
async def home(request: Request):
    return RedirectResponse(url="/docs/")

@home_router.get("/en/{rest_of_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, rest_of_path: str):
    logger.info("rest of path :" + rest_of_path)
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


# Define a health check route
@home_router.get('/health')
def health_check():
    return {'status': 'ok'}


@home_router.get("/configs")
async def get_configs():
    return app_settings.dict()


@home_router.get("/image_root_dir")
async def get_image_root_dir():
    root_dir = fetch_image_root_dir()
    return {"image_root_dir": root_dir}


@home_router.get("/html")
async def html(request: Request):
    html_content = """
    <h1>Hello, world!</h1>
    <p>This is an example of returning an HTML page using FastAPI and Jinja templates.</p>
    """
    return TEMPLATES.TemplateResponse("index.html", {"request": request, "html_content": html_content})


