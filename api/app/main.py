from fastapi import FastAPI

from app.clock import Clock, SystemClock
from app.config import Settings


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings or Settings()
    app.state.clock = clock or SystemClock()

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app
