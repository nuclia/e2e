"""Helpers for interacting with OneDrive via the Microsoft Graph API."""

from nuclia_e2e.settings import settings
from pathlib import Path

import aiohttp
import re

# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

# Valid slug pattern: letters, numbers, underscores, colons, and dashes
_INVALID_SLUG_CHARS = re.compile(r"[^a-zA-Z0-9:_-]")


def sanitize_slug(value: str) -> str:
    """Sanitize a string to be used as a slug.

    Replaces any characters that are not letters, numbers, underscores,
    colons, or dashes with dashes.
    """
    return _INVALID_SLUG_CHARS.sub("-", value)


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def refresh_token(session: aiohttp.ClientSession) -> str:
    """Obtain a fresh access token using the refresh token."""
    resp = await session.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "client_id": settings.azure_client_id,
            "client_secret": settings.azure_client_secret,
            "refresh_token": settings.azure_refresh_token,
            "grant_type": "refresh_token",
            "scope": "https://graph.microsoft.com/.default offline_access",
        },
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["access_token"]


async def get_root_item_id(session: aiohttp.ClientSession, access_token: str) -> str:
    """Get the root drive item ID for the authenticated user's OneDrive."""
    resp = await session.get(
        f"{GRAPH_BASE}/me/drive/root",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["id"]


async def create_folder(
    session: aiohttp.ClientSession,
    access_token: str,
    parent_item_id: str,
    folder_name: str,
) -> str:
    """Create a folder in OneDrive. Returns the item ID."""
    resp = await session.post(
        f"{GRAPH_BASE}/me/drive/items/{parent_item_id}/children",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        },
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["id"]


async def create_file(
    session: aiohttp.ClientSession,
    access_token: str,
    parent_item_id: str,
    filename: str,
    content: str,
) -> str:
    """Create a text file in OneDrive. Returns the item ID."""
    resp = await session.put(
        f"{GRAPH_BASE}/me/drive/items/{parent_item_id}:/{filename}:/content",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/plain",
        },
        data=content.encode(),
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["id"]


async def update_file_content(
    session: aiohttp.ClientSession,
    access_token: str,
    item_id: str,
    new_content: str,
) -> None:
    """Update the content of an existing OneDrive file."""
    resp = await session.put(
        f"{GRAPH_BASE}/me/drive/items/{item_id}/content",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/plain",
        },
        data=new_content.encode(),
    )
    resp.raise_for_status()


async def move_file(
    session: aiohttp.ClientSession,
    access_token: str,
    item_id: str,
    new_parent_id: str,
) -> None:
    """Move a file or folder to a new parent in OneDrive."""
    resp = await session.patch(
        f"{GRAPH_BASE}/me/drive/items/{item_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"parentReference": {"id": new_parent_id}},
    )
    resp.raise_for_status()


async def rename_file(
    session: aiohttp.ClientSession,
    access_token: str,
    item_id: str,
    new_name: str,
) -> None:
    """Rename a file or folder in OneDrive."""
    resp = await session.patch(
        f"{GRAPH_BASE}/me/drive/items/{item_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"name": new_name},
    )
    resp.raise_for_status()


async def delete_file(
    session: aiohttp.ClientSession,
    access_token: str,
    item_id: str,
) -> None:
    """Delete (recycle) a file or folder in OneDrive. Ignores 404."""
    resp = await session.delete(
        f"{GRAPH_BASE}/me/drive/items/{item_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status != 404:
        resp.raise_for_status()


async def upload_local_tree(
    session: aiohttp.ClientSession,
    access_token: str,
    parent_item_id: str,
    local_dir: Path,
    _prefix: str = "",
    content_suffix: str = "",
) -> dict[str, str]:
    """Recursively upload a local directory tree to OneDrive.

    Returns a dict mapping item_id -> relative path (e.g. "subfolder/readme.md").
    """
    files: dict[str, str] = {}
    for entry in sorted(local_dir.iterdir()):
        rel_path = f"{_prefix}{entry.name}"
        if entry.is_dir():
            subfolder_id = await create_folder(session, access_token, parent_item_id, entry.name)
            sub_files = await upload_local_tree(
                session, access_token, subfolder_id, entry, _prefix=f"{rel_path}/",
                content_suffix=content_suffix,
            )
            files.update(sub_files)
        else:
            content = entry.read_text()
            if content_suffix:
                content = f"{content}\n{content_suffix}"
            item_id = await create_file(session, access_token, parent_item_id, entry.name, content)
            files[item_id] = rel_path
    return files
