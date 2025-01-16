from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict

import pytest


@pytest.mark.asyncio_cooperative
async def test_llm_schema_nua(nua_client: AsyncNuaClient):
    np = AsyncNucliaPredict()
    config = await np.schema(nc=nua_client)

    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5


@pytest.mark.asyncio_cooperative
async def test_llm_schema_kbid(nua_client: AsyncNuaClient):
    np = AsyncNucliaPredict()
    config = await np.schema("fake_kbid", nc=nua_client)
    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5
