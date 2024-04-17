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
    # return TEMPLATES.TemplateResponse("index.html", {"request": request})
    return RedirectResponse(url="/docs/")

@home_router.get("/en/{rest_of_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, rest_of_path: str):
    logger.info("rest of path :" + rest_of_path)
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


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

@home_router.get("/hello/{name}")
async def get_xml_info(name: str):
    return {"message": f"Hello {name}"}