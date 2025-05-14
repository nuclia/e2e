from nuclia import sdk
from nuclia.data import get_auth
from nuclia.sdk.kbs import AsyncNucliaKBS
from nuclia.sdk.search import AsyncNucliaSearch
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import get_async_kb_ndb_client
from nuclia_e2e.utils import wait_for, get_kbid_from_slug
from nuclia_models.accounts.backups import BackupCreate
from nuclia_models.accounts.backups import BackupRestore


import pytest
from typing import Callable

Logger = Callable[[str], None]

@pytest.mark.asyncio_cooperative
async def test_kb_backup(request: pytest.FixtureRequest, regional_api_config: ZoneConfig):
    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    account_slug = regional_api_config.global_config.permanent_account_slug
    sdk.NucliaAccounts().default(account_slug)

    # Create Backup
    backup_create = await sdk.AsyncNucliaBackup().create(backup=BackupCreate(kb_id=kb_id), zone=zone)

    # Wait till backup is finished
    async def check_backup_finished() -> bool:
        backups = await sdk.AsyncNucliaBackup().list(zone=zone)
        backup_list = [b for b in backups if b.id == backup_create.id]
        assert len(backup_list) == 1
        backup_object = backup_list[0]
        return backup_object.finished_at is not None, backup_object

    await wait_for(condition=check_backup_finished, max_wait=180, interval=10)

    new_kb_slug = f"{regional_api_config.test_kb_slug}-test_kb_backup"

    # Make sure the kb used for this test is deleted, as the slug is reused:
    old_kbid = await get_kbid_from_slug(regional_api_config.zone_slug, new_kb_slug)
    if old_kbid is not None:
        await AsyncNucliaKBS().delete(zone=regional_api_config.zone_slug, id=old_kbid)

    # Restore Backup
    new_kb = await sdk.AsyncNucliaBackup().restore(
        restore=BackupRestore(slug=new_kb_slug, title="Test E2E Backup (can be deleted)"),
        backup_id=backup_create.id,
        zone=zone,
    )
    # Check a new KB is created
    kbs = AsyncNucliaKBS()
    kb_get = await kbs.get(id=new_kb.id)
    assert kb_get is not None

    # Wait restore is completed
    auth = get_auth()
    ndb = get_async_kb_ndb_client(zone=zone, kbid=new_kb.id, user_token=auth._config.token)
    search = AsyncNucliaSearch()

    async def check_restore_completed() -> bool:
        catalog = await search.catalog(ndb=ndb)
        return len(catalog.resources) > 0, catalog

    await wait_for(condition=check_restore_completed, max_wait=180, interval=10)

    # Delete the restored KB
    await kbs.delete(id=new_kb.id, zone=zone)
    with pytest.raises(Exception) as exc_info:  # noqa: PT011
        _ = await kbs.get(id=new_kb.id, zone=zone)
    assert exc_info.value.args[0]["status"] == 404

    # Delete backup
    await sdk.AsyncNucliaBackup().delete(id=backup_create.id, zone=zone)
    backups = await sdk.AsyncNucliaBackup().list(zone=zone)
    backup_list = [b for b in backups if b.id == backup_create.id]
    assert len(backup_list) == 0
