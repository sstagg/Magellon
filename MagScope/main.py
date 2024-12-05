from fastapi import FastAPI
from pyscope import de
from pyscope import fei
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/camera/image")
async def test_camera(name: str):
    c = de.DeApollo()
    image = c.getImage()
    return {"message": f"Hello {name}"}


@app.get("/scope/image")
async def test_camera():
    t = fei.Krios()
    mag = t.getMagnification()
    return {"mag": f"{mag}"}
