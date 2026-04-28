from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua import AsyncNuaClient
from nuclia.lib.nua_responses import LearningConfigurationCreation
from nuclia.sdk.predict import AsyncNucliaPredict

import pytest


@pytest.mark.asyncio_cooperative
async def test_llm_config_nua(nua_client: AsyncNuaClient, kb_id: str):
    np = AsyncNucliaPredict()

    try:
        await np.del_config(kb_id, nc=nua_client)
    except NuaAPIException:
        pass

    with pytest.raises(NuaAPIException):
        config = await np.config(kb_id, nc=nua_client)

    lcc = LearningConfigurationCreation()
    try:
        await np.set_config(kb_id, lcc, nc=nua_client)

        config = await np.config(kb_id, nc=nua_client)

        assert config.resource_labelers_models is None
        assert config.ner_model == "multilingual"
        assert config.generative_model == "chatgpt-azure-4o"
    finally:
        await np.del_config(kb_id, nc=nua_client)
