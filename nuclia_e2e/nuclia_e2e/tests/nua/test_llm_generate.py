from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_LLMS

import pytest


# Assumtion is that when they fail is either
# - server overload (ours or llm provider)
# - asyncio loop overload
# - Transient error
# For any t of hese reasons, make sense not to retry immediately
@pytest.mark.flaky(reruns=2, reruns_delay=10)
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_generate(nua_client: AsyncNuaClient, model):
    np = AsyncNucliaPredict()
    generated = await np.generate("Which is the capital of Catalonia?", model=model, nc=nua_client)
    assert "Barcelona" in generated.answer
