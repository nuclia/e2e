from collections.abc import Callable
from nuclia.sdk.kbs import AsyncNucliaKBS
from nuclia_e2e.tests.conftest import RegionalAPI
from nuclia_e2e.tests.conftest import ZoneConfig
from nuclia_e2e.utils import create_test_kb
from nuclia_e2e.utils import delete_test_kb
from nuclia_e2e.utils import get_kbid_from_slug

import pytest

Logger = Callable[[str], None]


@pytest.mark.asyncio_cooperative
async def test_kb_vectorsets(
    request: pytest.FixtureRequest, regional_api: RegionalAPI, regional_api_config: ZoneConfig
):
    def logger(msg):
        print(f"{request.node.name} ::: {msg}")

    current_embedding_model = "multilingual-2024-05-06"
    new_embedding_model = "text-embedding-3-small"

    kb_slug = f"{regional_api_config.test_kb_slug}-test_kb_vectorsets"

    # Make sure the kb used for this test is deleted, as the slug is reused:
    old_kbid = await get_kbid_from_slug(regional_api_config.zone_slug, kb_slug)
    if old_kbid is not None:
        await AsyncNucliaKBS().delete(zone=regional_api_config.zone_slug, id=old_kbid)

    # Creates a brand new kb that will be used troughout this test
    kb_id = await create_test_kb(regional_api_config, kb_slug, logger)

    kb_config = await regional_api.get_configuration(kb_id=kb_id)
    assert set(kb_config["semantic_models"]) == {current_embedding_model}

    await regional_api.create_vector_set(kb_id=kb_id, model=new_embedding_model)

    kb_config = await regional_api.get_configuration(kb_id=kb_id)
    assert set(kb_config["semantic_models"]) == {current_embedding_model, new_embedding_model}

    await regional_api.delete_vector_set(kb_id=kb_id, model=new_embedding_model)

    kb_config = await regional_api.get_configuration(kb_id=kb_id)
    assert set(kb_config["semantic_models"]) == {current_embedding_model}

    # Delete the kb as a final step
    await delete_test_kb(regional_api_config, kb_id, kb_slug, logger)
