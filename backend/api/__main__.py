import uvicorn
from archiver.config import settings

if __name__ == "__main__":
    config = uvicorn.Config("api:app", port=settings.API_PORT, host="0.0.0.0", log_level=settings.API_LOG_LEVEL, reload=settings.API_RELOAD)
    server = uvicorn.Server(config)
    server.run()
