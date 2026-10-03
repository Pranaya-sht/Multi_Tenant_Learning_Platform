import logging
from threading import Event

from redis.exceptions import RedisError

from app.core.config import Settings
from app.infrastructure.redis import create_queue, create_queue_connection

logger = logging.getLogger(__name__)


def run(stop_event: Event, settings: Settings | None = None) -> None:
    settings = settings or Settings()
    connection = create_queue_connection(settings)
    queue = create_queue(settings, connection)
    try:
        while not stop_event.is_set():
            try:
                queue.enqueue("app.jobs.expire_tenants", job_timeout=120, result_ttl=300)
                logger.info("Queued tenant expiration sweep")
            except RedisError:
                logger.warning("Redis unavailable; will retry the expiration sweep")
            stop_event.wait(settings.expiration_interval_seconds)
    finally:
        connection.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        run(Event())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
