"""Helpers for interacting with the Google Drive API."""

from nuclia_e2e.settings import settings
from pathlib import Path

import aiohttp
import json


async def refresh_token(session: aiohttp.ClientSession) -> str:
    """Obtain a fresh access token using the refresh token."""
    resp = await session.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.google_drive_client_id,
            "client_secret": settings.google_drive_client_secret,
            "refresh_token": settings.google_drive_refresh_token,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["access_token"]


async def create_folder(
    session: aiohttp.ClientSession,
    access_token: str,
    parent_folder_id: str,
    folder_name: str,
) -> str:
    """Create a folder in Google Drive. Returns the folder ID."""
    resp = await session.post(
        "https://www.googleapis.com/drive/v3/files?fields=id",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        },
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["id"]


async def create_file(
    session: aiohttp.ClientSession,
    access_token: str,
    folder_id: str,
    filename: str,
    content: str,
) -> str:
    """Create a text file in Google Drive. Returns the file ID."""
    metadata = {"name": filename, "parents": [folder_id]}
    boundary = "e2e_boundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/plain\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--"
    )
    resp = await session.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        data=body.encode(),
    )
    resp.raise_for_status()
    data = await resp.json()
    return data["id"]


async def update_file_content(
    session: aiohttp.ClientSession,
    access_token: str,
    file_id: str,
    new_content: str,
) -> None:
    """Update the content of an existing Google Drive file."""
    resp = await session.patch(
        f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/plain",
        },
        data=new_content.encode(),
    )
    resp.raise_for_status()


async def trash_file(
    session: aiohttp.ClientSession,
    access_token: str,
    file_id: str,
) -> None:
    """Trash a file in Google Drive."""
    resp = await session.patch(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"trashed": True},
    )
    resp.raise_for_status()


async def delete_file(
    session: aiohttp.ClientSession,
    access_token: str,
    file_id: str,
) -> None:
    """Permanently delete a file from Google Drive. Ignores 404."""
    resp = await session.delete(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status != 404:
        resp.raise_for_status()


async def upload_local_tree(
    session: aiohttp.ClientSession,
    access_token: str,
    parent_folder_id: str,
    local_dir: Path,
    _prefix: str = "",
) -> dict[str, str]:
    """Recursively upload a local directory tree to Google Drive.

    Returns a dict mapping file_id -> relative path (e.g. "subfolder/readme.md").
    """
    files: dict[str, str] = {}
    for entry in sorted(local_dir.iterdir()):
        rel_path = f"{_prefix}{entry.name}"
        if entry.is_dir():
            subfolder_id = await create_folder(session, access_token, parent_folder_id, entry.name)
            sub_files = await upload_local_tree(
                session, access_token, subfolder_id, entry, _prefix=f"{rel_path}/"
            )
            files.update(sub_files)
        else:
            content = entry.read_text()
            fid = await create_file(session, access_token, parent_folder_id, entry.name, content)
            files[fid] = rel_path
    return files


async def list_files_in_folder(
    session: aiohttp.ClientSession,
    access_token: str,
    folder_id: str,
) -> list[dict]:
    """List all non-trashed files (recursively) under a folder."""
    files: list[dict] = []
    page_token = None
    while True:
        params: dict = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType)",
            "pageSize": "100",
        }
        if page_token:
            params["pageToken"] = page_token
        resp = await session.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        resp.raise_for_status()
        data = await resp.json()
        for f in data.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                sub_files = await list_files_in_folder(session, access_token, f["id"])
                files.extend(sub_files)
            else:
                files.append(f)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return files
