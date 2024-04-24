import uvicorn
from archiver.config import settings
import pathlib

if __name__ == "__main__":
    config = uvicorn.Config("api:app", port=settings.API_PORT, host="0.0.0.0", log_level=settings.API_LOG_LEVEL, reload_dirs=[
                            str(pathlib.Path(__file__).parent)], reload=(settings.API_RELOAD or settings.API_RELOAD == 'true'))
    server = uvicorn.Server(config)
    server.run()
