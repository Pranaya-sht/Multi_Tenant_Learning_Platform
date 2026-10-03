from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.roles import Role
from app.core.security import hash_password
from app.models import Tenant, User
from tests.support import PASSWORD, course, request

EMAIL = "shared@example.com"
OTHER_PASSWORD = "Other-tenant-password!"
PLATFORM_PASSWORD = "Platform-shared-password!"


@pytest.fixture
def accounts(api):
    created = {}
    for actor, password in (("ta", PASSWORD), ("tb", OTHER_PASSWORD)):
        response = request(
            api,
            "POST",
            "/tenant/users",
            actor,
            json={"name": "Shared learner", "email": EMAIL.upper(), "password": password},
        )
        assert response.status_code == 201, response.text
        created[actor] = response.json()
    platform = request(
        api,
        "POST",
        "/platform-users",
        "root",
        json={
            "name": "Shared viewer",
            "email": EMAIL,
            "password": PLATFORM_PASSWORD,
            "role": "super_viewer",
        },
    )
    assert platform.status_code == 201
    created["platform"] = platform.json()
    return created


def test_email_is_unique_per_tenant_and_within_platform(api, accounts):
    assert len({user["id"] for user in accounts.values()}) == 3
    for actor in ("ta", "tb"):
        response = request(
            api,
            "POST",
            "/tenant/users",
            actor,
            json={"name": "Duplicate", "email": EMAIL, "password": PASSWORD},
        )
        assert response.status_code == 409
    response = request(
        api,
        "POST",
        "/platform-users",
        "root",
        json={"name": "Duplicate", "email": EMAIL, "password": PASSWORD, "role": "admin"},
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "slug,password,identity",
    [
        ("institute-a", PASSWORD, "ta"),
        ("institute-b", OTHER_PASSWORD, "tb"),
        (None, PLATFORM_PASSWORD, "platform"),
        (None, PASSWORD, None),
        ("institute-b", PASSWORD, None),
        ("missing-tenant", PASSWORD, None),
        ("institute-a", PLATFORM_PASSWORD, None),
    ],
)
def test_login_uses_explicit_account_scope(api, accounts, slug, password, identity):
    response = api.post(
        "/api/v1/auth/login",
        json={"email": EMAIL.upper(), "password": password, "tenant_slug": slug},
    )
    assert response.status_code == (200 if identity else 401)
    if identity:
        assert response.json()["user"]["id"] == accounts[identity]["id"]
        assert response.json()["user"]["tenant_id"] == accounts[identity]["tenant_id"]
    else:
        assert response.json()["detail"] == "Invalid email or password"


def test_same_email_accounts_have_independent_tokens_and_tenant_access(api, accounts):
    headers = {}
    for key, slug, password in (
        ("a", "institute-a", PASSWORD),
        ("b", "institute-b", OTHER_PASSWORD),
    ):
        response = api.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": password, "tenant_slug": slug}
        )
        headers[key] = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert api.get("/api/v1/tenant", headers=headers["a"]).json()["id"] == api.tenants["a"].id
    assert api.get("/api/v1/tenant", headers=headers["b"]).json()["id"] == api.tenants["b"].id
    content = course(api)
    assert (
        request(
            api,
            "POST",
            "/tenant/assignments",
            json={"course_id": content["id"], "user_id": accounts["ta"]["id"]},
        ).status_code
        == 201
    )
    course_path = "/api/v1/tenant/courses/" + content["id"]
    assert api.get(course_path, headers=headers["a"]).status_code == 200
    assert api.get(course_path, headers=headers["b"]).status_code == 404
    assert api.post("/api/v1/auth/logout", headers=headers["a"]).status_code == 204
    assert api.get("/api/v1/auth/me", headers=headers["a"]).status_code == 401
    assert api.get("/api/v1/auth/me", headers=headers["b"]).status_code == 200


def test_email_migration_preserves_accounts_and_refuses_destructive_downgrade(database):
    from alembic.config import Config

    from alembic import command

    config = Config("alembic.ini")
    with database.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_learning_schema")
        tenant_ids = []
        for slug in ("migration-a", "migration-b"):
            tenant_ids.append(
                connection.execute(
                    Tenant.__table__.insert().values(
                        name=slug,
                        slug=slug,
                        trial_expires_at=datetime.now(UTC) + timedelta(days=14),
                    )
                ).inserted_primary_key[0]
            )
        values = {
            "email": EMAIL,
            "name": "Preserved learner",
            "role": Role.TENANT_USER,
            "password_hash": hash_password(PASSWORD),
        }
        connection.execute(User.__table__.insert().values(tenant_id=tenant_ids[0], **values))
        original = dict(connection.execute(select(User.__table__)).mappings().one())
        command.upgrade(config, "0002_tenant_scoped_email")
        assert dict(connection.execute(select(User.__table__)).mappings().one()) == original
        connection.execute(User.__table__.insert().values(tenant_id=tenant_ids[1], **values))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(User.__table__.insert().values(tenant_id=tenant_ids[0], **values))
        with pytest.raises(RuntimeError, match="cross-scope duplicates"):
            command.downgrade(config, "0001_learning_schema")
        assert connection.scalar(select(func.count()).select_from(User)) == 2
