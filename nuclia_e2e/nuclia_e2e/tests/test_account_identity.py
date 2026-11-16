from nuclia.sdk.auth import AsyncNucliaAuth
from nuclia.sdk.kbs import AsyncNucliaKBS
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import require_test_account

import pytest


@pytest.mark.asyncio_cooperative
async def test_account_slug_resolution(
    regional_api_config: ZoneConfig, auth: AsyncNucliaAuth, account_id: str, kb_id: str
):
    assert regional_api_config.global_config is not None
    account = require_test_account(await auth.accounts(), account_id, regional_api_config.global_config.name)
    assert account.slug, f"Configured test account '{account_id}' has no usable slug"
    assert auth.get_account_id(account.slug) == account_id

    kb = await AsyncNucliaKBS().get(
        slug=regional_api_config.permanent_kb_slug,
        account=account.slug,
        zone=regional_api_config.zone_slug,
    )
    assert kb["id"] == kb_id
