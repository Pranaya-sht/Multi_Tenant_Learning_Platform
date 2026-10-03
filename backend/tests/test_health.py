from unittest.mock import MagicMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError


def test_liveness_does_not_require_external_services(client):
    client.app.state.engine = MagicMock()
    client.app.state.cache = MagicMock()
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    client.app.state.engine.connect.assert_not_called()
    client.app.state.cache.ping.assert_not_called()


def test_readiness_reports_connected_services(client):
    client.app.state.engine = MagicMock()
    client.app.state.cache = MagicMock()
    client.app.state.queue_connection = MagicMock()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "services": {"postgres": "ok", "redis_cache": "ok", "redis_queue": "ok"},
    }


@pytest.mark.parametrize("failed_service", ["postgres", "redis_cache", "redis_queue"])
def test_readiness_returns_503_without_leaking_connection_errors(client, failed_service):
    engine = MagicMock()
    cache = MagicMock()
    queue_connection = MagicMock()
    if failed_service == "postgres":
        engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("secret"))
    elif failed_service == "redis_cache":
        cache.ping.side_effect = RedisConnectionError("secret")
    else:
        queue_connection.ping.side_effect = RedisConnectionError("secret")
    client.app.state.engine = engine
    client.app.state.cache = cache
    client.app.state.queue_connection = queue_connection
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["services"][failed_service] == "unavailable"
    assert "secret" not in response.text


def test_cors_allows_local_frontend_authorization_header(client):
    response = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
