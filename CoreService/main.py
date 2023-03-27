from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from controllers.camera_controller import camera_router
from controllers.home_controller import home_router
from database import engine, session_local

app = FastAPI(title="Magellon Core Service",
              description="Magellon Core Service that provides main services",
              version="1.0.0", )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.dbengine = engine
app.dbsession = session_local

app.include_router(home_router)
app.include_router(camera_router)


@app.exception_handler(Exception)
def validation_exception_handler(request, err):
    base_error_message = f"Failed to execute: {request.method}: {request.url}"
    return JSONResponse(status_code=400, content={"message": f"{base_error_message}. Detail: {err}"})


# @app.get("/cameras2/", response_model=List[CameraDto])
# def show_cameras(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records
