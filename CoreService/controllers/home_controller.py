from fastapi import APIRouter
from starlette.responses import RedirectResponse

home_router = APIRouter()


@home_router.get("/", tags=['Home'])
async def home():
    return RedirectResponse(url="/docs/")


@home_router.get("/hello/{name}", tags=['Home'])
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
