from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, filters, search
from app.config import settings
from app.deps import build_services
from app.ratelimit import AskLimits


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
    app.state.ask_limits = AskLimits(settings)
    for module in (search, ask, filters):
        app.include_router(module.router)

    @app.get("/health")
    def health():
        services = app.state.services
        info = {"status": "ok", "index_loaded": services is not None}
        if services is not None:  # which retrieval setup is live (useful to confirm a deployment)
            info["search_mode"] = services.retriever.mode
            info["rerank"] = services.retriever.reranker is not None
        return info

    return app


app = create_app()
