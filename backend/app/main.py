from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, filters, search
from app.config import settings
from app.deps import build_services


@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(app.state, "services", None) is None:  # tests inject their own
        app.state.services = build_services()
    yield
    services = getattr(app.state, "services", None)
    if services is not None:
        services.close()


def create_app() -> FastAPI:
    app = FastAPI(title="MapleMinutes", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.services = None
    for module in (search, ask, filters):
        app.include_router(module.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "index_loaded": app.state.services is not None}

    return app


app = create_app()
