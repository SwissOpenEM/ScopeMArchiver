import uvicorn
from archiver.config.variables import AppConfig
import api.router as archiver_api
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import argparse


def init_app(config: AppConfig):
    app = FastAPI(root_path=config.API_ROOT_PATH)

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

    return app


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog='ScopeM Archiver Backend')

    parser.add_argument('-c', '--config', default=None, type=pathlib.Path)

    args, _ = parser.parse_known_args()
    config = AppConfig(_env_file=args.config)
    print(config)
    app = init_app(config)

    uvi_config = uvicorn.Config(app, port=config.API_PORT, host="0.0.0.0", log_level=config.API_LOG_LEVEL, reload_dirs=[
        str(pathlib.Path(__file__).parent)], reload=config.API_RELOAD)
    server = uvicorn.Server(uvi_config)
    server.run()
