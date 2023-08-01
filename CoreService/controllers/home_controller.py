from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from pathlib import Path
import logging
from config import fetch_image_root_dir, app_settings
from lib.image_not_found import get_image_not_found

home_router = APIRouter()

BASE_PATH = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_PATH / "../templates"))

logger = logging.getLogger(__name__)


@home_router.get("/")
async def home():
    return RedirectResponse(url="/docs/")


# Define a health check route
@home_router.get('/health')
def health_check():
    logger.info("Logger is working")
    print("Health check")
    # raise Exception("just to test this")
    # try:
    #
    # except Exception:
    #     console = Console()
    #     console.print_exception(show_locals=True)
    return {'status': 'ok'}


# @home_router.get("/notfound")
# async def get_not_found():
#     # image_path = r"c:/temp/icon-image-not-found.png"
#     # base64_string = image_to_base64(image_path)
#     # print(base64_string)
#     # return get_image_base64(base64_string)
#     return get_image_not_found()


@home_router.get("/configs")
async def get_configs():
    return app_settings.dict()


# @home_router.get("/env_type")
# async def get_env_type():
#     return {"Environment Type": ENV_TYPE, "DATA_DIR": IMAGE_ROOT_DIR}
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


@home_router.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
