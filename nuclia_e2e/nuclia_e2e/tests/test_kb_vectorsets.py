from nuclia_e2e.tests.conftest import RegionalAPI
from nuclia_e2e.tests.conftest import ZoneConfig

import pytest


@pytest.mark.asyncio_cooperative
async def test_kb_vectorsets(regional_api: RegionalAPI, regional_api_config: ZoneConfig):
    kb_id = regional_api_config.permanent_kb_id
    current_embedding_model = "multilingual-2024-05-06"
    new_embedding_model = "text-embedding-3-small"

    kb_config = await regional_api.get_configuration(kb_id=kb_id)
    assert set(kb_config["semantic_models"]) == {current_embedding_model}

    await regional_api.create_vector_set(kb_id=kb_id, model=new_embedding_model)

    kb_config = await regional_api.get_configuration(kb_id=kb_id)
    assert set(kb_config["semantic_models"]) == {current_embedding_model, new_embedding_model}

    await regional_api.delete_vector_set(kb_id=kb_id, model=new_embedding_model)

    kb_config = await regional_api.get_configuration(kb_id=kb_id)
    assert set(kb_config["semantic_models"]) == {current_embedding_model}
