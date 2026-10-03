"""Run the expiration scheduler and RQ worker from one local terminal."""

import logging
from threading import Event, Thread

from app import scheduler, worker


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    stop_event = Event()
    scheduler_thread = Thread(
        target=scheduler.run,
        args=(stop_event,),
        name="expiration-scheduler",
        daemon=True,
    )
    scheduler_thread.start()
    try:
        worker.main()
    finally:
        stop_event.set()
        scheduler_thread.join(timeout=7)


if __name__ == "__main__":
    main()
