"""Explicit CLI bootstrap; never seed accounts automatically during API startup."""

import argparse
import getpass
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.roles import Role
from app.core.security import hash_password
from app.models import Assignment, Course, Lesson, Tenant, User
from app.schemas.domain import PlatformUserCreate

DEMO_PASSWORD = "LocalDemo-learning-2026!"


def add_user(session, email, name, role, password, tenant_id=None):
    email = email.lower()
    existing = session.scalar(select(User).where(User.email == email, User.tenant_id == tenant_id))
    if existing:
        if existing.role != role or existing.tenant_id != tenant_id:
            raise ValueError(f"Existing account conflicts with bootstrap identity: {email}")
        return existing
    user = User(
        email=email,
        name=name,
        role=role,
        tenant_id=tenant_id,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.flush()
    return user


def seed_demo(session, settings):
    if make_url(settings.database_url).host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Demo accounts may only be created on a loopback database")
    add_user(
        session, "superadmin@example.com", "Platform Super Admin", Role.SUPER_ADMIN, DEMO_PASSWORD
    )
    add_user(session, "admin@example.com", "Platform Admin", Role.ADMIN, DEMO_PASSWORD)
    add_user(session, "viewer@example.com", "Platform Viewer", Role.SUPER_VIEWER, DEMO_PASSWORD)
    for slug, name in (
        ("river-institute", "River Institute"),
        ("summit-institute", "Summit Institute"),
    ):
        tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            now = datetime.now(UTC)
            tenant = Tenant(
                name=name,
                slug=slug,
                created_at=now,
                trial_expires_at=now + timedelta(days=settings.trial_days),
            )
            session.add(tenant)
            session.flush()
        prefix = slug.split("-")[0]
        add_user(
            session,
            f"{prefix}.admin@example.com",
            f"{name} Admin",
            Role.TENANT_ADMIN,
            DEMO_PASSWORD,
            tenant.id,
        )
        learner = add_user(
            session,
            f"{prefix}.learner@example.com",
            f"{name} Learner",
            Role.TENANT_USER,
            DEMO_PASSWORD,
            tenant.id,
        )
        course = session.scalar(select(Course).where(Course.tenant_id == tenant.id))
        if course is None:
            course = Course(
                tenant_id=tenant.id,
                title="Introduction to Python",
                description="A short demonstration course.",
            )
            session.add(course)
            session.flush()
            session.add_all(
                [
                    Lesson(
                        tenant_id=tenant.id,
                        course_id=course.id,
                        title="Variables",
                        position=1,
                        content="A variable gives a name to a value. Example: count = 3.",
                    ),
                    Lesson(
                        tenant_id=tenant.id,
                        course_id=course.id,
                        title="Functions",
                        position=2,
                        content="A function groups reusable steps. Define one with def.",
                    ),
                ]
            )
            session.flush()
        if not session.scalar(
            select(Assignment.id).where(
                Assignment.tenant_id == tenant.id,
                Assignment.course_id == course.id,
                Assignment.user_id == learner.id,
            )
        ):
            session.add(Assignment(tenant_id=tenant.id, course_id=course.id, user_id=learner.id))
    session.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Initialize explicit local demo or super-admin accounts"
    )
    parser.add_argument("--demo", action="store_true", help="Create documented local demo accounts")
    parser.add_argument("--email", help="Super-admin email for non-demo bootstrap")
    args = parser.parse_args()
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as session:
            if args.demo:
                seed_demo(session, settings)
                print("Local demo initialized. Credentials are documented in backend/README.md.")
            else:
                if not args.email:
                    parser.error("Provide --email or explicitly choose --demo")
                data = PlatformUserCreate(
                    name="Platform Super Admin",
                    email=args.email,
                    role="super_admin",
                    password=getpass.getpass("Password: "),
                )
                add_user(session, str(data.email), data.name, data.role, data.password)
                session.commit()
                print("Super-admin account is ready; an existing account was left unchanged.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
