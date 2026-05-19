from datetime import datetime
from nuclia_e2e.settings import settings
from nuclia_e2e.tests.cloud_storage_sync import css_helpers
from nuclia_e2e.tests.cloud_storage_sync import nucliadb_helpers
from nuclia_e2e.tests.cloud_storage_sync import sharepoint_helpers as onedrive
from nuclia_e2e.tests.cloud_storage_sync.sharepoint_helpers import sanitize_slug
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

CHANGES_API_PROPAGATION_DELAY = 5  # seconds to wait for Microsoft Graph delta propagation
SEED_FILES_DIR = Path(__file__).parent / "seed_files"


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio_cooperative
async def test_sharepoint_sync_lifecycle(  # noqa: C901, PLR0912
    regional_api_config: ZoneConfig, kb_id: str, aiohttp_session: aiohttp.ClientSession
):
    """Full lifecycle: initial → create+update → delete+move-out → move-back → rename root."""
    run_id = uuid.uuid4().hex[:8]
    external_connection_id = settings.azure_external_connection_id

    # Derive auth headers and zone URL from fixtures
    global_config = regional_api_config.global_config
    assert global_config is not None, "global_config must be set on ZoneConfig"
    zone_url = f"https://{regional_api_config.zone_slug}.{global_config.base_domain}"
    auth_headers = {"Authorization": f"Bearer {global_config.permanent_account_owner_pat_token}"}

    folder_name = f"e2e_{regional_api_config.zone_slug}_{run_id}"
    dynamic_folder_name = f"dynamic_folder_{run_id}"
    dynamic_filename = "dynamic_file.txt"
    new_filename = "new_file.txt"

    folder_id: str | None = None
    dynamic_folder_id: str | None = None
    dynamic_file_id: str | None = None
    new_file_id: str | None = None
    config_id: str | None = None
    labelset_name = f"e2e_labelset_{run_id}"
    label_value = "synced"
    all_file_ids: list[str] = []
    root_item_id: str | None = None

    session = aiohttp_session
    try:
        # --- Setup: get OneDrive access token ---
        access_token = await onedrive.refresh_token(session)

        # --- Setup: get root drive item ID (needed for move operations) ---
        root_item_id = await onedrive.get_root_item_id(session, access_token)

        # --- Setup: create ephemeral test folder with initial files from seed_files/ ---
        logger.info("Setup: creating test folder '%s'", folder_name)
        folder_id = await onedrive.create_folder(session, access_token, root_item_id, folder_name)
        logger.info("Created test folder: %s", folder_id)

        uploaded_files = await onedrive.upload_local_tree(session, access_token, folder_id, SEED_FILES_DIR)
        # Separate excluded files (.ignore extension) from synced files
        excluded_file_ids = [fid for fid, rel in uploaded_files.items() if rel.endswith(".ignore")]
        synced_uploaded = {fid: rel for fid, rel in uploaded_files.items() if not rel.endswith(".ignore")}
        # file_id -> expected full path in OneDrive (only for synced files)
        expected_paths: dict[str, str] = {
            fid: f"/{folder_name}/{rel}" for fid, rel in synced_uploaded.items()
        }
        all_file_ids.extend(synced_uploaded.keys())
        logger.info("Created %d files (%d excluded by filter)", len(uploaded_files), len(excluded_file_ids))

        # --- Phase 1: Initial Sync ---
        logger.info("Phase 1: Creating dynamic folder with dynamic file and running initial sync")

        # Create a dynamic subfolder and place the dynamic file inside it
        dynamic_folder_id = await onedrive.create_folder(
            session, access_token, folder_id, dynamic_folder_name
        )
        logger.info("Created dynamic folder: %s", dynamic_folder_id)

        dynamic_file_id = await onedrive.create_file(
            session, access_token, dynamic_folder_id, dynamic_filename, "initial content"
        )
        all_file_ids.append(dynamic_file_id)
        expected_paths[dynamic_file_id] = f"/{folder_name}/{dynamic_folder_name}/{dynamic_filename}"
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
            name=f"e2e-sharepoint-{run_id}",
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
                session, zone_url, auth_headers, kb_id, sanitize_slug(file_id)
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
                session, zone_url, auth_headers, kb_id, sanitize_slug(file_id)
            )
            assert resource is None, f"Excluded file {file_id} should not exist in NucliaDB but was found"

        # Assert: job logs show created entries for all files (with correct extras)
        logs = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job_id)
        assert_logged_paths(logs, "Created file", {fid: expected_paths[fid] for fid in all_file_ids})

        logger.info("Phase 1 passed: %d resources created", len(all_file_ids))

        # Store the modification time of dynamic file for later comparison
        dynamic_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, sanitize_slug(dynamic_file_id)
        )
        assert dynamic_resource is not None
        initial_modified = dynamic_resource["modified"]

        # --- Phase 2: Incremental — Create + Update ---
        logger.info("Phase 2: Creating new file and updating dynamic file")

        new_file_id = await onedrive.create_file(
            session, access_token, folder_id, new_filename, "brand new file"
        )
        expected_paths[new_file_id] = f"/{folder_name}/{new_filename}"
        logger.info("Created new file: %s", new_file_id)

        await onedrive.update_file_content(
            session, access_token, dynamic_file_id, "updated content with new bytes"
        )
        logger.info("Updated dynamic file content")

        # Wait for delta API propagation
        await asyncio.sleep(CHANGES_API_PROPAGATION_DELAY)

        job2_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Assert: new file exists in NucliaDB with correct labels
        new_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, sanitize_slug(new_file_id)
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
            session, zone_url, auth_headers, kb_id, sanitize_slug(dynamic_file_id)
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

        # --- Phase 3: Incremental — Delete + Move Out ---
        logger.info("Phase 3: Deleting new file and moving dynamic folder outside sync root")

        await onedrive.delete_file(session, access_token, new_file_id)
        logger.info("Deleted file: %s", new_file_id)

        # Move the dynamic folder to OneDrive root (outside the sync root)
        await onedrive.move_file(session, access_token, dynamic_folder_id, root_item_id)
        logger.info("Moved dynamic folder to root (outside sync root)")

        # Wait for delta API propagation
        await asyncio.sleep(CHANGES_API_PROPAGATION_DELAY)

        job3_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Assert: deleted file no longer exists in NucliaDB
        deleted_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, sanitize_slug(new_file_id)
        )
        assert deleted_resource is None, f"Deleted file {new_file_id} still exists in NucliaDB"

        # Assert: dynamic file no longer exists (its folder moved outside sync root)
        moved_out_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, sanitize_slug(dynamic_file_id)
        )
        assert (
            moved_out_resource is None
        ), f"Dynamic file {dynamic_file_id} still exists after folder moved outside sync root"

        # Assert: job logs show 2 deletions
        logs3 = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job3_id)
        deleted_logs3 = [
            log
            for log in logs3
            if "Deleted file" in log.get("message", "")
            or "File was deleted or trashed" in log.get("message", "")
        ]
        assert len(deleted_logs3) == 2, f"Expected 2 delete logs, got {len(deleted_logs3)}"

        assert_logged_paths(
            logs3,
            "Deleted file",
            {
                new_file_id: expected_paths[new_file_id],
                dynamic_file_id: expected_paths[dynamic_file_id],
            },
        )

        # Assert: remaining seed file resources still exist
        remaining_ids = [fid for fid in all_file_ids if fid not in (new_file_id, dynamic_file_id)]
        for file_id in remaining_ids:
            resource = await nucliadb_helpers.get_resource_by_slug(
                session, zone_url, auth_headers, kb_id, sanitize_slug(file_id)
            )
            assert resource is not None, f"Resource {file_id} unexpectedly missing after delete sync"

        logger.info("Phase 3 passed: 2 deleted, remaining resources intact")

        # --- Phase 4: Move Back In ---
        logger.info("Phase 4: Moving dynamic folder back into sync root")

        await onedrive.move_file(session, access_token, dynamic_folder_id, folder_id)
        logger.info("Moved dynamic folder back into sync root")

        # Wait for delta API propagation
        await asyncio.sleep(CHANGES_API_PROPAGATION_DELAY)

        job4_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Assert: dynamic file re-created in NucliaDB with correct labels
        recreated_resource = await nucliadb_helpers.get_resource_by_slug(
            session, zone_url, auth_headers, kb_id, sanitize_slug(dynamic_file_id)
        )
        assert (
            recreated_resource is not None
        ), f"Dynamic file {dynamic_file_id} not re-created after moving folder back"
        recreated_classifications = recreated_resource.get("usermetadata", {}).get("classifications", [])
        assert any(
            c.get("labelset") == expected_label["labelset"] and c.get("label") == expected_label["label"]
            for c in recreated_classifications
        ), f"Re-created resource {dynamic_file_id} missing expected label, got {recreated_classifications}"

        # Assert: origin.path is correct
        origin_path = recreated_resource.get("origin", {}).get("path")
        assert (
            origin_path == expected_paths[dynamic_file_id]
        ), f"origin.path mismatch: expected {expected_paths[dynamic_file_id]}, got {origin_path}"

        # Assert: job logs show 1 created file
        logs4 = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job4_id)
        assert_logged_paths(logs4, "Created file", {dynamic_file_id: expected_paths[dynamic_file_id]})

        logger.info("Phase 4 passed: dynamic file re-created")

        # --- Phase 5: Rename Sync Root Folder ---
        renamed_folder_name = f"{folder_name}_renamed"
        logger.info("Phase 5: Renaming sync root folder to '%s'", renamed_folder_name)

        await onedrive.rename_file(session, access_token, folder_id, renamed_folder_name)
        logger.info("Renamed sync root folder")

        # Wait for delta API propagation
        await asyncio.sleep(CHANGES_API_PROPAGATION_DELAY)

        job5_id = await run_sync_and_wait(session, zone_url, auth_headers, kb_id, config_id)

        # Update expected paths with the new folder name prefix
        renamed_expected_paths: dict[str, str] = {
            fid: path.replace(f"/{folder_name}/", f"/{renamed_folder_name}/", 1)
            for fid, path in expected_paths.items()
        }

        # Assert: all remaining resources have updated origin.path
        active_file_ids = [fid for fid in all_file_ids if fid != new_file_id]
        for file_id in active_file_ids:
            resource = await nucliadb_helpers.get_resource_by_slug(
                session, zone_url, auth_headers, kb_id, sanitize_slug(file_id)
            )
            assert resource is not None, f"Resource {file_id} missing after rename sync"
            origin_path = resource.get("origin", {}).get("path")
            assert origin_path == renamed_expected_paths[file_id], (
                f"origin.path not updated for {file_id}: "
                f"expected {renamed_expected_paths[file_id]}, got {origin_path}"
            )

        # Assert: job logs show updated entries for all active files
        logs5 = await css_helpers.get_job_logs(session, zone_url, auth_headers, kb_id, job5_id)
        assert_logged_paths(
            logs5, "Updated file metadata", {fid: renamed_expected_paths[fid] for fid in active_file_ids}
        )

        logger.info("Phase 5 passed: all resources have updated origin.path")

    finally:
        # --- Cleanup (idempotent) ---
        logger.info("Cleanup: removing test artifacts")
        cleanup_token: str | None = None
        try:
            cleanup_token = await onedrive.refresh_token(session)
        except Exception:
            cleanup_token = None

        # Delete the entire test folder from OneDrive (recursively deletes all contents)
        if folder_id and cleanup_token:
            try:
                await onedrive.delete_file(session, cleanup_token, folder_id)
            except Exception as e:
                logger.warning("Failed to delete test folder: %s", e)

        # Delete the dynamic folder if it's still at root (outside the test folder)
        if dynamic_folder_id and cleanup_token:
            try:
                await onedrive.delete_file(session, cleanup_token, dynamic_folder_id)
            except Exception as e:
                logger.warning("Failed to delete dynamic folder: %s", e)

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
                    session, zone_url, auth_headers, kb_id, sanitize_slug(file_id)
                )
            except Exception as e:
                logger.warning("Failed to delete resource %s: %s", file_id, e)

        # Delete labelset
        try:
            await nucliadb_helpers.delete_labelset(session, zone_url, auth_headers, kb_id, labelset_name)
        except Exception as e:
            logger.warning("Failed to delete labelset: %s", e)
