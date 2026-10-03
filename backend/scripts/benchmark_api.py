"""Repeatable local API baseline using a disposable PostgreSQL schema.

Set TEST_DATABASE_URL and REDIS_TEST_URL to local development services, then run
`uv run python -m scripts.benchmark_api`. Never points at the application's public schema.
"""

import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import create_app
from app.models import Assignment, Course, Lesson, LessonProgress, Tenant, User


def main() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    redis_url = os.environ.get("REDIS_TEST_URL")
    if not database_url or not redis_url:
        raise SystemExit("Set TEST_DATABASE_URL and REDIS_TEST_URL to local test services")
    if make_url(database_url).host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Benchmark refuses a non-loopback PostgreSQL host")
    if Redis.from_url(redis_url).connection_pool.connection_kwargs["host"] not in {
        "127.0.0.1",
        "localhost",
    }:
        raise SystemExit("Benchmark refuses a non-loopback Redis host")

    schema = "bench_" + uuid4().hex
    administrative_engine = create_engine(database_url)
    with administrative_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(database_url, connect_args={"options": f"-csearch_path={schema}"})
    tenant_id = None
    cache = Redis.from_url(redis_url, socket_connect_timeout=2)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            now = datetime.now(UTC)
            tenant = Tenant(
                name="Benchmark Institute",
                slug=schema,
                created_at=now,
                trial_expires_at=now + timedelta(days=14),
            )
            db.add(tenant)
            db.flush()
            password = hash_password("Benchmark-password-2026!")
            admin = User(
                tenant_id=tenant.id,
                name="Benchmark Admin",
                email="admin@benchmark.invalid",
                password_hash=password,
                role=Role.TENANT_ADMIN,
            )
            learner = User(
                tenant_id=tenant.id,
                name="Benchmark Learner",
                email="learner@benchmark.invalid",
                password_hash=password,
                role=Role.TENANT_USER,
            )
            db.add_all([tenant, admin, learner])
            db.flush()
            tenant_id = tenant.id
            courses = [
                Course(tenant_id=tenant.id, title=f"Benchmark course {i:03d}") for i in range(60)
            ]
            db.add_all(courses)
            db.flush()
            lessons = [
                Lesson(
                    tenant_id=tenant.id,
                    course_id=course.id,
                    title=f"Lesson {position}",
                    content="A short lesson for timing and response-size measurements.",
                    position=position,
                )
                for course in courses
                for position in range(1, 4)
            ]
            db.add_all(lessons)
            assignments = [
                Assignment(tenant_id=tenant.id, course_id=course.id, user_id=learner.id)
                for course in courses[:40]
            ]
            db.add_all(assignments)
            db.flush()
            for assignment in assignments:
                first_lesson = next(
                    lesson for lesson in lessons if lesson.course_id == assignment.course_id
                )
                db.add(
                    LessonProgress(
                        tenant_id=tenant.id,
                        assignment_id=assignment.id,
                        course_id=assignment.course_id,
                        user_id=learner.id,
                        lesson_id=first_lesson.id,
                    )
                )
            db.commit()
            admin_id, learner_id = admin.id, learner.id
            course_id, assignment_id = courses[0].id, assignments[0].id
            visible_assignment_ids = [assignment.id for assignment in assignments[:10]]

        settings = Settings(
            _env_file=None,
            database_url=database_url,
            redis_cache_url=redis_url,
            redis_queue_url=redis_url,
            queue_name=schema,
            jwt_secret="benchmark-secret-with-at-least-thirty-two-characters",
        )
        counter = [0]

        def count_query(connection, cursor, statement, parameters, context, executemany):
            counter[0] += 1

        event.listen(engine, "before_cursor_execute", count_query)
        with TestClient(create_app(settings, engine=engine)) as client:
            admin_headers = {
                "Authorization": "Bearer "
                + create_access_token(admin_id, settings, tenant_id=tenant_id)
            }
            learner_headers = {
                "Authorization": "Bearer "
                + create_access_token(learner_id, settings, tenant_id=tenant_id)
            }

            def measure(path, headers, *, cold_cache=False):
                samples = []
                query_counts = []
                response_bytes = 0
                for _ in range(21):
                    if cold_cache:
                        cache.delete(f"tenant:{tenant_id}:course:{course_id}:v1")
                    counter[0] = 0
                    started = time.perf_counter()
                    response = client.get("/api/v1" + path, headers=headers)
                    elapsed = (time.perf_counter() - started) * 1000
                    if response.status_code != 200:
                        raise RuntimeError(f"{path} returned {response.status_code}")
                    samples.append(elapsed)
                    query_counts.append(counter[0])
                    response_bytes = len(response.content)
                ordered = sorted(samples)
                return {
                    "median_ms": round(statistics.median(samples), 2),
                    "p95_ms": round(ordered[19], 2),
                    "sql_queries": sorted(set(query_counts)),
                    "response_bytes": response_bytes,
                }

            routes = {
                "admin_course_list_50": measure("/tenant/courses?limit=50&offset=0", admin_headers),
                "admin_course_list_100": measure(
                    "/tenant/courses?limit=100&offset=0", admin_headers
                ),
                "admin_course_page_10": measure(
                    "/tenant/courses/page?limit=10&offset=0", admin_headers
                ),
                "learner_course_list_50": measure(
                    "/tenant/courses?limit=50&offset=0", learner_headers
                ),
                "admin_assignment_list_50": measure(
                    "/tenant/assignments?limit=50&offset=0", admin_headers
                ),
                "learner_progress": measure(
                    f"/tenant/assignments/{assignment_id}/progress", learner_headers
                ),
                "learner_course_warm": measure(f"/tenant/courses/{course_id}", learner_headers),
                "learner_course_cold": measure(
                    f"/tenant/courses/{course_id}", learner_headers, cold_cache=True
                ),
            }

            def measure_visible_progress():
                samples = []
                query_counts = []
                response_bytes = 0
                for _ in range(21):
                    counter[0] = 0
                    started = time.perf_counter()
                    responses = [
                        client.get(
                            f"/api/v1/tenant/assignments/{identifier}/progress",
                            headers=admin_headers,
                        )
                        for identifier in visible_assignment_ids
                    ]
                    samples.append((time.perf_counter() - started) * 1000)
                    if any(response.status_code != 200 for response in responses):
                        raise RuntimeError("Progress requests failed")
                    query_counts.append(counter[0])
                    response_bytes = sum(len(response.content) for response in responses)
                return {
                    "median_ms": round(statistics.median(samples), 2),
                    "p95_ms": round(sorted(samples)[19], 2),
                    "sql_queries": sorted(set(query_counts)),
                    "response_bytes": response_bytes,
                    "requests": len(visible_assignment_ids),
                }

            routes["visible_progress_10_requests"] = measure_visible_progress()
            progress_query = "&".join(
                f"assignment_ids={identifier}" for identifier in visible_assignment_ids
            )
            routes["visible_progress_batch"] = measure(
                f"/tenant/assignments/progress?{progress_query}", admin_headers
            )

            def concurrent(path, headers):
                def call(_):
                    started = time.perf_counter()
                    response = client.get("/api/v1" + path, headers=headers)
                    return response.status_code, (time.perf_counter() - started) * 1000

                started = time.perf_counter()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(call, range(32)))
                elapsed = time.perf_counter() - started
                if any(status != 200 for status, _ in results):
                    raise RuntimeError("Concurrent requests failed")
                durations = sorted(duration for _, duration in results)
                return {
                    "requests": len(results),
                    "workers": 8,
                    "throughput_rps": round(len(results) / elapsed, 2),
                    "p95_ms": round(durations[30], 2),
                }

            print(
                json.dumps(
                    {
                        "dataset": "1 tenant, 2 users, 60 courses, 180 lessons, 40 assignments",
                        "routes": routes,
                        "concurrent_admin_course_list": concurrent(
                            "/tenant/courses?limit=50&offset=0", admin_headers
                        ),
                        "concurrent_learner_course_list": concurrent(
                            "/tenant/courses?limit=50&offset=0", learner_headers
                        ),
                    },
                    indent=2,
                )
            )
    finally:
        engine.dispose()
        try:
            if tenant_id:
                for key in cache.scan_iter(match=f"tenant:{tenant_id}:*"):
                    cache.delete(key)
        except RedisError:
            pass  # Cache entries expire by TTL; do not skip database schema cleanup.
        finally:
            cache.close()
        with administrative_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        administrative_engine.dispose()


if __name__ == "__main__":
    main()
