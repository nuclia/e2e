"""Helpers for interacting with the Cloud Storage Sync (CSS) service."""

import aiohttp

JOB_POLL_INTERVAL = 5  # seconds between job status checks
JOB_POLL_TIMEOUT = 300  # max seconds to wait for a sync job to complete


async def create_sync_config(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    name: str,
    sync_root_path: str,
    external_connection_id: str,
    labels: list[dict[str, str]],
    file_filter: dict,
) -> dict:
    """Create a sync config. Returns the full SyncConfigOutput."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/sync_configs"
    payload: dict = {
        "name": name,
        "sync_root_path": sync_root_path,
        "external_connection_id": external_connection_id,
        "labels": labels,
        "file_filter": file_filter,
    }

    resp = await session.post(
        url,
        headers=auth_headers,
        json=payload,
    )
    resp.raise_for_status()
    return await resp.json()


async def delete_sync_config(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    config_id: str,
) -> None:
    """Delete a sync config. Ignores 404."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/sync_config/{config_id}"
    resp = await session.delete(url, headers=auth_headers)
    if resp.status != 404:
        resp.raise_for_status()


async def trigger_sync(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    config_id: str,
) -> dict:
    """Trigger a sync job. Returns the SyncJobOutput."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/sync_config/{config_id}/sync"
    resp = await session.post(url, headers=auth_headers)
    resp.raise_for_status()
    return await resp.json()


async def get_latest_job(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    config_id: str,
) -> dict | None:
    """Get the most recent sync job for a config."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/sync_config/{config_id}/jobs"
    resp = await session.get(url, headers=auth_headers, params={"limit": "1"})
    resp.raise_for_status()
    data = await resp.json()
    items = data.get("items", [])
    return items[0] if items else None


async def get_job_logs(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    job_id: str,
    level: str = "INFO",
) -> list[dict]:
    """Get all log entries for a job (paginated). Returns list of LogEntryOutput."""
    logs: list[dict] = []
    cursor = None
    url = f"{zone_url}/api/v1/kb/{kb_id}/sync_job/{job_id}/logs"
    while True:
        params: dict = {"level": level, "limit": "100"}
        if cursor is not None:
            params["cursor"] = str(cursor)
        resp = await session.get(url, headers=auth_headers, params=params)
        resp.raise_for_status()
        data = await resp.json()
        logs.extend(data.get("items", []))
        cursor = data.get("next_cursor")
        if cursor is None:
            break
    return logs
