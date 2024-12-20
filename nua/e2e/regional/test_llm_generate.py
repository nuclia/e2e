import pytest
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia.lib.nua import AsyncNuaClient
from regional.models import ALL_LLMS


@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_generate(nua_config: AsyncNuaClient, model):
    np = AsyncNucliaPredict()
    generated = await np.generate(
        "Which is the capital of Catalonia?", model=model, nc=nua_config
    )
    assert "Barcelona" in generated.answer
