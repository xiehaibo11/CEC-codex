"""Scheduler options must reach APScheduler, not the task function."""

from __future__ import annotations

from services.scheduler import TaskScheduler


class _FakeScheduler:
    def __init__(self):
        self.calls = []
        self.running = True

    def add_job(self, **kwargs):
        self.calls.append(kwargs)


def test_interval_task_accepts_ap_scheduler_job_options():
    scheduler = TaskScheduler()
    scheduler._started = True
    scheduler.scheduler = _FakeScheduler()

    def task(**kwargs):
        return kwargs

    scheduler.add_interval_task(
        task_func=task,
        interval_seconds=1,
        task_id="bar-boundary",
        job_options={"max_instances": 1, "coalesce": True, "misfire_grace_time": 2},
        source="paper",
    )

    job = scheduler.scheduler.calls[0]
    assert job["max_instances"] == 1
    assert job["coalesce"] is True
    assert job["misfire_grace_time"] == 2
    assert job["kwargs"] == {"source": "paper"}
