import os

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.routes.bot_call_router import call_router
from backend.routes.conference_router import conference_router
from backend.routes.media_router import media_router
from backend.routes.user_call_router import user_call_router

load_dotenv('../env/.env')

PORT = int(os.getenv('PORT', 5050))


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(call_router, prefix="/calls", tags=["calls"])
    app.include_router(conference_router, prefix="/conference", tags=["conference"])
    app.include_router(media_router, prefix="/media", tags=["media"])
    app.include_router(user_call_router, prefix="/user_calls", tags=["user_calls"])
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
