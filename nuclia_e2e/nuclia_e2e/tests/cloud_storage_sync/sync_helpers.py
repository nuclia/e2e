"""Shared helpers for cloud storage sync tests"""

from nuclia_e2e.tests.cloud_storage_sync import css_helpers
from nuclia_e2e.utils import wait_for

import aiohttp
import logging

logger = logging.getLogger(__name__)


async def run_sync_and_wait(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict,
    kb_id: str,
    config_id: str,
) -> str:
    """Trigger a sync job and block until it completes. Returns the job_id."""
    job = await css_helpers.trigger_sync(session, zone_url, auth_headers, kb_id, config_id)
    job_id = job["id"]
    logger.info("Triggered sync job: %s", job_id)

    async def completed():
        latest = await css_helpers.get_latest_job(session, zone_url, auth_headers, kb_id, config_id)
        if latest and latest["id"] == job_id:
            status = latest["status"]
            if status == "failed":
                raise AssertionError(f"Sync job {job_id} failed")
            return status == "completed", latest
        return False, None

    success, _ = await wait_for(
        completed,
        max_wait=css_helpers.JOB_POLL_TIMEOUT,
        interval=css_helpers.JOB_POLL_INTERVAL,
    )
    assert success, f"Sync job {job_id} did not complete within {css_helpers.JOB_POLL_TIMEOUT}s"
    return job_id


def log_paths_by_file_id(logs: list[dict], message_substring: str) -> dict[str, str]:
    """Build a {file_id: file_path} mapping from logs whose message contains the substring."""
    return {
        log.get("extra", {}).get("file_id"): log.get("extra", {}).get("file_path")
        for log in logs
        if message_substring in log.get("message", "")
    }


def assert_logged_paths(
    logs: list[dict],
    message_substring: str,
    expected: dict[str, str],
) -> None:
    """Assert that each (file_id -> file_path) in `expected` appears in matching log entries."""
    actual = log_paths_by_file_id(logs, message_substring)
    assert len(actual) == len(
        expected
    ), f"Expected {len(expected)} '{message_substring}' logs, got {len(actual)}"
    for file_id, file_path in expected.items():
        assert file_id in actual, f"file_id {file_id} not found in '{message_substring}' logs"
        assert (
            actual[file_id] == file_path
        ), f"file_path mismatch for {file_id}: expected {file_path}, got {actual[file_id]}"
