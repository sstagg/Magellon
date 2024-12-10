from fastapi import FastAPI
from pyscope import de
from pyscope import fei
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/camera/image")
async def test_camera():
    c = de.Apollo()
    image = c.getImage()
    return {"message": f"Hello"}


@app.get("/scope/image")
async def test_scope():
    t = fei.Krios()
    mag = t.getMagnification()
    return {"mag": f"{mag}"}
