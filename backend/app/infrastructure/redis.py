from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

from app.core.config import Settings


def create_cache(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_cache_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def create_queue_connection(settings: Settings, *, for_worker: bool = False) -> Redis:
    return Redis.from_url(
        settings.redis_queue_url,
        socket_connect_timeout=2,
        socket_timeout=None if for_worker else 5,
    )


def create_queue(settings: Settings, connection: Redis) -> Queue:
    return Queue(settings.queue_name, connection=connection, serializer=JSONSerializer)
