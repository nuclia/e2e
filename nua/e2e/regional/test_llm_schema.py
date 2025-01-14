from nuclia.sdk.predict import AsyncNucliaPredict
import pytest
from nuclia.lib.nua import AsyncNuaClient


@pytest.mark.asyncio_cooperative
async def test_llm_schema_nua(nua_config: AsyncNuaClient):
    np = AsyncNucliaPredict()
    config = await np.schema(nc=nua_config)

    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5


@pytest.mark.asyncio_cooperative
async def test_llm_schema_kbid(nua_config: AsyncNuaClient):
    np = AsyncNucliaPredict()
    config = await np.schema("fake_kbid", nc=nua_config)
    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5
