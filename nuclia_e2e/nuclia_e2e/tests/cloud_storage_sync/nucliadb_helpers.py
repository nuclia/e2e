"""Helpers for interacting with NucliaDB resources."""

import aiohttp


async def get_resource_by_slug(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    slug: str,
) -> dict | None:
    """Get a resource by slug. Returns None if 404."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/slug/{slug}"
    resp = await session.get(
        url,
        headers=auth_headers,
        params={"show": ["basic", "origin"]},
    )
    if resp.status == 404:
        return None
    resp.raise_for_status()
    return await resp.json()


async def delete_resource_by_slug(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    slug: str,
) -> None:
    """Delete a resource by slug. Ignores 404."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/slug/{slug}"
    resp = await session.delete(url, headers=auth_headers)
    if resp.status != 404:
        resp.raise_for_status()


async def create_labelset(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    labelset_name: str,
    labels: list[str],
) -> None:
    """Create a labelset. Ignores 422 (already exists)."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/labelset/{labelset_name}"
    resp = await session.post(
        url,
        headers=auth_headers,
        json={
            "title": labelset_name,
            "color": "#E6E6F9",
            "multiple": True,
            "kind": ["RESOURCES"],
            "labels": [{"title": label} for label in labels],
        },
    )
    if resp.status != 422:
        resp.raise_for_status()


async def delete_labelset(
    session: aiohttp.ClientSession,
    zone_url: str,
    auth_headers: dict[str, str],
    kb_id: str,
    labelset_name: str,
) -> None:
    """Delete a labelset. Ignores 404."""
    url = f"{zone_url}/api/v1/kb/{kb_id}/labelset/{labelset_name}"
    resp = await session.delete(url, headers=auth_headers)
    if resp.status != 404:
        resp.raise_for_status()
