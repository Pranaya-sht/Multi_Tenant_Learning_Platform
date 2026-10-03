import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.core.security import create_access_token
from app.db.base import Base
from app.models import Assignment, Course, LessonProgress, Tenant, User
from app.services.tenants import expire_due_tenants
from tests.support import PASSWORD, assign, course, request


def test_login_me_logout_revokes_the_token(api):
    response = api.post(
        "/api/v1/auth/login",
        json={"email": "LA@example.com", "password": PASSWORD, "tenant_slug": "institute-a"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert api.get("/api/v1/auth/me", headers=headers).json()["id"] == api.users["la"].id
    assert "password_hash" not in response.text
    assert api.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_public_institute_search_returns_bounded_names_and_slugs_only(api):
    response = api.get("/api/v1/auth/institutes", params={"q": "institute"})
    assert response.status_code == 200
    assert response.json() == [
        {"name": "Institute A", "slug": "institute-a"},
        {"name": "Institute B", "slug": "institute-b"},
    ]
    assert api.get("/api/v1/auth/institutes", params={"q": "tute-b"}).json() == [
        {"name": "Institute B", "slug": "institute-b"}
    ]
    assert api.get("/api/v1/auth/institutes", params={"q": "%_"}).json() == []
    assert api.get("/api/v1/auth/institutes", params={"q": "a"}).status_code == 422


@pytest.mark.parametrize(
    "email,password", [("la@example.com", "wrong"), ("unknown@example.com", PASSWORD)]
)
def test_invalid_login_has_uniform_response(api, email, password):
    response = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": "institute-a"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.parametrize(
    "role,status", [("root", 200), ("admin", 200), ("viewer", 200), ("ta", 403), ("la", 403)]
)
def test_platform_tenant_read_permissions(api, role, status):
    assert request(api, "GET", "/tenants", role).status_code == status


@pytest.mark.parametrize(
    "role,status", [("root", 201), ("admin", 201), ("viewer", 403), ("ta", 403), ("la", 403)]
)
def test_tenant_creation_permissions_and_trial(api, role, status):
    response = request(
        api,
        "POST",
        "/tenants",
        role,
        json={
            "name": "New Institute",
            "slug": "new-institute",
            "admin": {
                "name": "Institute administrator",
                "email": "new-admin@example.com",
                "password": PASSWORD,
            },
        },
    )
    assert response.status_code == status, response.text
    if status == 201:
        assert response.json()["status"] == "trial_active"
        assert datetime.fromisoformat(response.json()["trial_expires_at"]) - datetime.fromisoformat(
            response.json()["created_at"]
        ) == timedelta(days=14)
        assert (
            api.post(
                "/api/v1/auth/login",
                json={
                    "email": "new-admin@example.com",
                    "password": PASSWORD,
                    "tenant_slug": "new-institute",
                },
            ).status_code
            == 200
        )


@pytest.mark.parametrize(
    "role,status", [("root", 201), ("admin", 403), ("viewer", 403), ("ta", 403), ("la", 403)]
)
def test_platform_user_creation_permissions(api, role, status):
    assert (
        request(
            api,
            "POST",
            "/platform-users",
            role,
            json={
                "name": "Viewer",
                "email": "other-viewer@example.com",
                "password": PASSWORD,
                "role": "super_viewer",
            },
        ).status_code
        == status
    )


def test_multiple_platform_super_admins_are_allowed(api):
    response = request(
        api,
        "POST",
        "/platform-users",
        "root",
        json={
            "name": "Second Super Admin",
            "email": "second.super@example.com",
            "password": PASSWORD,
            "role": "super_admin",
        },
    )
    assert response.status_code == 201, response.text
    login = api.post(
        "/api/v1/auth/login",
        json={"email": "second.super@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "super_admin"


@pytest.mark.parametrize(
    "role,status", [("root", 403), ("admin", 403), ("viewer", 403), ("ta", 201), ("la", 403)]
)
def test_learning_mutation_role_permissions(api, role, status):
    assert (
        request(api, "POST", "/tenant/courses", role, json={"title": "A course"}).status_code
        == status
    )


def test_course_assignment_progress_and_idempotent_completion(api):
    data = course(api)
    assert request(api, "GET", f"/tenant/courses/{data['id']}", "la").status_code == 404
    assignment = assign(api, data).json()
    assert request(api, "GET", "/tenant/courses", "la").json()[0]["id"] == data["id"]
    assert (
        request(api, "GET", f"/tenant/courses/{data['id']}", "la").json()["lessons"][0]["content"]
        == "Read this lesson"
    )
    for index, lesson in enumerate(data["lessons"]):
        path = f"/tenant/assignments/{assignment['id']}/lessons/{lesson['id']}/complete"
        first = request(api, "PUT", path, "la")
        repeated = request(api, "PUT", path, "la")
        assert first.status_code == repeated.status_code == 200
        assert first.json() == repeated.json()
        assert first.json()["completed_lessons"] == index + 1
    assert repeated.json()["percent_complete"] == 100
    assert repeated.json()["is_complete"] is True
    assert (
        request(api, "GET", f"/tenant/assignments/{assignment['id']}/progress").json()[
            "completed_lessons"
        ]
        == 2
    )


def test_batch_enrollment_creates_two_scoped_assignments_atomically(api):
    data = course(api)
    ids = [api.users["la2"].id, api.users["la"].id]
    path = "/tenant/assignments/batch"
    response = request(api, "POST", path, json={"course_id": data["id"], "user_ids": ids})
    assert response.status_code == 201, response.text
    assert [item["user_id"] for item in response.json()] == ids
    assert all(item["tenant_id"] == api.tenants["a"].id for item in response.json())
    assert {item["id"] for item in request(api, "GET", "/tenant/assignments").json()} == {
        item["id"] for item in response.json()
    }
    assert request(api, "GET", f"/tenant/courses/{data['id']}", "la").status_code == 200
    assert request(api, "GET", f"/tenant/courses/{data['id']}", "la2").status_code == 200


def test_batch_enrollment_rejects_invalid_sets_without_partial_writes(api):
    data = course(api)
    path = "/tenant/assignments/batch"
    valid = api.users["la"].id
    for other, status in [
        (api.users["lb"].id, 404),
        (api.users["ta"].id, 409),
    ]:
        response = request(
            api, "POST", path, json={"course_id": data["id"], "user_ids": [valid, other]}
        )
        assert response.status_code == status, response.text
        assert request(api, "GET", "/tenant/assignments").json() == []
    for ids in [[valid, valid], [], [str(uuid4()) for _ in range(51)]]:
        assert (
            request(api, "POST", path, json={"course_id": data["id"], "user_ids": ids}).status_code
            == 422
        )
    assert (
        request(
            api, "POST", path, "la", json={"course_id": data["id"], "user_ids": [valid]}
        ).status_code
        == 403
    )
    assign(api, data, "la2")
    response = request(
        api,
        "POST",
        path,
        json={"course_id": data["id"], "user_ids": [valid, api.users["la2"].id]},
    )
    assert response.status_code == 409
    assert [item["user_id"] for item in request(api, "GET", "/tenant/assignments").json()] == [
        api.users["la2"].id
    ]


def test_batch_enrollment_respects_course_and_trial_rules(api):
    path = "/tenant/assignments/batch"
    learner_id = api.users["la"].id
    empty = course(api, lessons=0)
    assert (
        request(
            api, "POST", path, json={"course_id": empty["id"], "user_ids": [learner_id]}
        ).status_code
        == 409
    )
    data = course(api)
    foreign = course(api, "tb")
    assert (
        request(
            api, "POST", path, json={"course_id": foreign["id"], "user_ids": [learner_id]}
        ).status_code
        == 404
    )
    assert (
        request(
            api,
            "PATCH",
            f"/tenant/users/{learner_id}",
            json={"is_active": False},
        ).status_code
        == 200
    )
    assert (
        request(
            api, "POST", path, json={"course_id": data["id"], "user_ids": [learner_id]}
        ).status_code
        == 409
    )
    with Session(api.database) as session:
        tenant = session.get(Tenant, api.tenants["a"].id)
        tenant.created_at = datetime.now(UTC) - timedelta(days=14)
        tenant.trial_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert (
        request(
            api, "POST", path, json={"course_id": data["id"], "user_ids": [learner_id]}
        ).status_code
        == 403
    )
    assert request(api, "GET", "/tenant/assignments", "tb").json() == []


def test_batched_progress_matches_individual_results_and_enforces_assignment_access(api):
    first, second = course(api), course(api)
    own = assign(api, first, "la").json()
    other = assign(api, second, "la2").json()
    request(
        api,
        "PUT",
        f"/tenant/assignments/{own['id']}/lessons/{first['lessons'][0]['id']}/complete",
        "la",
    )
    path = "/tenant/assignments/progress"
    params = [("assignment_ids", own["id"]), ("assignment_ids", other["id"])]
    batched = request(api, "GET", path, params=params)
    assert batched.status_code == 200, batched.text
    assert batched.json() == [
        request(api, "GET", f"/tenant/assignments/{item['id']}/progress").json()
        for item in (own, other)
    ]
    assert request(api, "GET", path, "la", params=params).status_code == 404
    assert request(api, "GET", path, "la", params=[params[0]]).json() == batched.json()[:1]
    assert request(api, "GET", path, "tb", params=[params[0]]).status_code == 404
    assert request(api, "GET", path, params=params * 6).status_code == 422


def test_course_page_search_reaches_every_record_and_respects_assignment_scope(api):
    assignable = course(api)
    request(api, "POST", "/tenant/courses", json={"title": "100%_Python"})
    for index in range(11):
        request(api, "POST", "/tenant/courses", json={"title": f"Course {index:02d}"})
    course(api, "tb")
    full = request(api, "GET", "/tenant/courses", params={"limit": 100}).json()
    pages = [
        request(api, "GET", "/tenant/courses/page", params={"limit": 5, "offset": offset})
        for offset in (0, 5, 10)
    ]
    assert all(page.status_code == 200 for page in pages)
    assert all(page.json()["total"] == 13 for page in pages)
    assert [row for page in pages for row in page.json()["items"]] == full
    literal = request(api, "GET", "/tenant/courses/page", params={"q": "%_"}).json()
    assert [item["title"] for item in literal["items"]] == ["100%_Python"]
    assert request(api, "GET", "/tenant/courses/page", "la").json()["total"] == 0
    assign(api, assignable)
    learner = request(api, "GET", "/tenant/courses/page", "la").json()
    assert learner["total"] == 1
    assert learner["items"][0]["id"] == assignable["id"]
    request(api, "DELETE", f"/tenant/courses/{assignable['id']}")
    assert (
        request(api, "GET", "/tenant/courses/page", "la", params={"status": "active"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        request(api, "GET", "/tenant/courses/page", "la", params={"status": "archived"}).json()[
            "total"
        ]
        == 1
    )


@pytest.mark.parametrize("role", ["tb", "lb", "la2"])
def test_other_tenant_or_unassigned_learner_cannot_read_course(api, role):
    data = course(api)
    assign(api, data)
    assert request(api, "GET", f"/tenant/courses/{data['id']}", role).status_code == 404


def test_cross_tenant_writes_and_progress_are_denied(api):
    data_a, data_b = course(api), course(api, "tb")
    assert assign(api, data_a, "lb").status_code == 404
    assert assign(api, data_b, "la").status_code == 404
    assert (
        request(
            api, "PATCH", f"/tenant/users/{api.users['lb'].id}", json={"name": "Changed"}
        ).status_code
        == 404
    )
    assert (
        request(
            api, "PATCH", f"/tenant/courses/{data_b['id']}", json={"title": "Changed"}
        ).status_code
        == 404
    )
    assignment = assign(api, data_a).json()
    base = f"/tenant/assignments/{assignment['id']}"
    assert request(api, "GET", base + "/progress", "lb").status_code == 404
    assert request(api, "GET", base + "/progress", "la2").status_code == 404
    assert (
        request(
            api, "PUT", base + f"/lessons/{data_b['lessons'][0]['id']}/complete", "la"
        ).status_code
        == 404
    )
    assert (
        request(
            api, "PUT", base + f"/lessons/{data_a['lessons'][0]['id']}/complete", "ta"
        ).status_code
        == 403
    )


def test_duplicate_empty_archived_and_admin_assignments_are_rejected(api):
    empty = course(api, lessons=0)
    assert assign(api, empty).status_code == 409
    data = course(api)
    assert assign(api, data, "ta").status_code == 409
    assert assign(api, data).status_code == 201
    assert assign(api, data).status_code == 409
    assert (
        request(
            api,
            "POST",
            f"/tenant/courses/{data['id']}/lessons",
            json={"title": "Late lesson", "content": "Text", "position": 3},
        ).status_code
        == 409
    )
    assert request(api, "DELETE", f"/tenant/courses/{data['id']}").status_code == 204
    assert assign(api, data, "la2").status_code == 409
    assert request(api, "GET", f"/tenant/courses/{data['id']}", "la").status_code == 200


def test_cache_is_tenant_scoped_invalidated_and_authorized_before_read(api):
    data = course(api)
    assignment = assign(api, data).json()
    path = f"/tenant/courses/{data['id']}"
    assert request(api, "GET", path, "la").status_code == 200
    assert all(
        key.startswith(f"tenant:{api.tenants['a'].id}:") for key in api.app.state.cache.values
    )
    assert request(api, "PATCH", path, json={"title": "Updated title"}).status_code == 200
    assert request(api, "GET", path, "la").json()["title"] == "Updated title"
    assert request(api, "DELETE", f"/tenant/assignments/{assignment['id']}").status_code == 204
    assert request(api, "GET", path, "la").status_code == 404
    cache = MagicMock()
    cache.get.side_effect = RedisConnectionError("down")
    cache.setex.side_effect = RedisConnectionError("down")
    api.app.state.cache = cache
    assert request(api, "GET", path).status_code == 200


def test_expiration_boundary_repeated_processing_and_reactivation(api):
    data = course(api)
    now = datetime.now(UTC)
    with Session(api.database) as session:
        tenant = session.get(Tenant, api.tenants["a"].id)
        tenant.created_at = now - timedelta(days=14)
        tenant.trial_expires_at = now
        session.commit()
        assert request(api, "GET", "/tenant/courses", "la").status_code == 403
        assert expire_due_tenants(session, now) == 1
        assert expire_due_tenants(session, now) == 0
        assert session.get(Course, data["id"]) is not None
    assert request(api, "GET", "/tenant", "la").json()["status"] == "expired"
    path = f"/tenants/{api.tenants['a'].id}/reactivate"
    assert request(api, "POST", path, "admin", json={"days": 14}).status_code == 403
    assert request(api, "POST", path, "root", json={"days": 14}).status_code == 200
    assert request(api, "GET", "/tenant/courses").status_code == 200


def test_disabling_resetting_and_last_admin_protection(api):
    assert (
        request(
            api, "PATCH", f"/tenant/users/{api.users['ta'].id}", json={"is_active": False}
        ).status_code
        == 409
    )
    learner = api.users["la"].id
    assert (
        request(
            api,
            "PUT",
            f"/tenant/users/{learner}/password",
            json={"password": "A-new-learning-password!"},
        ).status_code
        == 204
    )
    assert request(api, "GET", "/auth/me", "la").status_code == 401
    assert (
        request(api, "PATCH", f"/tenant/users/{learner}", json={"is_active": False}).status_code
        == 200
    )
    assert (
        api.post(
            "/api/v1/auth/login",
            json={
                "email": "la@example.com",
                "password": "A-new-learning-password!",
                "tenant_slug": "institute-a",
            },
        ).status_code
        == 401
    )


def test_one_tenant_admin_rule_and_database_constraint(api):
    admin_id = api.users["ta"].id
    learner_id = api.users["la"].id
    assert (
        request(
            api,
            "POST",
            "/tenant/users",
            json={
                "name": "Second administrator",
                "email": "second.admin@example.com",
                "password": PASSWORD,
                "role": "tenant_admin",
            },
        ).status_code
        == 409
    )
    assert (
        request(
            api, "PATCH", f"/tenant/users/{learner_id}", json={"role": "tenant_admin"}
        ).status_code
        == 409
    )
    assert (
        request(api, "PATCH", f"/tenant/users/{admin_id}", json={"role": "tenant_user"}).status_code
        == 409
    )
    with Session(api.database) as session:
        session.add(
            User(
                tenant_id=api.tenants["a"].id,
                email="direct.admin@example.com",
                name="Direct administrator",
                role=Role.TENANT_ADMIN,
                password_hash="unused",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_admin_transfer_is_atomic_and_revokes_old_tokens_without_losing_progress(api):
    data = course(api)
    assignment = assign(api, data).json()
    progress_path = f"/tenant/assignments/{assignment['id']}/progress"
    completion_path = (
        f"/tenant/assignments/{assignment['id']}/lessons/{data['lessons'][0]['id']}/complete"
    )
    assert request(api, "PUT", completion_path, "la").status_code == 200
    learner_id = api.users["la"].id
    transfer = f"/tenant/users/{learner_id}/transfer-admin"
    assert request(api, "POST", transfer, "la").status_code == 403
    assert (
        request(api, "POST", f"/tenant/users/{api.users['lb'].id}/transfer-admin").status_code
        == 404
    )
    assert (
        request(api, "POST", f"/tenant/users/{api.users['ta'].id}/transfer-admin").status_code
        == 409
    )
    assert (
        request(api, "PATCH", f"/tenant/users/{learner_id}", json={"is_active": False}).status_code
        == 200
    )
    assert request(api, "POST", transfer).status_code == 409
    assert (
        request(api, "PATCH", f"/tenant/users/{learner_id}", json={"is_active": True}).status_code
        == 200
    )

    response = request(api, "POST", transfer)
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "tenant_admin"
    assert request(api, "GET", "/auth/me", "ta").status_code == 401
    assert request(api, "GET", "/auth/me", "la").status_code == 401
    login = api.post(
        "/api/v1/auth/login",
        json={"email": "la@example.com", "password": PASSWORD, "tenant_slug": "institute-a"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "tenant_admin"
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (
        api.post(
            f"/api/v1/tenant/users/{api.users['ta'].id}/transfer-admin", headers=headers
        ).status_code
        == 200
    )
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401
    learner_login = api.post(
        "/api/v1/auth/login",
        json={"email": "la@example.com", "password": PASSWORD, "tenant_slug": "institute-a"},
    )
    assert learner_login.json()["user"]["role"] == "tenant_user"
    headers = {"Authorization": "Bearer " + learner_login.json()["access_token"]}
    assert api.get("/api/v1" + progress_path, headers=headers).json()["completed_lessons"] == 1
    with Session(api.database) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.tenant_id == api.tenants["a"].id,
                    User.role == Role.TENANT_ADMIN,
                )
            )
            == 1
        )


def test_deactivating_and_reactivating_learner_preserves_progress(api):
    data = course(api)
    assignment = assign(api, data).json()
    progress_path = f"/tenant/assignments/{assignment['id']}/progress"
    completion_path = (
        f"/tenant/assignments/{assignment['id']}/lessons/{data['lessons'][0]['id']}/complete"
    )
    assert request(api, "PUT", completion_path, "la").status_code == 200
    user_path = f"/tenant/users/{api.users['la'].id}"
    assert request(api, "PATCH", user_path, json={"is_active": False}).status_code == 200
    assert request(api, "GET", progress_path, "la").status_code == 401
    assert request(api, "GET", progress_path).json()["completed_lessons"] == 1
    assert request(api, "PATCH", user_path, json={"is_active": True}).status_code == 200
    login = api.post(
        "/api/v1/auth/login",
        json={"email": "la@example.com", "password": PASSWORD, "tenant_slug": "institute-a"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert api.get("/api/v1" + progress_path, headers=headers).json()["completed_lessons"] == 1


def test_mass_assignment_role_escalation_pagination_and_missing_auth(api):
    assert api.get("/api/v1/tenant/courses").status_code == 401
    assert (
        request(
            api,
            "POST",
            "/tenant/users",
            json={
                "name": "New learner",
                "email": "new@example.com",
                "password": PASSWORD,
                "role": "super_admin",
            },
        ).status_code
        == 422
    )
    assert (
        request(
            api,
            "POST",
            "/tenant/courses",
            json={"title": "Course", "tenant_id": api.tenants["b"].id},
        ).status_code
        == 422
    )
    assert request(api, "GET", "/tenant/users?limit=1").status_code == 200
    assert len(request(api, "GET", "/tenant/users?limit=1").json()) == 1
    assert request(api, "GET", "/tenant/users?limit=101").status_code == 422
    assert request(api, "GET", "/tenant/courses/not-a-uuid").status_code == 422


def test_database_rejects_cross_tenant_assignment(api):
    data = course(api)
    with Session(api.database) as session:
        session.add(
            Assignment(
                tenant_id=api.tenants["a"].id, course_id=data["id"], user_id=api.users["lb"].id
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.scalar(select(func.count()).select_from(Assignment)) == 0


def test_assignment_revocation_removes_progress(api):
    data = course(api)
    assignment = assign(api, data).json()
    assert (
        request(
            api,
            "PUT",
            f"/tenant/assignments/{assignment['id']}/lessons/{data['lessons'][0]['id']}/complete",
            "la",
        ).status_code
        == 200
    )
    assert request(api, "DELETE", f"/tenant/assignments/{assignment['id']}").status_code == 204
    with Session(api.database) as session:
        assert session.scalar(select(func.count()).select_from(LessonProgress)) == 0


def test_migration_round_trip(database):
    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command

    config = Config("alembic.ini")
    with database.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert {"tenants", "users", "courses", "lessons", "assignments", "lesson_progress"} <= set(
            inspect(connection).get_table_names()
        )
        command.downgrade(config, "base")
        assert not (set(Base.metadata.tables) & set(inspect(connection).get_table_names()))


@pytest.mark.parametrize("legacy_state", ["duplicate", "missing"])
def test_admin_uniqueness_migration_refuses_legacy_invalid_account_state(database, legacy_state):
    from alembic.config import Config

    from alembic import command

    config = Config("alembic.ini")
    with database.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "f1fa000f70dd")
    with Session(database) as session:
        tenant = Tenant(
            name="Legacy institute",
            slug="legacy-institute",
            trial_expires_at=datetime.now(UTC) + timedelta(days=14),
        )
        session.add(tenant)
        session.flush()
        if legacy_state == "duplicate":
            session.add_all(
                [
                    User(
                        tenant_id=tenant.id,
                        name=f"Admin {index}",
                        email=f"admin{index}@example.com",
                        role=Role.TENANT_ADMIN,
                        password_hash="legacy",
                    )
                    for index in (1, 2)
                ]
            )
        session.commit()
    with database.begin() as connection:
        config.attributes["connection"] = connection
        with pytest.raises(RuntimeError, match="one (active )?Tenant Admin per institute"):
            command.upgrade(config, "head")


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL row locks required")
def test_concurrent_completion_is_idempotent(api):
    data = course(api)
    assignment = assign(api, data).json()
    path = f"/tenant/assignments/{assignment['id']}/lessons/{data['lessons'][0]['id']}/complete"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: request(api, "PUT", path, "la"), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    with Session(api.database) as session:
        assert session.scalar(select(func.count()).select_from(LessonProgress)) == 1


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL row locks required")
def test_concurrent_admin_transfers_preserve_one_admin(api):
    def transfer(learner):
        return request(api, "POST", f"/tenant/users/{api.users[learner].id}/transfer-admin")

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(transfer, ["la", "la2"]))
    assert sorted(r.status_code for r in responses) == [200, 401]
    with Session(api.database) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.tenant_id == api.tenants["a"].id,
                    User.role == Role.TENANT_ADMIN,
                )
            )
            == 1
        )


def test_reactivation_does_not_expire_again_and_preserves_progress(api):
    data = course(api)
    assignment = assign(api, data).json()
    path = f"/tenant/assignments/{assignment['id']}/lessons/{data['lessons'][0]['id']}/complete"
    assert request(api, "PUT", path, "la").status_code == 200
    tenant = api.tenants["a"].id
    assert request(api, "POST", f"/tenants/{tenant}/expire", "root").status_code == 200
    assert request(api, "PUT", path, "la").status_code == 403
    assert (
        request(api, "POST", f"/tenants/{tenant}/reactivate", "root", json={"days": 7}).status_code
        == 200
    )
    with Session(api.database) as session:
        assert expire_due_tenants(session) == 0
    assert (
        request(api, "GET", f"/tenant/assignments/{assignment['id']}/progress", "la").json()[
            "completed_lessons"
        ]
        == 1
    )


def test_demo_bootstrap_is_repeatable(api, settings):
    from app.bootstrap import seed_demo

    with Session(api.database) as session:
        seed_demo(session, settings)
        first_counts = [
            session.scalar(select(func.count()).select_from(model))
            for model in (Tenant, User, Course, Assignment)
        ]
        seed_demo(session, settings)
        assert first_counts == [
            session.scalar(select(func.count()).select_from(model))
            for model in (Tenant, User, Course, Assignment)
        ]
    response = api.post(
        "/api/v1/auth/login",
        json={
            "email": "river.learner@example.com",
            "password": "LocalDemo-learning-2026!",
            "tenant_slug": "river-institute",
        },
    )
    assert response.status_code == 200


def test_signed_wrong_tenant_and_invalid_bearer_are_rejected(api, settings):
    forged_context = create_access_token(
        api.users["la"].id, settings, tenant_id=api.tenants["b"].id
    )
    for token in ("invalid-token", forged_context):
        assert (
            api.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code
            == 401
        )


@pytest.mark.skipif(not os.environ.get("REDIS_TEST_URL"), reason="Real Redis URL required")
def test_real_redis_cache_preserves_authorization(api, settings):
    from app.infrastructure.redis import create_cache

    data = course(api)
    assignment = assign(api, data).json()
    cache = create_cache(
        settings.model_copy(update={"redis_cache_url": os.environ["REDIS_TEST_URL"]})
    )
    api.app.state.cache = cache
    prefix = f"tenant:{api.tenants['a'].id}:"
    try:
        path = f"/tenant/courses/{data['id']}"
        assert request(api, "GET", path, "la").status_code == 200
        keys = list(cache.scan_iter(match=prefix + "*"))
        assert len(keys) == 1
        assert 0 < cache.ttl(keys[0]) <= settings.cache_seconds
        assert request(api, "GET", path, "lb").status_code == 404
        assert request(api, "DELETE", f"/tenant/assignments/{assignment['id']}").status_code == 204
        assert request(api, "GET", path, "la").status_code == 404
    finally:
        keys = list(cache.scan_iter(match=prefix + "*"))
        if keys:
            cache.delete(*keys)
        cache.close()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL locks required")
@pytest.mark.parametrize("change", ["expire", "disable", "demote"])
def test_learning_rechecks_identity_and_tenant_after_waiting_for_lock(api, change):
    changed = False

    def change_before_lock(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if changed or "FOR UPDATE" not in statement:
            return
        changed = True
        # Apply a concurrent committed change after authentication, before lock acquisition.
        with Session(api.database) as session:
            if change == "expire":
                session.get(Tenant, api.tenants["a"].id).status = "expired"
            else:
                target = session.get(User, api.users["ta"].id)
                target.token_version += 1
                if change == "disable":
                    target.is_active = False
                else:
                    target.role = Role.TENANT_USER
            session.commit()

    event.listen(api.database, "before_cursor_execute", change_before_lock)
    try:
        response = request(api, "POST", "/tenant/courses", json={"title": "Denied course"})
        assert changed
        assert response.status_code == (403 if change == "expire" else 401)
        with Session(api.database) as session:
            assert session.scalar(select(func.count()).select_from(Course)) == 0
    finally:
        event.remove(api.database, "before_cursor_execute", change_before_lock)


@pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") and os.environ.get("REDIS_TEST_URL")),
    reason="PostgreSQL and real Redis required",
)
def test_rq_worker_executes_repeatable_expiration_job(api, settings, monkeypatch):
    from rq.job import JobStatus

    from app.infrastructure.redis import create_queue, create_queue_connection
    from app.worker import create_worker

    with Session(api.database) as session:
        schema = session.scalar(text("SELECT current_schema()"))
        tenant = session.get(Tenant, api.tenants["a"].id)
        tenant.created_at = datetime.now(UTC) - timedelta(days=15)
        tenant.trial_expires_at = datetime.now(UTC) - timedelta(days=1)
        session.commit()
    scoped_url = api.database.url.update_query_dict({"options": "-csearch_path=" + schema})
    monkeypatch.setenv("DATABASE_URL", scoped_url.render_as_string(hide_password=False))
    monkeypatch.setenv("JWT_SECRET", settings.jwt_secret.get_secret_value())
    configuration = settings.model_copy(
        update={
            "redis_queue_url": os.environ["REDIS_TEST_URL"],
            "queue_name": "test-expiration-" + uuid4().hex,
        }
    )
    connection = create_queue_connection(configuration, for_worker=True)
    queue = create_queue(configuration, connection)
    first = second = None
    try:
        first = queue.enqueue("app.jobs.expire_tenants", job_timeout=30)
        second = queue.enqueue("app.jobs.expire_tenants", job_timeout=30)
        worker = create_worker(queue, connection)
        worker.work(burst=True, logging_level="WARNING")
        for job in (first, second):
            job.refresh()
            assert job.get_status() == JobStatus.FINISHED
        assert first.return_value() == 1
        assert second.return_value() == 0
    finally:
        for job in (first, second):
            if job is not None:
                job.delete()
        queue.delete(delete_jobs=True)
        connection.close()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="PostgreSQL locks required")
def test_password_reset_does_not_overwrite_concurrent_token_revocation(api, settings):
    revoked = False

    def logout_before_user_lock(connection, cursor, statement, parameters, context, executemany):
        nonlocal revoked
        if revoked or "FROM users" not in statement or "FOR UPDATE" not in statement:
            return
        revoked = True
        with Session(api.database) as session:
            session.get(User, api.users["ta"].id).token_version += 1
            session.commit()

    event.listen(api.database, "before_cursor_execute", logout_before_user_lock)
    try:
        response = request(
            api,
            "PUT",
            f"/tenant/users/{api.users['ta'].id}/password",
            json={"password": "Updated-learning-password!"},
        )
        assert response.status_code == 204
        assert revoked
        with Session(api.database) as session:
            assert session.get(User, api.users["ta"].id).token_version == 2
        intermediate_token = create_access_token(
            api.users["ta"].id, settings, tenant_id=api.tenants["a"].id, version=1
        )
        assert (
            api.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer " + intermediate_token}
            ).status_code
            == 401
        )
    finally:
        event.remove(api.database, "before_cursor_execute", logout_before_user_lock)
