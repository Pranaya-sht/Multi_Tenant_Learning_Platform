from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    services: dict[str, Literal["ok", "unavailable"]]


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/ready", response_model=ReadinessResponse)
def readiness(request: Request, response: Response) -> ReadinessResponse:
    services = {}
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except SQLAlchemyError:
        services["postgres"] = "unavailable"

    for name, client in (
        ("redis_cache", request.app.state.cache),
        ("redis_queue", request.app.state.queue_connection),
    ):
        try:
            services[name] = "ok" if client.ping() else "unavailable"
        except RedisError:
            services[name] = "unavailable"

    ready = all(status == "ok" for status in services.values())
    if not ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if ready else "unavailable", services=services)
