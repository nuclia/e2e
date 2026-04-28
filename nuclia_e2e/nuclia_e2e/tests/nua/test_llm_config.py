from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua import AsyncNuaClient
from nuclia.lib.nua_responses import LearningConfigurationCreation
from nuclia.sdk.predict import AsyncNucliaPredict

import pytest


async def delete_config_if_present(np: AsyncNucliaPredict, kb_id: str, nua_client: AsyncNuaClient):
    try:
        await np.del_config(kb_id, nc=nua_client)
    except NuaAPIException as exc:
        if exc.code not in (204, 404):
            raise


@pytest.mark.asyncio_cooperative
async def test_llm_config_nua(nua_client: AsyncNuaClient, kb_id: str):
    np = AsyncNucliaPredict()

    await delete_config_if_present(np, kb_id, nua_client)

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
        await delete_config_if_present(np, kb_id, nua_client)
