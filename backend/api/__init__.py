import api.api as archiver_api
from archiver.config import settings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(root_path=settings.API_ROOT_PATH)

app.include_router(archiver_api.router)

origins = [
    "http://127.0.0.1*",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
