import pytest
from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua_responses import LearningConfigurationCreation
from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict


@pytest.mark.asyncio_cooperative
async def test_llm_config_nua(nua_config: AsyncNuaClient):
    np = AsyncNucliaPredict()

    try:
        await np.del_config("kbid", nc=nua_config)
    except NuaAPIException:
        pass

    with pytest.raises(NuaAPIException):
        config = await np.config("kbid", nc=nua_config)

    lcc = LearningConfigurationCreation()
    await np.set_config("kbid", lcc, nc=nua_config)

    config = await np.config("kbid", nc=nua_config)

    assert config.resource_labelers_models is None
    assert config.ner_model == "multilingual"
    assert config.generative_model == "chatgpt-azure-4o"
