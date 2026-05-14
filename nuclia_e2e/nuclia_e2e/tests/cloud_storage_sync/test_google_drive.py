"""
E2E test: Google Drive Sync Lifecycle

Validates the full sync lifecycle (initial → incremental create+update → incremental delete)
against a deployed cloud_storage_sync service, a real Google Drive folder, and NucliaDB.

Prerequisites (not managed by the test):
- Pre-existing KB (resolved via regional_api_config fixture)
- Pre-existing external_connection (GOOGLE_OAUTH) in that KB
- Google Drive OAuth credentials as env vars
"""

from datetime import datetime
from nuclia_e2e.settings import settings
from nuclia_e2e.tests.cloud_storage_sync import css_helpers
from nuclia_e2e.tests.cloud_storage_sync import google_drive_helpers as gdrive
from nuclia_e2e.tests.cloud_storage_sync import nucliadb_helpers
from nuclia_e2e.tests.cloud_storage_sync.sync_helpers import assert_logged_paths
from nuclia_e2e.tests.cloud_storage_sync.sync_helpers import run_sync_and_wait
from nuclia_e2e.tests.conftest import ZoneConfig
from pathlib import Path

import aiohttp
import asyncio
import logging
import pytest
import uuid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHANGES_API_PROPAGATION_DELAY = 10  # seconds to wait for Google Drive Changes API
SEED_FILES_DIR = Path(__file__).parent / "seed_files"


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio_cooperative
async def test_google_drive_sync_lifecycle(  # noqa: C901
    regional_api_config: ZoneConfig, kb_id: str, aiohttp_session: aiohttp.ClientSession
):
    """Full lifecycle: initial sync → incremental create+update → incremental delete."""
    run_id = uuid.uuid4().hex[:8]
    external_connection_id = settings.external_connection_id

    # Derive auth headers and zone URL from fixtures
    global_config = regional_api_config.global_config
    assert global_config is not None, "global_config must be set on ZoneConfig"
    zone_url = f"https://{regional_api_config.zone_slug}.{global_config.base_domain}"
    auth_headers = {"Authorization": f"Bearer {global_config.permanent_account_owner_pat_token}"}

    folder_name = f"e2e_{regional_api_config.zone_slug}_{run_id}"
    dynamic_filename = "dynamic_file.txt"
    new_filename = "new_file.txt"

    folder_id: str | None = None
    dynamic_file_id: str | None = None
    new_file_id: str | None = None
    config_id: str | None = None
    labelset_name = f"e2e_labelset_{run_id}"
    label_value = "synced"
    all_file_ids: list[str] = []

    session = aiohttp_session
    try:
        # --- Setup: get Google Drive access token ---
        access_token = await gdrive.refresh_token(session)

        # --- Setup: create ephemeral test folder with initial files from seed_files/ ---
        logger.info("Setup: creating test folder '%s'", folder_name)
        folder_id = await gdrive.create_folder(session, access_token, "root", folder_name)
        logger.info("Created test folder: %s", folder_id)

        uploaded_files = await gdrive.upload_local_tree(session, access_token, folder_id, SEED_FILES_DIR)
        # Separate excluded files (.ignore extension) from synced files
        excluded_file_ids = [fid for fid, rel in uploaded_files.items() if rel.endswith(".ignore")]
        synced_uploaded = {fid: rel for fid, rel in uploaded_files.items() if not rel.endswith(".ignore")}
        # file_id -> expected full path in Drive (only for synced files)
        expected_paths: dict[str, str] = {
            fid: f"/{folder_name}/{rel}" for fid, rel in synced_uploaded.items()
        }
        all_file_ids.extend(synced_uploaded.keys())
        logger.info("Created %d files (%d excluded by filter)", len(uploaded_files), len(excluded_file_ids))

        # --- Phase 1: Initial Sync ---
        logger.info("Phase 1: Creating dynamic file and running initial sync")

        dynamic_file_id = await gdrive.create_file(
            session, access_token, folder_id, dynamic_filename, "initial content"
        )
        all_file_ids.append(dynamic_file_id)
        expected_paths[dynamic_file_id] = f"/{folder_name}/{dynamic_filename}"
        logger.info("Created dynamic file: %s", dynamic_file_id)

        # Create labelset for tagging synced resources
        await nucliadb_helpers.create_labelset(
            session, zone_url, auth_headers, kb_id, labelset_name, [label_value]
        )
        logger.info("Created labelset: %s", labelset_name)

        # Create sync config
        sync_config = await css_helpers.create_sync_config(
            session,
            zone_url,
            auth_headers,
            kb_id,
            name=f"e2e-gdrive-{run_id}",
            sync_root_path=folder_name,
            external_connection_id=external_connection_id,
            labels=[{"labelset": labelset_name, "label": label_value}],
            file_filter={
                "mode": "exclude",
                "extensions": ["ignore"],
                "glob_patterns": None,
            },
        )
        config_id = sync_config["id"]
        assert config_id is not None
        logger.info("Created sync config: %s", config_id)

        job_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Assert: all files exist as resources in NucliaDB with correct labels
        expected_label = {"labelset": labelset_name, "label": label_value}
        for file_id in all_file_ids:
            resource = await nucliadb_helpers.get_resource_by_slug(
                session, zone_url, auth_headers, kb_id, file_id
            )
            assert (
                resource is not None
            ), f"Resource with slug {file_id} not found in NucliaDB after initial sync"
            classifications = resource.get("usermetadata", {}).get("classifications", [])
            assert any(
                c.get("labelset") == expected_label["labelset"] and c.get("label") == expected_label["label"]
                for c in classifications
            ), f"Resource {file_id} missing expected label {expected_label}, got {classifications}"

        # Assert: excluded files (.ignore) were NOT synced to NucliaDB
        for file_id in excluded_file_ids:
            resource = await nucliadb_helpers.get_resource_by_slug(
                session, zone_url, auth_headers, kb_id, file_id
            )
            assert resource is None, f"Excluded file {file_id} should not exist in NucliaDB but was found"

        # Assert: job logs show created entries for all files (with correct extras)
        logs = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job_id)
        assert_logged_paths(logs, "Created file", {fid: expected_paths[fid] for fid in all_file_ids})

        logger.info("Phase 1 passed: %d resources created", len(all_file_ids))

        # Store the modification time of dynamic file for later comparison
        dynamic_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, dynamic_file_id
        )
        assert dynamic_resource is not None
        initial_modified = dynamic_resource["modified"]

        # --- Phase 2: Incremental — Create + Update ---
        logger.info("Phase 2: Creating new file and updating dynamic file")

        new_file_id = await gdrive.create_file(
            session, access_token, folder_id, new_filename, "brand new file"
        )
        expected_paths[new_file_id] = f"/{folder_name}/{new_filename}"
        logger.info("Created new file: %s", new_file_id)

        await gdrive.update_file_content(
            session, access_token, dynamic_file_id, "updated content with new bytes"
        )
        logger.info("Updated dynamic file content")

        # Wait for Changes API propagation
        await asyncio.sleep(CHANGES_API_PROPAGATION_DELAY)

        job2_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Assert: new file exists in NucliaDB with correct labels
        new_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, new_file_id
        )
        assert (
            new_resource is not None
        ), f"New file {new_file_id} not found in NucliaDB after incremental sync"
        new_classifications = new_resource.get("usermetadata", {}).get("classifications", [])
        assert any(
            c.get("labelset") == expected_label["labelset"] and c.get("label") == expected_label["label"]
            for c in new_classifications
        ), f"New resource {new_file_id} missing expected label, got {new_classifications}"

        # Assert: dynamic file was updated (modification time changed)
        updated_dynamic = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, dynamic_file_id
        )
        assert updated_dynamic is not None
        updated_modified = datetime.fromisoformat(updated_dynamic["modified"])
        initial_modified_dt = datetime.fromisoformat(initial_modified)
        assert (
            updated_modified > initial_modified_dt
        ), f"Resource was not updated: modified {updated_dynamic['modified']} is not after {initial_modified}"

        # Assert: job logs show 1 created + 1 updated, with exact extras
        logs2 = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job2_id)
        assert_logged_paths(logs2, "Created file", {new_file_id: expected_paths[new_file_id]})
        assert_logged_paths(logs2, "Updated file", {dynamic_file_id: expected_paths[dynamic_file_id]})

        logger.info("Phase 2 passed: 1 created + 1 updated")

        # Add new file to tracked IDs
        all_file_ids.append(new_file_id)

        # --- Phase 3: Incremental — Delete ---
        logger.info("Phase 3: Trashing new file")

        await gdrive.trash_file(session, access_token, new_file_id)
        logger.info("Trashed file: %s", new_file_id)

        # Wait for Changes API propagation
        await asyncio.sleep(CHANGES_API_PROPAGATION_DELAY)

        job3_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Assert: trashed file no longer exists in NucliaDB
        deleted_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, new_file_id
        )
        assert deleted_resource is None, f"Trashed file {new_file_id} still exists in NucliaDB"

        # Assert: job logs show deletion
        logs3 = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job3_id)
        deleted_logs3 = [
            log
            for log in logs3
            if "Deleted file" in log.get("message", "")
            or "File was deleted or trashed" in log.get("message", "")
        ]
        assert len(deleted_logs3) == 1, f"Expected 1 delete log, got {len(deleted_logs3)}"

        assert_logged_paths(logs3, "Deleted file", {new_file_id: expected_paths[new_file_id]})

        # Assert: remaining resources still exist (4 fixed + dynamic)
        remaining_ids = [fid for fid in all_file_ids if fid != new_file_id]
        for file_id in remaining_ids:
            resource = await nucliadb_helpers.get_resource_by_slug(
                session, zone_url, auth_headers, kb_id, file_id
            )
            assert resource is not None, f"Resource {file_id} unexpectedly missing after delete sync"

        logger.info("Phase 3 passed: 1 deleted, remaining resources intact")

    finally:
        # --- Phase 4: Cleanup (idempotent) ---
        logger.info("Cleanup: removing test artifacts")
        cleanup_token: str | None = None
        try:
            cleanup_token = await gdrive.refresh_token(session)
        except Exception:
            cleanup_token = None

        # Delete the entire test folder from Drive (recursively deletes all contents)
        if folder_id and cleanup_token:
            try:
                await gdrive.delete_file(session, cleanup_token, folder_id)
            except Exception as e:
                logger.warning("Failed to delete test folder: %s", e)

        # Delete sync config
        if config_id:
            try:
                await css_helpers.delete_sync_config(session, zone_url, auth_headers, kb_id, config_id)
            except Exception as e:
                logger.warning("Failed to delete sync config: %s", e)

        # Delete all synced resources from NucliaDB
        for file_id in all_file_ids:
            try:
                await nucliadb_helpers.delete_resource_by_slug(
                    session, zone_url, auth_headers, kb_id, file_id
                )
            except Exception as e:
                logger.warning("Failed to delete resource %s: %s", file_id, e)

        # Delete labelset
        try:
            await nucliadb_helpers.delete_labelset(session, zone_url, auth_headers, kb_id, labelset_name)
        except Exception as e:
            logger.warning("Failed to delete labelset: %s", e)
