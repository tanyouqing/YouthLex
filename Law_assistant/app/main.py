from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.triage import router as triage_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_log_level)
    app = FastAPI(
        title="Qinglv Legal Triage Agent",
        version="0.1.0",
        description="高校学生维权智能体后端骨架服务",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok", "model": settings.minimax_model}

    app.include_router(triage_router)
    return app


app = create_app()
