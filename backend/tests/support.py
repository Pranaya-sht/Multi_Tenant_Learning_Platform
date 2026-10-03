import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import create_app
from app.models import Tenant, User

PASSWORD = "Learning-test-password!"
PASSWORD_HASH = hash_password(PASSWORD)


class MemoryCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value


@pytest.fixture
def database():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        schema = "test_" + uuid4().hex
        administrative_engine = create_engine(url)
        with administrative_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
        try:
            yield engine
        finally:
            engine.dispose()
            # Only the schema generated above is removed; never drop the supplied database.
            with administrative_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            administrative_engine.dispose()
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def api(database, settings):
    Base.metadata.create_all(database)
    now = datetime.now(UTC)
    with Session(database) as session:
        tenants = {
            key: Tenant(
                name=f"Institute {key.upper()}",
                slug=f"institute-{key}",
                created_at=now,
                trial_expires_at=now + timedelta(days=14),
            )
            for key in ("a", "b")
        }
        session.add_all(tenants.values())
        session.flush()
        users = {}
        for key, role, tenant in (
            ("root", Role.SUPER_ADMIN, None),
            ("admin", Role.ADMIN, None),
            ("viewer", Role.SUPER_VIEWER, None),
            ("ta", Role.TENANT_ADMIN, "a"),
            ("la", Role.TENANT_USER, "a"),
            ("la2", Role.TENANT_USER, "a"),
            ("tb", Role.TENANT_ADMIN, "b"),
            ("lb", Role.TENANT_USER, "b"),
        ):
            users[key] = User(
                name=key,
                email=f"{key}@example.com",
                role=role,
                tenant_id=tenants[tenant].id if tenant else None,
                password_hash=PASSWORD_HASH,
            )
        session.add_all(users.values())
        session.commit()
        for item in [*tenants.values(), *users.values()]:
            session.refresh(item)
            session.expunge(item)
    with TestClient(create_app(settings, engine=database)) as client:
        client.app.state.cache = MemoryCache()
        client.app.state.queue_connection = MagicMock()
        client.users, client.tenants, client.database = users, tenants, database
        client.headers_for = lambda key: {
            "Authorization": "Bearer "
            + create_access_token(users[key].id, settings, tenant_id=users[key].tenant_id)
        }
        yield client


def request(api, method, path, role="ta", **kwargs):
    return api.request(method, "/api/v1" + path, headers=api.headers_for(role), **kwargs)


def course(api, role="ta", lessons=2):
    response = request(api, "POST", "/tenant/courses", role, json={"title": "Python foundations"})
    assert response.status_code == 201, response.text
    data = response.json()
    data["lessons"] = []
    for position in range(1, lessons + 1):
        response = request(
            api,
            "POST",
            f"/tenant/courses/{data['id']}/lessons",
            role,
            json={
                "title": f"Lesson {position}",
                "content": "Read this lesson",
                "position": position,
            },
        )
        assert response.status_code == 201, response.text
        data["lessons"].append(response.json())
    return data


def assign(api, data, user="la", role="ta"):
    return request(
        api,
        "POST",
        "/tenant/assignments",
        role,
        json={"course_id": data["id"], "user_id": api.users[user].id},
    )
