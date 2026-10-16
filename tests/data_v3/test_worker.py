import asyncio
from datetime import datetime

import pytest

from skyview.data.v3 import worker


@pytest.mark.parametrize(
    "moment,delay",
    [
        ("2026-10-15T18:29:59+00:00", 6),
        ("2026-10-15T18:30:00+00:00", 21600),
        ("2026-10-15T12:00:00+00:00", 21600),
    ],
)
def test_rollover_follows_india_midnight(moment, delay):
    assert worker._rollover_delay(datetime.fromisoformat(moment)) == delay


@pytest.mark.asyncio
async def test_no_worker_in_legacy(monkeypatch):
    monkeypatch.setattr(worker, "_worker", None)
    monkeypatch.setattr(worker, "enabled", lambda: False)
    assert await worker.start_background_worker() is False


@pytest.mark.asyncio
async def test_single_worker_start_and_graceful_stop(monkeypatch):
    monkeypatch.setattr(worker, "_worker", None)
    monkeypatch.setattr(worker, "enabled", lambda: True)
    monkeypatch.setattr(worker, "mode", lambda: "v3_demo")
    monkeypatch.setattr(worker, "_lease", lambda: object())
    releases = []
    monkeypatch.setattr(worker, "_release", lambda lease: releases.append(lease))

    async def loop(self):
        await self.stop.wait()

    monkeypatch.setattr(worker.BackgroundWorker, "telemetry", loop)
    monkeypatch.setattr(worker.BackgroundWorker, "sources", loop)
    assert await worker.start_background_worker() is True
    assert await worker.start_background_worker() is False
    await worker.stop_background_worker()
    assert worker._worker is None and len(releases) == 1
    await worker.stop_background_worker()
    assert len(releases) == 1


@pytest.mark.asyncio
async def test_lease_owned_by_other_process(monkeypatch):
    monkeypatch.setattr(worker, "_worker", None)
    monkeypatch.setattr(worker, "enabled", lambda: True)
    monkeypatch.setattr(worker, "_lease", lambda: None)
    assert await worker.start_background_worker() is False
    assert worker._worker is None


@pytest.mark.asyncio
async def test_job_failure_is_reported_and_does_not_escape(monkeypatch):
    failures = []
    monkeypatch.setattr(
        worker,
        "_failure",
        lambda source, scope, exc: failures.append((source, scope, type(exc).__name__)),
    )

    def fail():
        raise TimeoutError("secret-sensitive error text")

    background = worker.BackgroundWorker(None)
    assert await background.job(fail, source="open_meteo", scope="public-grid") is None
    assert failures == [("open_meteo", "public-grid", "TimeoutError")]


@pytest.mark.asyncio
async def test_wait_wakes_immediately_on_shutdown():
    background = worker.BackgroundWorker(None)
    pending = asyncio.create_task(background.wait(3600))
    background.stop.set()
    await asyncio.wait_for(pending, timeout=0.2)


def test_weather_due_success_failure_and_history_cutoff():
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    healthy = {
        "status": "healthy",
        "checked_at": now,
        "source_valid_through": now.date() - timedelta(days=7),
    }
    assert worker._weather_due(None, False, now)
    assert not worker._weather_due(healthy, False, now)
    assert not worker._weather_due(healthy, True, now)
    assert worker._weather_due(
        {**healthy, "checked_at": now - timedelta(hours=7)}, False, now
    )
    assert worker._weather_due(
        {**healthy, "source_valid_through": now.date() - timedelta(days=8)}, True, now
    )
    outage = {**healthy, "status": "outage", "retry_after": now + timedelta(minutes=30)}
    assert not worker._weather_due(outage, False, now)
    assert worker._weather_due(
        {**outage, "retry_after": now - timedelta(seconds=1)}, False, now
    )


@pytest.mark.asyncio
async def test_empty_source_worker_later_activates_linked_grid(monkeypatch):
    for key in ["DATAGOV_API_KEY", "DATA_GOV_API_KEY", "OGD_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    background = worker.BackgroundWorker(None)
    selections = 0
    imported = []
    public_location = {"id": "public-fixture", "latitude": 28.5, "longitude": 77.25}

    async def job(func, *args, **kwargs):
        nonlocal selections
        if func is worker._weather_jobs:
            selections += 1
            return (
                []
                if selections == 1
                else [
                    (
                        public_location,
                        [("open_meteo", False, False, "public-fixture:forecast")],
                    )
                ]
            )
        if func is worker._weather:
            imported.append(args)
            background.stop.set()
            return {"accepted": 16}
        return None

    async def wait(seconds):
        await asyncio.sleep(0)

    monkeypatch.setattr(background, "job", job)
    monkeypatch.setattr(background, "wait_sources", wait)
    await background.sources()
    assert selections == 2
    assert imported == [(public_location, False, False)]


def test_revoked_weather_link_sends_no_request(monkeypatch):
    monkeypatch.setattr(worker, "_eligible_locations", list)

    def prohibited(*args, **kwargs):
        raise AssertionError("outbound request after consent revocation")

    monkeypatch.setattr(worker, "fetch_weather", prohibited)
    assert (
        worker._weather({"id": "public-fixture", "latitude": 28.5, "longitude": 77.25})[
            "status"
        ]
        == "consent_revoked_or_unlinked"
    )


@pytest.mark.asyncio
async def test_weather_wakeup_does_not_wait_for_poll_timeout():
    background = worker.BackgroundWorker(None)
    pending = asyncio.create_task(background.wait_sources(3600))
    background.wake.set()
    await asyncio.wait_for(pending, timeout=0.2)
    assert not background.wake.is_set()


def test_bounded_batch_rotates_past_fresh_and_backoff_grids(monkeypatch):
    from contextlib import contextmanager
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    locations = [
        {"id": f"public-{i}", "latitude": 28.5, "longitude": 77.25} for i in range(5)
    ]
    health = []
    for number in (0, 1):
        for provider, product in [
            ("open_meteo", "forecast"),
            ("open_meteo", "history"),
            ("nasa_power", "history"),
        ]:
            health.append(
                {
                    "code": provider,
                    "scope_key": f"public-{number}:{product}",
                    "checked_at": now,
                    "retry_after": None if number == 0 else now + timedelta(minutes=30),
                    "status": "healthy" if number == 0 else "outage",
                    "source_valid_through": now.date() - timedelta(days=7),
                }
            )

    @contextmanager
    def db(**kwargs):
        yield object()

    class Result:
        def mappings(self):
            return self

        def all(self):
            return health

    monkeypatch.setattr(worker, "_eligible_locations", lambda: locations)
    monkeypatch.setattr(worker, "connection", db)
    monkeypatch.setattr(worker, "execute", lambda *args, **kwargs: Result())
    jobs = worker._weather_jobs(limit=2, now=now)
    assert [location["id"] for location, _ in jobs] == ["public-2", "public-3"]
    assert len(jobs[0][1]) == 3


@pytest.mark.asyncio
async def test_market_loop_respects_persisted_due_time(monkeypatch):
    monkeypatch.setenv("OGD_API_KEY", "private-test-key")
    background = worker.BackgroundWorker(None)
    calls = []

    async def job(func, *args, **kwargs):
        calls.append(func)
        if func is worker._mandi_due:
            return False
        raise AssertionError("Backoff must prevent an outbound market request")

    async def wait(_):
        background.stop.set()

    monkeypatch.setattr(background, "job", job)
    monkeypatch.setattr(background, "wait", wait)
    await background.markets()
    assert calls == [worker._mandi_due]
