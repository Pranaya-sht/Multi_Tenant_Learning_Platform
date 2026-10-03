"""RQ job targets. Keep importable by name for queued work."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.tenants import expire_due_tenants


def expire_tenants() -> int:
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as session:
            return expire_due_tenants(session)
    finally:
        engine.dispose()
