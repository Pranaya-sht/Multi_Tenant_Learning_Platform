from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Tenant


def as_utc(value: datetime) -> datetime:
    # SQLite test storage returns naive datetimes; production uses TIMESTAMPTZ.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def effective_status(tenant: Tenant, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if tenant.status == "expired" or as_utc(tenant.trial_expires_at) <= now:
        return "expired"
    return tenant.status


def expire_due_tenants(session: Session, now: datetime | None = None) -> int:
    """Atomic and repeatable: already expired tenants do not match the UPDATE."""
    result = session.execute(
        update(Tenant)
        .where(Tenant.trial_expires_at <= (now or datetime.now(UTC)), Tenant.status != "expired")
        .values(status="expired")
    )
    session.commit()
    return result.rowcount
