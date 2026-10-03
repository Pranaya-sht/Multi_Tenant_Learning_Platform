import os

from redis import Redis
from rq import Queue, SimpleWorker, Worker
from rq.serializers import JSONSerializer
from rq.worker import BaseWorker

from app.core.config import Settings
from app.infrastructure.redis import create_queue, create_queue_connection


def create_worker(queue: Queue, connection: Redis) -> BaseWorker:
    # Windows has no fork/wait4. SimpleWorker uses RQ's platform-aware timeout.
    worker_class = SimpleWorker if os.name == "nt" else Worker
    return worker_class([queue], connection=connection, serializer=JSONSerializer)


def main() -> None:
    settings = Settings()
    connection = create_queue_connection(settings, for_worker=True)
    try:
        queue = create_queue(settings, connection)
        worker = create_worker(queue, connection)
        worker.work()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
