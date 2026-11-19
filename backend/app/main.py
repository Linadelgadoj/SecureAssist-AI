import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.users import router as users_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db.database import Database
from app.repositories.conversations import SupabaseConversationRepository
from app.repositories.memory_conversations import InMemoryConversationRepository
from app.repositories.memory_users import InMemoryUserRepository
from app.repositories.postgres_conversations import PostgresConversationRepository
from app.repositories.postgres_inventory import (
    PostgresCatalogRepository,
    PostgresClientRepository,
    PostgresRepairRepository,
)
from app.repositories.postgres_users import PostgresUserRepository
from app.services.dev_auth import DevAuthService

logger = logging.getLogger("uvicorn.error")


def _compose_storage(application: FastAPI, settings: Settings) -> Database | None:
    """Raíz de composición del almacenamiento: elige el adaptador de cada puerto.

    1. DATABASE_URL definido  -> PostgreSQL local (docker-compose).
    2. DEV_LOGIN sin base      -> memoria (se pierde al reiniciar).
    3. En otro caso            -> Supabase (PostgREST + RLS) para conversaciones.

    El inventario solo existe con PostgreSQL; sin él sus rutas responden 503.
    """
    application.state.catalog_repository = None
    application.state.client_repository = None
    application.state.repair_repository = None
    if settings.database_url:
        database = Database(settings.database_url)
        conversations = PostgresConversationRepository(database)
        application.state.conversation_repository_factory = lambda _token: conversations
        application.state.user_repository = PostgresUserRepository(database)
        application.state.catalog_repository = PostgresCatalogRepository(database)
        application.state.client_repository = PostgresClientRepository(database)
        application.state.repair_repository = PostgresRepairRepository(database)
        return database
    application.state.user_repository = InMemoryUserRepository()
    if settings.dev_login:
        memory = InMemoryConversationRepository()
        application.state.conversation_repository_factory = lambda _token: memory
    else:
        application.state.conversation_repository_factory = (
            lambda token: SupabaseConversationRepository(settings, token)
        )
    return None


def create_app(settings: Settings | None = None, auth_service=None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database: Database | None = application.state.database
        if database is not None:
            await database.connect()
            applied = await database.migrate()
            if applied:
                logger.info("Migraciones aplicadas: %s", ", ".join(applied))
        try:
            yield
        finally:
            close = getattr(application.state.auth_service, "aclose", None)
            if close is not None:
                await close()
            if database is not None:
                await database.close()

    application = FastAPI(
        title="SecureAssist AI API",
        version="0.2.0",
        description="API de SecureAssist AI.",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.auth_service = auth_service
    application.state.database = _compose_storage(application, settings)
    if settings.dev_login and auth_service is None:
        if settings.app_env != "development":
            raise ValueError("DEV_LOGIN solo se permite con APP_ENV=development.")
        application.state.auth_service = DevAuthService(settings)
        logger.warning("DEV_LOGIN activo: login de prueba sin Supabase. No usar fuera de desarrollo local.")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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
    application.include_router(users_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    application.include_router(inventory_router, prefix="/api/v1")
    return application


app = create_app()
