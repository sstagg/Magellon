from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from pathlib import Path

home_router = APIRouter()

BASE_PATH = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_PATH / "../templates"))


@home_router.get("/", tags=['Home'])
async def home():
    return RedirectResponse(url="/docs/")


@home_router.get("/html", tags=['Home'])
async def html(request: Request):
    html_content = """
    <h1>Hello, world!</h1>
    <p>This is an example of returning an HTML page using FastAPI and Jinja templates.</p>
    """
    return TEMPLATES.TemplateResponse("index.html", {"request": request, "html_content": html_content})


@home_router.get("/hello/{name}", tags=['Home'])
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
