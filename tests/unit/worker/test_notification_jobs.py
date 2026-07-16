import asyncio

from apps.worker.jobs import (
    diff_snapshot_job,
    forecast_recompute_job,
    ingest_snapshot_job,
    notify_users_job,
)
from apps.worker.main import WorkerSettings


def test_notification_jobs_skip_missing_payload_and_chain_snapshots() -> None:
    assert asyncio.run(ingest_snapshot_job({}))["status"] == "skipped"
    assert asyncio.run(diff_snapshot_job({}, "synthetic"))["status"] == "queued"
    assert asyncio.run(forecast_recompute_job({}, "synthetic"))["status"] == "queued"
    assert asyncio.run(notify_users_job({}, "synthetic"))["status"] == "skipped"


def test_worker_registers_separate_pipeline_jobs() -> None:
    names = {function.__name__ for function in WorkerSettings.functions}
    assert {
        "ingest_snapshot_job",
        "ingest_itmo_batch_job",
        "diff_snapshot_job",
        "forecast_recompute_job",
        "notify_users_job",
    } <= names
    assert WorkerSettings.max_tries == 3
