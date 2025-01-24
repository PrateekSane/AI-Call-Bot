import os

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.routes.call_routes import call_router
from backend.routes.conference_routes import conference_router
from backend.routes.media_router import media_router

load_dotenv('../env/.env')

PORT = int(os.getenv('PORT', 5050))


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(call_router, prefix="/calls", tags=["calls"])
    app.include_router(conference_router, prefix="/conference", tags=["conference"])
    app.include_router(media_router, prefix="/media", tags=["media"])
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
