from typing import List

from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from config import get_db_connection
from models.pydantic_models import PyCamera
from models.sqlalchemy_models import Camera

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
async def root():
    return RedirectResponse(url="/docs/")


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/cameras/", response_model=List[PyCamera])
def show_records(db: Session = Depends(get_db)):
    records = db.query(Camera).all()
    return records
