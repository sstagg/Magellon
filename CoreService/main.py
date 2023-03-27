from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse, JSONResponse

from config import get_db_connection
from models.pydantic_models import PyCamera
from models.sqlalchemy_models import Camera
from repositories.camera_repository import CameraRepository

app = FastAPI(title="Magellon Core Service",
              description="Magellon Core Application with Swagger and Sqlalchemy",
              version="1.0.0", )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

engine = create_engine(get_db_connection())
session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency
def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()


@app.get("/")
async def home():
    return RedirectResponse(url="/docs/")


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


# @app.get("/cameras/", response_model=List[PyCamera])
# def show_cameras(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records


@app.exception_handler(Exception)
def validation_exception_handler(request, err):
    base_error_message = f"Failed to execute: {request.method}: {request.url}"
    return JSONResponse(status_code=400, content={"message": f"{base_error_message}. Detail: {err}"})


@app.post('/cameras', tags=["Camera"], response_model=PyCamera, status_code=201)
async def create_camera(camera_request: PyCamera, db: Session = Depends(get_db)):
    """
    Create a Camera and save it in the database
    """
    db_camera = CameraRepository.fetch_by_name(db, name=camera_request.name)
    print(db_camera)
    if db_camera:
        raise HTTPException(status_code=400, detail="Camera already exists!")

    return await CameraRepository.create(db=db, camera_dto=camera_request)


@app.get('/cameras', tags=["Camera"], response_model=List[PyCamera])
def get_all_cameras(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the cameras camerad in database
    """
    if name:
        cameras = []
        db_camera = CameraRepository.fetch_by_name(db, name)
        print(db_camera)
        cameras.append(db_camera)
        return cameras
    else:
        return CameraRepository.fetch_all(db)


@app.get('/cameras/{oid}', tags=["Camera"], response_model=PyCamera)
def get_camera(oid: UUID, db: Session = Depends(get_db)):
    """
    Get the camera with the given ID provided by User camerad in database
    """
    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="camera not found with the given ID")
    return db_camera


@app.delete('/cameras/{oid}', tags=["Camera"])
async def delete_camera(oid: UUID, db: Session = Depends(get_db)):
    """
    Delete the Item with the given ID provided by User camerad in database
    """
    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="camera not found with the given ID")
    await CameraRepository.delete(db, oid)
    return "camera deleted successfully!"
