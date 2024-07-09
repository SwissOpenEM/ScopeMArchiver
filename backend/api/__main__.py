import uvicorn
import api.router as archiver_api
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    UVICORN_PORT: int = 8000
    UVICORN_ROOT_PATH: str = "/"
    UVICORN_RELOAD: bool = False
    UVICORN_LOG_LEVEL: str = "info"


if __name__ == "__main__":

    settings = Settings()
    print(settings)
    app = FastAPI()

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
    uvi_config = uvicorn.Config(app,
                                host="0.0.0.0",
                                port=settings.UVICORN_PORT,
                                root_path=settings.UVICORN_ROOT_PATH,
                                reload=settings.UVICORN_RELOAD,
                                log_level=settings.UVICORN_LOG_LEVEL,
                                reload_dirs=[
                                    str(pathlib.Path(__file__).parent)])
    server = uvicorn.Server(uvi_config)
    server.run()
