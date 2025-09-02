import uvicorn

from app.api import app
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
