from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers


def create_app(settings: Settings | None = None, auth_service=None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        service = application.state.auth_service
        provider_client = getattr(getattr(service, "client", None), "client", None)
        if provider_client is not None:
            await provider_client.aclose()

    application = FastAPI(
        title="SecureAssist AI API",
        version="0.1.0",
        description="API de SecureAssist AI.",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.auth_service = auth_service
    application.state.conversation_repository_factory = None
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Authorization", "Origin"],
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    install_error_handlers(application)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    return application


app = create_app()
