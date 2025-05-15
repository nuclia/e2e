from nuclia.lib.nua import AsyncNuaClient
from nuclia.sdk.predict import AsyncNucliaPredict
from nuclia_e2e.models import ALL_LLMS
from nuclia_e2e.utils import make_retry_async
import pytest


# Assumtion is that when they fail is either
# - server overload (ours or llm provider)
# - asyncio loop overload
# - Transient error
# For any t of hese reasons, make sense not to retry immediately
@pytest.mark.asyncio_cooperative
@pytest.mark.parametrize("model", ALL_LLMS)
async def test_llm_rag(nua_client: AsyncNuaClient, model):
    np = AsyncNucliaPredict()

    @make_retry_async(attempts=3, delay=10, exceptions=(AssertionError))
    async def retryable_block():
        generated = await np.rag(
            question="Which is the CEO of Nuclia?",
            context=[
                "Nuclia CTO is Ramon Navarro",
                "Eudald Camprubí is CEO at the same company as Ramon Navarro",
            ],
            model=model,
            nc=nua_client,
        )
        assert "Eudald" in generated.answer

    await retryable_block()
