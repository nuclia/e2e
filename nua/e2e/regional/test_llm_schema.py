from nuclia.sdk.predict import AsyncNucliaPredict
import pytest


@pytest.mark.asyncio_cooperative
async def test_llm_schema_nua(nua_config):
    np = AsyncNucliaPredict()
    config = await np.schema()

    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5


@pytest.mark.asyncio_cooperative
async def test_llm_schema_kbid(nua_config):
    np = AsyncNucliaPredict()
    config = await np.schema("fake_kbid")
    assert len(config.ner_model.options) == 1
    assert len(config.generative_model.options) >= 5
