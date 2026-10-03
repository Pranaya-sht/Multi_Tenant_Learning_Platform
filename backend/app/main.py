from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.api.router import api_router
from app.core.config import Settings
from app.infrastructure.redis import create_cache, create_queue, create_queue_connection


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Connections are lazy: the API can serve liveness without external services.
        application_engine = engine or create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        cache = create_cache(settings)
        queue_connection = create_queue_connection(settings)
        app.state.engine = application_engine
        app.state.session_factory = sessionmaker(bind=application_engine, expire_on_commit=False)
        app.state.cache = cache
        app.state.queue_connection = queue_connection
        app.state.queue = create_queue(settings, queue_connection)
        try:
            yield
        finally:
            cache.close()
            queue_connection.close()
            if engine is None:
                application_engine.dispose()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    @app.exception_handler(OperationalError)
    async def database_unavailable(request, error):
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(api_router)
    return app
