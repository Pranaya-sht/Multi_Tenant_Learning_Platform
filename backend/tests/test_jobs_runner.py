from threading import Event
from unittest.mock import MagicMock

from app import background, jobs, scheduler


def test_scheduler_enqueues_once_and_closes_connection_on_stop(monkeypatch, settings):
    assert callable(jobs.expire_tenants)
    stop_event = Event()
    connection = MagicMock()
    queue = MagicMock()
    queue.enqueue.side_effect = lambda *args, **kwargs: stop_event.set()
    monkeypatch.setattr(scheduler, "create_queue_connection", lambda _: connection)
    monkeypatch.setattr(scheduler, "create_queue", lambda *_: queue)

    scheduler.run(stop_event, settings)

    queue.enqueue.assert_called_once_with(
        "app.jobs.expire_tenants", job_timeout=120, result_ttl=300
    )
    connection.close.assert_called_once()


def test_expiration_job_disposes_its_database_engine(monkeypatch, settings):
    engine = MagicMock()
    session = MagicMock()
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    monkeypatch.setattr(jobs, "Settings", lambda: settings)
    monkeypatch.setattr(jobs, "create_engine", lambda _: engine)
    monkeypatch.setattr(jobs, "Session", lambda _: session_context)
    sweep = MagicMock(return_value=3)
    monkeypatch.setattr(jobs, "expire_due_tenants", sweep)

    assert jobs.expire_tenants() == 3
    sweep.assert_called_once_with(session)
    engine.dispose.assert_called_once()


def test_combined_runner_stops_scheduler_when_worker_exits(monkeypatch):
    started = Event()
    stopped = Event()

    def run_scheduler(stop_event):
        started.set()
        stop_event.wait(2)
        stopped.set()

    def run_worker():
        assert started.wait(2)

    monkeypatch.setattr(background.scheduler, "run", run_scheduler)
    monkeypatch.setattr(background.worker, "main", run_worker)

    background.main()

    assert stopped.is_set()
