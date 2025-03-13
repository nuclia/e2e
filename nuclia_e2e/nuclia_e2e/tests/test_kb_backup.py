from nuclia import sdk
from nuclia.sdk.kbs import AsyncNucliaKBS
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import wait_for
from nuclia_models.accounts.backups import BackupCreate
from nuclia_models.accounts.backups import BackupRestore

import pytest
import random
import string


@pytest.mark.asyncio_cooperative
async def test_kb_backup(request: pytest.FixtureRequest, regional_api_config: ZoneConfig):
    kb_id = regional_api_config.permanent_kb_id
    zone = regional_api_config.zone_slug
    account_slug = regional_api_config.global_config.permanent_account_slug
    sdk.NucliaAccounts().default(account_slug)

    # Create Backup
    backup_create = await sdk.AsyncNucliaBackup().create(backup=BackupCreate(kb_id=kb_id), zone=zone)

    # Wait till backup is finished
    # Get Backup
    async def check_backup_finished() -> bool:
        backups = await sdk.AsyncNucliaBackup().list(zone=zone)
        backup_list = [b for b in backups if b.id == backup_create.id]
        assert len(backup_list) == 1
        backup_object = backup_list[0]
        return backup_object.finished_at is not None

    await wait_for(condition=check_backup_finished, max_wait=180, interval=10)

    # Restore Backup
    new_kb_slug = "BackupTestE2E" + "".join(random.choices(string.ascii_letters, k=4))
    new_kb = await sdk.AsyncNucliaBackup().restore(
        restore=BackupRestore(slug=new_kb_slug, title="Test E2E Backup (can be deleted)"),
        backup_id=backup_create.id,
        zone=zone,
    )
    # TODO: Wait and check backup is restored
    kbs = AsyncNucliaKBS()
    kb_get = await kbs.get(id=new_kb.id)
    assert kb_get is not None

    # Delete the restored KB
    await kbs.delete(id=new_kb.id, zone=zone)

    # Delete backup
    await sdk.AsyncNucliaBackup().delete(id=backup_create.id, zone=zone)
